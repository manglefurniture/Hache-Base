#!/usr/bin/env python3
"""VAST-003 fixed SSH deployment channel: VPS -> one authorised running Vast instance.

No Vast rental, start, stop, shell API, HMAC transfer, or miner start.
"""
import argparse
import hashlib
import os
import stat
import time
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

import access_gateway as gateway

FILES = frozenset({'vast-auto-prepare.py','vast-instance-prepare.py',
                   'vast-onstart.sh','vast-collector.py'})
COMMIT = re.compile(r'[a-f0-9]{40}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
MAX_BUNDLE = 2 * 1024 * 1024
APPROVAL = '/etc/hache-mining-operator/approved-vast-release.json'
REMOTE_BASE = '/root/hache-vast/releases'


class DeployError(Exception):
    pass


def git_blob(data):
    """Compare bytes with the precise Git blob IDs trusted by root."""
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + bytes([0]) + data).hexdigest()


def load_approval(path=APPROVAL, now=None):
    """Root-controlled, per-instance, per-action authorization. Not writable by GPT."""
    now = int(time.time() if now is None else now)
    file=Path(path)
    try:
        info=file.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                info.st_nlink != 1 or info.st_mode & 0o077):
            raise DeployError('unsafe_root_approval')
        with file.open('rb') as h:
            raw=h.read(8193)
        if len(raw)>8192:
            raise DeployError('approval_too_large')
        a=json.loads(raw)
    except (OSError,ValueError):
        raise DeployError('approval_not_available') from None
    fields={'repository','commit','instance_id','machine_id','host_id',
            'gpu_count','ssh_host','ssh_port','approved_action',
            'not_before','expires_at','archive_sha256','files'}
    if not isinstance(a,dict) or set(a)!=fields:
        raise DeployError('invalid_root_approval')
    if (a['repository']!='manglefurniture/HACHE-MINER' or
            type(a['not_before']) is not int or type(a['expires_at']) is not int or
            not a['not_before']<=now<=a['expires_at'] or
            not 0<a['expires_at']-a['not_before']<=900 or
            a['approved_action'] not in ('stage','apply') or
            not COMMIT.fullmatch(a['commit']) or
            not SHA.fullmatch(a['archive_sha256']) or
            not isinstance(a['files'],dict) or set(a['files'])!=FILES or
            any(not COMMIT.fullmatch(h) for h in a['files'].values()) or
            not re.fullmatch(r'[1-9][0-9]{3,14}',str(a['instance_id'])) or
            not isinstance(a['machine_id'],int) or a['machine_id']<=0 or
            not isinstance(a['host_id'],int) or a['host_id']<=0 or
            type(a['gpu_count']) is not int or not 1<=a['gpu_count']<=16 or
            not isinstance(a['ssh_host'],str) or
            not gateway.HOST.fullmatch(a['ssh_host']) or
            type(a['ssh_port']) is not int or not 1<=a['ssh_port']<=65535):
        raise DeployError('invalid_or_expired_root_approval')
    return a


def check_approval(a, p, action, commit, now=None):
    now=int(time.time() if now is None else now)
    if not isinstance(a,dict) or action!=a['approved_action'] or commit!=a['commit']:
        raise DeployError('action_or_commit_not_approved')
    if not a['not_before']<=now<=a['expires_at']:
        raise DeployError('root_approval_expired')
    if (p['provider']!='vast' or p['instance_id']!=str(a['instance_id']) or
            p['machine_id']!=a['machine_id'] or p['host_id']!=a['host_id'] or
            p['gpu_count']!=a['gpu_count'] or p['host']!=a['ssh_host'] or
            p['port']!=a['ssh_port']):
        raise DeployError('profile_not_approved')


def validate_archive(filename, approval):
    """Tar digest alone is not trust: require root-pinned, per-file Git blobs."""
    file = Path(gateway.safe_file(filename, private=True))
    if file.stat().st_size > MAX_BUNDLE:
        raise DeployError('bundle_too_large')
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != approval['archive_sha256']:
        raise DeployError('bundle_sha256_mismatch')
    import io
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        entries = archive.getmembers()
        if (len(entries)!=len(FILES) or
                {e.name for e in entries} != FILES or
                any(not e.isfile() or e.size<=0 or e.size>300000
                    for e in entries)):
            raise DeployError('unexpected_bundle_contents')
        for member in entries:
            inp=archive.extractfile(member)
            if inp is None or git_blob(inp.read())!=approval['files'][member.name]:
                raise DeployError('unapproved_github_blob')
    return raw


def command_line(p, script):
    # Use existing pinned SSH profile and all of the host-key/identity defenses.
    args = gateway.ssh_args(p, 'clock')
    return args[:-1]+[script]


def verify_target(p, instance_id, send=gateway.broker):
    gateway.verify_profile(p)
    if p['provider']!='vast' or p['instance_id']!=instance_id:
        raise DeployError('target_not_approved')
    gateway.require_running(p, send=send)
    return True


def run_remote(p, action, commit, *, bundle=None, runner=subprocess.run):
    if not COMMIT.fullmatch(commit):
        raise DeployError('invalid_release_commit')
    dest = REMOTE_BASE+'/'+commit
    # Commands are entirely generated from static strings and pinned SHA,
    # never from user-provided arbitrary commands or filenames.
    if action=='stage':
        if bundle is None:
            raise DeployError('bundle_required')
        command = (
            'set -eu; umask 077; '
            'test ! -L /root/hache-vast && '
            'install -d -m 0700 /root/hache-vast /root/hache-vast/releases && '
            'test ! -L /root/hache-vast/releases && '
            'test ! -e '+dest+' && '
            'install -d -m 0700 '+dest+' && '
            'tar --no-same-owner --no-same-permissions -xzf - -C '+dest+' && '
            'chmod 0700 '+dest+'/*.py '+dest+'/*.sh'
        )
        data = bundle
    elif action=='apply':
        command=(
            'set -eu; '
            'test ! -L '+dest+' && '
            'test -f '+dest+'/vast-auto-prepare.py && '
            'python3 '+dest+'/vast-auto-prepare.py '
            '--recipe /etc/hache-vast/approved-recipe.json '
            '--apply --confirm-instance '+p['instance_id']
        )
        data=None
    else:
        raise DeployError('unsupported_remote_action')
    try:
        result=runner(command_line(p, command), input=data,
                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                      timeout=180, check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise DeployError('ssh_command_unavailable') from None
    if result.returncode:
        # Never expose private wallet/host logs or arbitrary remote stderr.
        raise DeployError('ssh_'+action+'_failed')
    return {'action':action,'instance_id':p['instance_id'],
            'release_commit':commit,'accepted':True,
            'mining_started':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--profiles',default=gateway.DEFAULT_PROFILES)
    parser.add_argument('--instance-id',required=True)
    parser.add_argument('--release-commit',required=True)
    parser.add_argument('--bundle')
    parser.add_argument('--stage',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--confirm-instance')
    args=parser.parse_args()
    try:
        if args.stage and args.apply:
            raise DeployError('choose_one_operation')
        if (args.stage or args.apply) and args.confirm_instance!=args.instance_id:
            raise DeployError('explicit_target_confirmation_required')
        p=gateway.profile_from_file(args.profiles,args.profile)
        gateway.verify_profile(p)
        if p['instance_id']!=args.instance_id or p['provider']!='vast':
            raise DeployError('profile_instance_mismatch')
        if not COMMIT.fullmatch(args.release_commit):
            raise DeployError('invalid_release_commit')
        if not args.stage and not args.apply:
            print(json.dumps({'ok':True,'status':'offline_plan_only',
                             'instance_id':args.instance_id,
                             'release_commit':args.release_commit}))
            return 0
        action='stage' if args.stage else 'apply'
        approval=load_approval()
        check_approval(approval,p,action,args.release_commit)
        bundle=None
        if args.stage:
            if not args.bundle:
                raise DeployError('approved_bundle_required')
            bundle=validate_archive(args.bundle,approval)
        verify_target(p,args.instance_id)
        result=run_remote(p,action,args.release_commit,bundle=bundle)
        print(json.dumps({'ok':True,'result':result}))
        return 0
    except (gateway.AccessError,DeployError,OSError,ValueError,tarfile.TarError):
        print(json.dumps({'ok':False,'error':'vast_provision_not_ready'}))
        return 2


if __name__=='__main__':
    sys.exit(main())
