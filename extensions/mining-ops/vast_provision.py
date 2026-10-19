#!/usr/bin/env python3
"""VAST-003 fixed SSH deployment channel: VPS -> one authorised running Vast instance.

No Vast rental, start, stop, shell API, HMAC transfer, or miner start.
"""
import argparse
import hashlib
import os
import pwd
import stat
import time
import json
from pathlib import Path
import re
import shlex
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
CLAIMS = '/var/lib/hache-mining-operator/deploy-claims'
REMOTE_BASE = '/root/hache-vast/releases'


class DeployError(Exception):
    pass


def git_blob(data):
    """Compare bytes with the precise Git blob IDs trusted by root."""
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + bytes([0]) + data).hexdigest()


def load_approval(path=APPROVAL, now=None):
    """Root-owned read-only metadata (e.g. 0644), never writable by GPT."""
    now = int(time.time() if now is None else now)
    file=Path(path)
    try:
        info=file.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                info.st_nlink != 1 or info.st_mode & 0o022):
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


def require_executor(executor_uid=None):
    """The provisioning channel must be called from a trusted service UID."""
    if executor_uid is None:
        executor_uid=pwd.getpwnam('hache-miner').pw_uid
    if os.geteuid()!=executor_uid:
        raise DeployError('trusted_executor_required')


def claim_approval(approval, *, directory=CLAIMS, executor_uid=None):
    """Consume grant durably BEFORE SSH. Only private trusted hache-miner can claim.

    The directory is not writable or traversable by gpt-agent. No agent-owned
    'used' marker can be deleted to replay. Any unknown outcome burns the grant.
    """
    require_executor(executor_uid)
    dirpath=Path(directory)
    try:
        info=dirpath.lstat()
    except OSError:
        raise DeployError('private_claim_store_missing') from None
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=executor_uid or
            stat.S_IMODE(info.st_mode)!=0o700):
        raise DeployError('unsafe_claim_store')
    digest=hashlib.sha256(json.dumps(approval,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    marker=dirpath/(digest+'.claimed')
    try:
        fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   getattr(os,'O_NOFOLLOW',0),0o600)
    except FileExistsError:
        raise DeployError('approval_already_consumed') from None
    except OSError:
        raise DeployError('claim_store_unavailable') from None
    with os.fdopen(fd,'w') as stream:
        stream.write(json.dumps({'commit':approval['commit'],
              'instance_id':approval['instance_id'],
              'action':approval['approved_action']})+'\\n')
        stream.flush()
        os.fsync(stream.fileno())
    return digest


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


REMOTE_STAGE_PY = r"""
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile

dest = Path(sys.argv[1])
expected = json.loads(sys.argv[2])
expected_archive = sys.argv[3]
binding = json.loads(sys.argv[4])
conf = Path(sys.argv[5])
root = dest.parent
if root.is_symlink() or root.parent.is_symlink():
    raise SystemExit('unsafe staging directory')
root.mkdir(mode=0o700, parents=True, exist_ok=True)
if root.is_symlink() or not root.is_dir():
    raise SystemExit('unsafe staging directory')
lock_fd = os.open(root/'.deploy.lock', os.O_RDWR | os.O_CREAT |
                  getattr(os, 'O_NOFOLLOW', 0), 0o600)
with os.fdopen(lock_fd, 'rb') as lock:
    info = os.fstat(lock.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise SystemExit('untrusted staging lock')
    fcntl.flock(lock, fcntl.LOCK_EX)
    archive = sys.stdin.buffer.read(2097153)
    if len(archive) > 2097152 or hashlib.sha256(archive).hexdigest() != expected_archive:
        raise SystemExit('wrong archive')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        members = tar.getmembers()
        if (len(members) != len(expected) or
                {m.name for m in members} != set(expected) or
                any(not m.isfile() or m.size < 1 or m.size > 300000
                    for m in members)):
            raise SystemExit('unapproved tar')
        blobs = {}
        for member in members:
            data = tar.extractfile(member).read()
            digest = hashlib.sha1(b'blob ' + str(len(data)).encode() +
                                  bytes([0]) + data).hexdigest()
            if digest != expected[member.name]:
                raise SystemExit('unapproved Git blob')
            blobs[member.name] = data
    def inspect_existing(where):
        if where.is_symlink() or not where.is_dir():
            raise SystemExit('staged release is unsafe')
        for name, data in blobs.items():
            item = where/name
            if item.is_symlink() or not item.is_file() or item.read_bytes() != data:
                raise SystemExit('staged release differs')
    if not dest.exists() and not dest.is_symlink():
        temporary = Path(tempfile.mkdtemp(prefix='.stage-', dir=root))
        try:
            for name, data in blobs.items():
                item = temporary/name
                fd = os.open(item, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                             getattr(os, 'O_NOFOLLOW', 0), 0o700)
                with os.fdopen(fd, 'wb') as out:
                    out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
            inspect_existing(temporary)
            # Under the filesystem lock, renaming a validated directory is atomic.
            os.rename(temporary, dest)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    inspect_existing(dest)
    if conf.is_symlink():
        raise SystemExit('unsafe configuration directory')
    conf.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = conf/'host-binding.json'
    content = json.dumps(binding, sort_keys=True, separators=(',', ':')).encode() + bytes([10])
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or target.read_bytes()!=content:
            raise SystemExit('conflicting host binding')
        info = target.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise SystemExit('unsafe host binding')
    else:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                     getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
"""

def remote_integrity_command(approval, dest):
    """Check bytes on the GPU before executing even if a staged file changed."""
    verifier = (
        'import hashlib,json,pathlib,sys; '
        'root=pathlib.Path(sys.argv[1]); expected=json.loads(sys.argv[2]); '
        'assert not root.is_symlink() and root.is_dir(); '
        'actual={}; '
        '[(lambda p,name: actual.__setitem__(name, '
        'hashlib.sha1(b"blob "+str(len(p.read_bytes())).encode()+bytes([0])+'
        'p.read_bytes()).hexdigest()) if p.is_file() and not p.is_symlink() '
        'else sys.exit(5))(root/name,name) for name in expected]; '
        'assert actual==expected'
    )
    return ('python3 -c '+shlex.quote(verifier)+' '+
            shlex.quote(dest)+' '+
            shlex.quote(json.dumps(approval['files'],sort_keys=True,separators=(',',':'))))


def run_remote(p, action, commit, *, bundle=None, approval=None,
               runner=subprocess.run):
    require_executor()
    if not COMMIT.fullmatch(commit):
        raise DeployError('invalid_release_commit')
    if approval is None:
        raise DeployError('root_approval_required')
    check_approval(approval,p,action,commit)
    dest = REMOTE_BASE+'/'+commit
    integrity=remote_integrity_command(approval,dest)
    # Commands are entirely generated from static strings and pinned SHA,
    # never from user-provided arbitrary commands or filenames.
    if action=='stage':
        if bundle is None:
            raise DeployError('bundle_required')
        host_binding = {
            'instance_id': p['instance_id'],
            'machine_id': str(p['machine_id']),
            'host_id': str(p['host_id']),
            'gpu_count': p['gpu_count'],
            'ssh_host': p['host'], 'ssh_port': p['port'],
        }
        # Python on the GPU verifies archive, exact Git bytes and host binding.
        # A private flock serializes staging; a temporary directory is renamed
        # only after validation. Incomplete transfers clean up automatically.
        command = (
            'python3 -c ' + shlex.quote(REMOTE_STAGE_PY) + ' ' +
            shlex.quote(dest) + ' ' +
            shlex.quote(json.dumps(approval['files'], sort_keys=True)) + ' ' +
            shlex.quote(approval['archive_sha256']) + ' ' +
            shlex.quote(json.dumps(host_binding, sort_keys=True)) + ' ' +
            shlex.quote('/etc/hache-vast')
        )
        data = bundle
    elif action=='apply':
        command=(
            'set -eu; '
            'test ! -L '+dest+' && '
            'test -f '+dest+'/vast-auto-prepare.py && ' + integrity + ' && '
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
        claim_approval(approval)
        result=run_remote(p,action,args.release_commit,
                          bundle=bundle,approval=approval)
        print(json.dumps({'ok':True,'result':result}))
        return 0
    except (gateway.AccessError,DeployError,OSError,ValueError,tarfile.TarError):
        print(json.dumps({'ok':False,'error':'vast_provision_not_ready'}))
        return 2


if __name__=='__main__':
    sys.exit(main())
