#!/usr/bin/env python3
"""Root-isolated release activator: exact one-use deployment grants, never GPUs.

The server accepts only a local gpt-agent UID and two fixed GitHub projects.
The release bundle MUST be independently verified against the approved GitHub
commit and CI by the owner BEFORE issuing its exact root grant. Its SHA256 alone
does not prove GitHub origin. No automatic root approval is provided here.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import socket
import socketserver
import sqlite3
import stat
import struct
import subprocess
import tarfile
import tempfile
import time

TARGETS = {
    'hache-miner': {
        'repo': 'manglefurniture/HACHE-MINER',
        'root': '/srv/hache-miner',
        'release_subdir': '',
        'anchors': ['public/index.php','app/core.php','database/001_initial.sql'],
        'lint': ['public/index.php','app/core.php'],
    },
    'hache-base': {
        'repo': 'manglefurniture/Hache-Base',
        'root': '/opt/hache-mining-operator',
        'release_subdir': 'extensions/mining-operator',
        'anchors': ['extensions/mining-operator/broker.py',
                    'extensions/mining-operator/authorize.py',
                    'extensions/mining-operator/provider.php',
                    'extensions/mining-operator/vast_start_guard.py'],
        'lint': ['extensions/mining-operator/provider.php'],
    },
}
SHA = re.compile(r'[a-f0-9]{40}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
PLAN = re.compile(r'[a-f0-9]{32}\Z')
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_UNPACKED = 350 * 1024 * 1024
MAX_FILES = 24000


class Rejected(Exception):
    pass


def compact(o):
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def fingerprint(o):
    return hashlib.sha256(compact(o).encode()).hexdigest()


def trusted_json(path, *, uid=0, maxbytes=4096):
    path=Path(path)
    fd=os.open(path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as handle:
        st=os.fstat(handle.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or
                st.st_mode & 0o022 or st.st_nlink!=1):
            raise Rejected('untrusted_file')
        raw=handle.read(maxbytes+1)
    if len(raw)>maxbytes:
        raise Rejected('file_too_large')
    return json.loads(raw)


def valid_request(req):
    if not isinstance(req,dict):
        raise Rejected('invalid_request')
    method=req.get('method')
    if method=='capabilities' and set(req)=={'method'}:
        return method,None
    if method=='prepare' and set(req)=={'method','target','commit','archive_sha256'}:
        target,commit,digest=req['target'],req['commit'],req['archive_sha256']
        if (type(target) is not str or target not in TARGETS or
                type(commit) is not str or not SHA.fullmatch(commit) or
                type(digest) is not str or not HASH.fullmatch(digest)):
            raise Rejected('invalid_release_identity')
        return method,{'target':target,'commit':commit,'archive_sha256':digest}
    if method in ('execute','status') and set(req)=={'method','plan_id'} and (
            type(req['plan_id']) is str and PLAN.fullmatch(req['plan_id'])):
        return method,req['plan_id']
    raise Rejected('invalid_request_fields')


def safe_archive(path):
    """No special nodes, paths, symlinks, duplicate names or secrets."""
    names=set()
    total=0
    with tarfile.open(path,'r:gz') as bundle:
        members=bundle.getmembers()
        if len(members)>MAX_FILES:
            raise Rejected('archive_too_many_entries')
        for item in members:
            n=item.name
            parts=PurePosixPath(n).parts
            if (not n or n.startswith('/') or '\\' in n or
                    not parts or any(x in ('.','..') for x in parts) or
                    n in names or not (item.isdir() or item.isfile())):
                raise Rejected('unsafe_archive_member')
            names.add(n)
            if item.isfile():
                total+=item.size
                if total>MAX_UNPACKED:
                    raise Rejected('archive_expansion_limit')
                bn=parts[-1].lower()
                if (bn in ('.env','runtime.php') or bn.startswith('.env.') or
                        bn.endswith(('.pem','.key','.p12','.pfx'))):
                    raise Rejected('private_file_in_release')
        return names


def strict_symlink_destination(current, release_dir):
    current=Path(current)
    root=Path(release_dir).resolve(strict=True)
    if not current.is_symlink():
        raise Rejected('current_not_a_symlink')
    try:
        link=current.resolve(strict=True)
    except OSError:
        raise Rejected('missing_current_release') from None
    try:
        relative=link.relative_to(root).parts
    except ValueError:
        raise Rejected('current_not_a_release') from None
    if not relative or not SHA.fullmatch(relative[0]) or (
            len(relative)!=1 and
            (len(relative)!=3 or relative[1:]!=('extensions','mining-operator'))):
        raise Rejected('current_not_a_release')
    if not link.exists() or not link.is_dir():
        raise Rejected('missing_current_release')
    return link


def own_file_copy(incoming, dest, uid):
    """Copy to root-private storage before hashing, to close upload TOCTOU."""
    fd=os.open(incoming,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or
                st.st_mode & 0o022 or st.st_nlink!=1 or
                not 0<st.st_size<=MAX_ARCHIVE):
            raise Rejected('untrusted_submission')
        with os.fdopen(fd,'rb',closefd=False) as src, open(dest,'xb') as out:
            digest=hashlib.sha256()
            count=0
            for block in iter(lambda:src.read(1024*1024), b''):
                count+=len(block)
                if count>MAX_ARCHIVE:
                    raise Rejected('archive_too_large')
                digest.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        return digest.hexdigest()
    finally:
        os.close(fd)


def extract_fixed_archive(archive, work):
    names=safe_archive(archive)
    root=Path(work)
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            parts=PurePosixPath(member.name).parts
            path=root.joinpath(*parts)
            if member.isdir():
                path.mkdir(mode=0o755,parents=True,exist_ok=True)
                continue
            path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
            stream=tar.extractfile(member)
            if stream is None:
                raise Rejected('archive_read_failed')
            with open(path,'xb') as out:
                shutil.copyfileobj(stream,out,1024*1024)
            # Preserve executable intent for approved scripts, never write bits.
            path.chmod(0o755 if member.mode & 0o111 else 0o644)
    for folder, subs, files in os.walk(root):
        Path(folder).chmod(0o755)
    return names


def swap_current(root, to):
    root=Path(root)
    current=root/'current'
    if not str(to).startswith(str((root/'releases').resolve())+'/'):
        raise Rejected('outside_release_root')
    temp=root/('.deploy-next-'+secrets.token_hex(8))
    os.symlink(str(to), temp)
    try:
        os.replace(temp,current)
    finally:
        if temp.is_symlink():
            temp.unlink()


def run_checks(target, release):
    meta=TARGETS[target]
    root=Path(release)
    if any(not (root/name).is_file() or (root/name).is_symlink()
           for name in meta['anchors']):
        raise Rejected('incomplete_release')
    for name in meta['lint']:
        p=subprocess.run(['/usr/bin/php','-l',str(root/name)],
                         capture_output=True,text=True,timeout=20)
        if p.returncode:
            raise Rejected('release_lint_failed')
    if target=='hache-base':
        # Parsing avoids executing newly supplied repository code as root.
        for source in (root/'extensions/mining-operator').glob('*.py'):
            if source.is_symlink():
                raise Rejected('unsafe_python_source')
            try:
                ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
            except (SyntaxError,UnicodeError):
                raise Rejected('invalid_python_source') from None


def check_financial_guard_clear(config_path='/etc/hache-mining-operator/config.json'):
    """Refuse to upgrade a running miner/watchdog during a Vast start lease."""
    try:
        cfg=trusted_json(config_path)
        database=Path(cfg['database'])
        if not database.is_absolute() or not database.is_relative_to(
                Path('/var/lib/hache-mining-operator')):
            raise Rejected('unexpected_operator_database')
        con=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=2)
        try:
            active=con.execute("SELECT COUNT(*) FROM vast_leases WHERE phase='armed'").fetchone()[0]
            row=con.execute('SELECT completed_at FROM lease_guard_heartbeat WHERE id=1').fetchone()
        finally:
            con.close()
        if active:
            raise Rejected('active_financial_lease_blocks_deployment')
        if not row or not 0<=time.time()-float(row[0])<=90:
            raise Rejected('financial_guard_unhealthy')
    except (OSError,sqlite3.Error,KeyError,TypeError,ValueError):
        raise Rejected('financial_guard_unverified') from None


def check_health(target, *, restart=False):
    """Passive tests on HACHE-MINER; fixed service restart only for the broker."""
    if target=='hache-base' and restart:
        # No arbitrary service names or arguments supplied by the agent.
        s=subprocess.run(['/usr/bin/systemctl','restart','hache-mining-operator.service'],
                         capture_output=True,timeout=25)
        if s.returncode:
            raise Rejected('operator_restart_failed')
    services=(['hache-mining-operator.service','hache-mining-operator.socket',
               'hache-mining-operator-vast-lease.timer']
              if target=='hache-base'
              else ['hache-miner-vast-watchdog.timer','hache-miner-vast-auto-stop.timer'])
    for service in services:
        r=subprocess.run(['/usr/bin/systemctl','is-active','--quiet',service],
                         capture_output=True,timeout=8)
        if r.returncode:
            raise Rejected('service_health_unknown')


class Gate:
    def __init__(self, cfg, *, now=time.time, owner_uid=0, deploy_fn=None):
        self.cfg=cfg
        self.now=now
        self.db=sqlite3.connect(cfg['database'],isolation_level=None,timeout=5)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS deploy_plans(
            id TEXT PRIMARY KEY, operation TEXT NOT NULL,
            snapshot TEXT NOT NULL, digest TEXT NOT NULL,
            expires INTEGER NOT NULL,phase TEXT NOT NULL,
            result TEXT);
          CREATE TABLE IF NOT EXISTS deploy_events(
            id INTEGER PRIMARY KEY,plan_id TEXT,phase TEXT,at INTEGER);
          CREATE TABLE IF NOT EXISTS deploy_requests(at INTEGER NOT NULL);
        ''')
        self.owner_uid=owner_uid
        self.deploy_fn=deploy_fn or self.activate

    def close(self):
        self.db.close()

    def charge(self):
        # A compromised agent must not fill root's archive cache or plan DB.
        stamp=int(self.now())
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('DELETE FROM deploy_requests WHERE at<?',(stamp-86400,))
            count=self.db.execute('SELECT COUNT(*) FROM deploy_requests WHERE at>?',
                                  (stamp-3600,)).fetchone()[0]
            if count>=120:
                raise Rejected('deployment_request_rate_limited')
            self.db.execute('INSERT INTO deploy_requests(at) VALUES(?)',(stamp,))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def srcpath(self, op):
        return (Path(self.cfg['inbox'])/op['target']/
                (op['commit']+'.tar.gz'))

    def gc_archives(self, *, now=None):
        """Prune old unreferenced root-owned bundles; never delete a live plan."""
        now=int(self.now() if now is None else now)
        directory=Path(self.cfg['state_dir'])/'approved-sources'
        directory.mkdir(mode=0o700,exist_ok=True)
        protected=set()
        for raw,expires,phase in self.db.execute(
                "SELECT operation,expires,phase FROM deploy_plans "
                "WHERE phase IN ('prepared','claimed')"):
            try:
                op=json.loads(raw)
                if expires+3600>now and HASH.fullmatch(op['archive_sha256']):
                    protected.add(op['archive_sha256'])
            except (ValueError,TypeError,KeyError):
                raise Rejected('plan_archive_index_corrupt') from None
        for item in directory.glob('*.tar.gz'):
            st=item.lstat()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid!=self.owner_uid or
                    st.st_nlink!=1 or st.st_mode & 0o022):
                raise Rejected('unsafe_root_cache_entry')
            digest=item.name[:-7]
            if (HASH.fullmatch(digest) and digest not in protected and
                    st.st_mtime<now-3600):
                item.unlink()
        return protected

    def cache_archive(self, op):
        destdir=Path(self.cfg['state_dir'])/'approved-sources'
        destdir.mkdir(mode=0o700,exist_ok=True)
        self.gc_archives()
        dest=destdir/(op['archive_sha256']+'.tar.gz')
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=op['archive_sha256']:
                raise Rejected('cached_archive_changed')
            safe_archive(dest)
            return dest
        if sum(1 for _ in destdir.glob('*.tar.gz'))>=8:
            raise Rejected('private_archive_cache_full')
        temp=destdir/('.pending-'+secrets.token_hex(12))
        try:
            found=own_file_copy(self.srcpath(op),temp,self.cfg['agent_uid'])
            if found!=op['archive_sha256']:
                raise Rejected('source_digest_mismatch')
            safe_archive(temp)
            os.replace(temp,dest)
        finally:
            if temp.exists():
                temp.unlink()
        return dest

    def status_snapshot(self,op):
        meta=TARGETS[op['target']]
        old=strict_symlink_destination(Path(meta['root'])/'current',
                                       Path(meta['root'])/'releases')
        return {'previous_release':str(old),'target':op['target'],
                'repository':meta['repo'],'archive_sha256':op['archive_sha256'],
                'commit':op['commit']}

    def handle(self, request):
        method,op=valid_request(request)
        if method=='capabilities':
            return {'targets':sorted(TARGETS),
                    'authority':'requires exact root authorization; no agent sudo',
                    'source':'root-reviewed GitHub commit + CI and digest; no dynamic commands'}
        if method=='prepare':
            self.cache_archive(op)
            snap=self.status_snapshot(op)
            digest=fingerprint({'operation':op,'snapshot':snap})
            pid=secrets.token_hex(16)
            expires=int(self.now())+300
            self.db.execute('INSERT INTO deploy_plans VALUES(?,?,?,?,?,?,NULL)',
                            (pid,compact(op),compact(snap),digest,expires,'prepared'))
            self.db.execute('INSERT INTO deploy_events VALUES(NULL,?,?,?)',
                            (pid,'prepared',int(self.now())))
            return {'plan_id':pid,'digest':digest,'expires_at':expires,
                    'operation':op,'snapshot':snap,
                    'owner_review_required':'Verify GitHub merge, CI and SHA256; root must approve'}
        pid=op
        row=self.db.execute('SELECT operation,snapshot,digest,expires,phase,result '
                            'FROM deploy_plans WHERE id=?',(pid,)).fetchone()
        if not row:
            raise Rejected('plan_not_found')
        result={'plan_id':pid,'phase':row[4],
                'result':json.loads(row[5]) if row[5] else None}
        if method=='status' or row[4]!='prepared':
            return result
        operation=json.loads(row[0])
        snap=json.loads(row[1])
        stamp=int(self.now())
        if row[3]<=stamp:
            raise Rejected('plan_expired')
        if fingerprint({'operation':operation,'snapshot':snap})!=row[2]:
            raise Rejected('plan_tampered')
        try:
            grant=trusted_json(Path(self.cfg['grants'])/(pid+'.json'),uid=self.owner_uid)
        except FileNotFoundError:
            raise Rejected('owner_authorization_required') from None
        if (set(grant)!={'plan_id','digest','expires_at'} or grant['plan_id']!=pid or
                grant['digest']!=row[2] or type(grant['expires_at']) is not int or
                not stamp<grant['expires_at']<=row[3]):
            raise Rejected('grant_invalid')
        if self.status_snapshot(operation)!=snap:
            raise Rejected('deployment_target_changed')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            changed=self.db.execute("UPDATE deploy_plans SET phase='claimed' "
                "WHERE id=? AND phase='prepared'",(pid,)).rowcount
            if changed!=1:
                raise Rejected('already_claimed')
            self.db.execute('INSERT INTO deploy_events VALUES(NULL,?,?,?)',
                            (pid,'claimed',stamp))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        try:
            answer=self.deploy_fn(operation,snap)
            phase='activated'
        except Exception:
            answer={'status':'failed_or_unknown','needs_operator_review':True}
            phase='failed_or_unknown'
        self.db.execute('UPDATE deploy_plans SET phase=?,result=? WHERE id=?',
                        (phase,compact(answer),pid))
        self.db.execute('INSERT INTO deploy_events VALUES(NULL,?,?,?)',
                        (pid,phase,int(self.now())))
        return {'plan_id':pid,'phase':phase,'result':answer}

    def activate(self,op,snapshot):
        meta=TARGETS[op['target']]
        root=Path(meta['root'])
        releases=root/'releases'
        dest=releases/op['commit']
        release=dest/meta['release_subdir'] if meta['release_subdir'] else dest
        if dest.exists() or dest.is_symlink():
            raise Rejected('release_exists_requires_review')
        old=Path(snapshot['previous_release'])
        temp=Path(tempfile.mkdtemp(prefix='.deploy-pending-',dir=releases))
        moved=False
        switched=False
        try:
            archive=Path(self.cfg['state_dir'])/'approved-sources'/(op['archive_sha256']+'.tar.gz')
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=op['archive_sha256']:
                raise Rejected('cached_archive_changed')
            extract_fixed_archive(archive,temp)
            run_checks(op['target'],temp)
            # Stop-leases and watchdogs are operational money controls.
            check_financial_guard_clear()
            os.replace(temp,dest)
            moved=True
            if self.status_snapshot(op)!=snapshot:
                raise Rejected('deployment_target_changed')
            swap_current(root,release)
            switched=True
            check_health(op['target'],restart=(op['target']=='hache-base'))
            return {'status':'activated','target':op['target'],
                    'release_commit':op['commit'],
                    'previous_release':str(old),
                    'verification':'services_active; no miner or Vast operations'}
        except Exception:
            if switched:
                try:
                    swap_current(root,old)
                    check_health(op['target'],restart=(op['target']=='hache-base'))
                except Exception:
                    pass
            raise
        finally:
            if temp.exists():
                shutil.rmtree(temp)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            creds=struct.unpack('3i',self.connection.getsockopt(
                socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if creds[1]!=self.server.allowed_uid:
                raise Rejected('peer_denied')
            self.server.gate.charge()
            raw=self.rfile.readline(8193)
            if not raw.endswith(b'\n') or len(raw)>8192:
                raise Rejected('invalid_request_size')
            response={'ok':True,'result':self.server.gate.handle(json.loads(raw))}
        except Rejected as e:
            response={'ok':False,'error':str(e)}
        except Exception:
            response={'ok':False,'error':'deployment_gate_unavailable'}
        self.wfile.write((compact(response)+'\n').encode())


def serve(config):
    cfg=trusted_json(config)
    if os.geteuid()!=0:
        raise RuntimeError('root_identity_required')
    if (os.getenv('LISTEN_FDS')!='1' or
            os.getenv('LISTEN_PID')!=str(os.getpid())):
        raise RuntimeError('socket_activation_required')
    gate=Gate(cfg)
    srv=socketserver.UnixStreamServer('',Handler,bind_and_activate=False)
    srv.socket.close()
    srv.socket=socket.socket(fileno=3)
    srv.allowed_uid=cfg['agent_uid']
    srv.gate=gate
    try:
        srv.serve_forever()
    finally:
        gate.close()
        srv.server_close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True)
    serve(p.parse_args().config)
