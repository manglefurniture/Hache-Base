#!/usr/bin/env python3
"""VAST-004 one-action SSH bridge for the broker's root-approved plans.

Run ONLY as the protected hache-miner service account, not root/gpt-agent.
It cannot rent/start/stop GPUs or execute an arbitrary SSH command. SSH key
must have forced-command restrictions installed on the Vast host.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import subprocess
import sys
import time

COMMIT=re.compile('[a-f0-9]{40}\\Z')
HASH=re.compile('[a-f0-9]{64}\\Z')
INSTANCE=re.compile('[1-9][0-9]{3,14}\\Z')
ACTIONS={'stage','configure','apply'}
ROOT=Path('/etc/hache-mining-operator/vast-provision')
BUNDLES=Path('/var/lib/hache-mining-operator/bundles')
DB=Path('/var/lib/hache-mining-operator/state.sqlite')
RECEIVER='root'
LIMIT=2*1024*1024


class Reject(Exception):
    pass


def owner_file(path, uid=0, *, secret=False, limit=16384):
    path=Path(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or st.st_nlink!=1 or
                st.st_mode & 0o022 or (secret and st.st_mode & 0o007)):
            raise Reject('unsafe_private_input')
        with os.fdopen(fd,'rb',closefd=False) as stream:
            raw=stream.read(limit+1)
        if len(raw)>limit:
            raise Reject('private_input_too_large')
        return raw
    finally:
        os.close(fd)


def load_target(instance_id, directory=ROOT):
    if not INSTANCE.fullmatch(instance_id):
        raise Reject('invalid_instance')
    config=json.loads(owner_file(Path(directory)/(instance_id+'.json')))
    exact={'instance_id','machine_id','host_id','gpu_count','ssh_host',
           'ssh_port','key_file','known_hosts','release_commit','archive_sha256'}
    if not isinstance(config,dict) or set(config)!=exact:
        raise Reject('invalid_target_config')
    if (config['instance_id']!=instance_id or
            type(config['machine_id']) is not int or config['machine_id']<1 or
            type(config['host_id']) is not int or config['host_id']<1 or
            type(config['gpu_count']) is not int or not 1<=config['gpu_count']<=16 or
            type(config['ssh_host']) is not str or
            not re.fullmatch('[A-Za-z0-9.-]{2,253}',config['ssh_host']) or
            type(config['ssh_port']) is not int or not 1<=config['ssh_port']<=65535 or
            type(config['release_commit']) is not str or not COMMIT.fullmatch(config['release_commit']) or
            type(config['archive_sha256']) is not str or not HASH.fullmatch(config['archive_sha256'])):
        raise Reject('invalid_target_identity')
    # Restrict file references to a root-controlled directory. Never accept
    # paths from the GPT request or arbitrary /root /home files.
    for field in ('key_file','known_hosts'):
        path=config[field]
        if type(path) is not str or not re.fullmatch(
                r'/etc/hache-mining-operator/ssh/[a-zA-Z0-9_-]{1,70}[.](?:key|known_hosts)',path):
            raise Reject('unapproved_ssh_credential_path')
        owner_file(path,secret=(field=='key_file'),limit=262144)
    return config


def configured_database():
    from broker import protected_json
    cfg=protected_json('/etc/hache-mining-operator/config.json')
    value=cfg.get('database')
    if (type(value) is not str or
            not value.startswith('/var/lib/hache-mining-operator/') or
            '..' in Path(value).parts):
        raise Reject('untrusted_broker_database')
    return Path(value)


def lease_active(instance, database=None, now=None, min_remaining=120):
    if database is None:
        database=configured_database()
    now=int(time.time() if now is None else now)
    try:
        db=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=2)
        try:
            row=db.execute(
                "SELECT deadline FROM vast_leases WHERE instance_id=? "
                "AND phase='armed' ORDER BY deadline DESC LIMIT 1",(instance,)).fetchone()
            heartbeat=db.execute('SELECT completed_at FROM lease_guard_heartbeat WHERE id=1').fetchone()
        finally:
            db.close()
    except (OSError,sqlite3.Error):
        raise Reject('financial_supervisor_unavailable') from None
    if (not row or not heartbeat or
            not 0<=now-int(heartbeat[0])<=90 or
            int(row[0])-now<min_remaining):
        raise Reject('financial_lease_required')
    return int(row[0])


def live_identity(op, cfg, *, provider, database=None, now=None):
    if (type(op) is not dict or set(op)!={'action','instance_id','release_commit','step'} or
            op['action']!='vast.provision' or
            type(op['instance_id']) is not str or not INSTANCE.fullmatch(op['instance_id']) or
            op['release_commit']!=cfg['release_commit'] or op['step'] not in ACTIONS):
        raise Reject('operation_not_allowed')
    deadline=lease_active(op['instance_id'],database,now,
                          min_remaining=240 if op['step']=='apply' else 90)
    p=provider(op['instance_id'])
    if (str(p.get('id'))!=op['instance_id'] or
            p.get('actual_status')!='running' or
            p.get('intended_status')!='running' or
            p.get('machine_id')!=cfg['machine_id'] or
            p.get('host_id')!=cfg['host_id'] or
            p.get('num_gpus')!=cfg['gpu_count'] or
            p.get('ssh_host')!=cfg['ssh_host'] or
            p.get('ssh_port')!=cfg['ssh_port']):
        raise Reject('provider_identity_or_state_changed')
    return {'instance_id':op['instance_id'],'machine_id':cfg['machine_id'],
            'host_id':cfg['host_id'],'gpu_count':cfg['gpu_count'],
            'ssh_host':cfg['ssh_host'],'ssh_port':cfg['ssh_port'],
            'release_commit':cfg['release_commit'],'bundle_sha256':cfg['archive_sha256'],
            'step':op['step'],'financial_lease_deadline':deadline}


def broker_provider(instance):
    from broker import safe_helper,protected_json
    cfg=protected_json('/etc/hache-mining-operator/config.json')
    res=safe_helper(cfg['helper_command'],'query',
                    {'action':'vast.inspect','instance_id':instance})
    if not isinstance(res,dict):
        raise Reject('provider_identity_unknown')
    return res


def verified_payload(op,cfg,*,bundles=BUNDLES,secrets_dir=ROOT):
    if op['step']=='apply':
        return b''
    if op['step']=='stage':
        path=Path(bundles)/(cfg['release_commit']+'.tar.gz')
        body=owner_file(path,limit=LIMIT)
        if hashlib.sha256(body).hexdigest()!=cfg['archive_sha256']:
            raise Reject('archive_not_pinned')
        return body
    body=owner_file(Path(secrets_dir)/(op['instance_id']+'.private.json'),
                    secret=True,limit=16384)
    try:
        envelope=json.loads(body)
        if (not isinstance(envelope,dict) or set(envelope)!= {'recipe','ingest_key'} or
                envelope['recipe']['instance_id']!=op['instance_id'] or
                str(envelope['recipe']['machine_id'])!=str(cfg['machine_id']) or
                str(envelope['recipe']['host_id'])!=str(cfg['host_id']) or
                envelope['recipe']['gpu_count']!=cfg['gpu_count']):
            raise Reject('private_config_identity_mismatch')
    except (KeyError,TypeError,ValueError):
        raise Reject('private_config_invalid') from None
    return body


def ssh_args(cfg,op):
    return [
        '/usr/bin/ssh','-T','-o','BatchMode=yes',
        '-o','PasswordAuthentication=no','-o','IdentitiesOnly=yes',
        '-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no',
        '-o','ClearAllForwardings=yes','-o','PermitLocalCommand=no',
        '-o','ConnectTimeout=12','-o','ConnectionAttempts=1',
        '-o','UserKnownHostsFile='+cfg['known_hosts'],
        '-i',cfg['key_file'],'-p',str(cfg['ssh_port']),
        'root@'+cfg['ssh_host'],
        op['step']+' '+op['instance_id']+' '+op['release_commit'],
    ]


def execute(op,cfg,*,provider=broker_provider,runner=subprocess.run,database=None):
    # Verify identities AND active independent financial lease a second time.
    live_identity(op,cfg,provider=provider,database=database)
    data=verified_payload(op,cfg)
    try:
        p=runner(ssh_args(cfg,op),input=data,
                 stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                 timeout=185 if op['step']=='apply' else 75,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise Reject('ssh_outcome_unknown') from None
    if p.returncode:
        raise Reject('ssh_provision_failed_or_unknown')
    try:
        response=json.loads(p.stdout)
    except (ValueError,TypeError):
        raise Reject('invalid_receiver_response') from None
    if (response.get('ok') is not True or
            response.get('mining_started') is not False or
            response.get('status') not in
            ('staged','already_staged','configured','miner_prepared_not_started')):
        raise Reject('receiver_not_confirmed')
    return {'status':response['status'],'mining_started':False,
            'instance_id':op['instance_id'],
            'verification_required':True}


def dispatch(req,*,provider=broker_provider,database=None):
    if not isinstance(req,dict) or set(req) not in (
            {'mode','operation'},{'mode','operation','snapshot'}):
        raise Reject('invalid_command_envelope')
    mode,op=req.get('mode'),req.get('operation')
    if type(op) is not dict or type(op.get('instance_id')) is not str:
        raise Reject('invalid_command')
    cfg=load_target(op['instance_id'])
    if mode=='prepare' and set(req)=={'mode','operation'}:
        return live_identity(op,cfg,provider=provider,database=database)
    if mode=='execute' and set(req)=={'mode','operation','snapshot'}:
        current=live_identity(op,cfg,provider=provider,database=database)
        if current!=req['snapshot']:
            raise Reject('provision_target_changed')
        return execute(op,cfg,provider=provider,database=database)
    raise Reject('unsupported_provision_mode')


def main():
    try:
        if os.geteuid()!=pwd.getpwnam('hache-miner').pw_uid:
            raise Reject('protected_service_identity_required')
        raw=sys.stdin.buffer.read(8193)
        if len(raw)>8192:
            raise Reject('oversize_command')
        result=dispatch(json.loads(raw))
        print(json.dumps({'ok':True,'result':result},separators=(',',':')))
    except (Reject,ValueError,TypeError,KeyError,OSError,sqlite3.Error):
        print(json.dumps({'ok':False,'error':'target_not_ready'}))
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
