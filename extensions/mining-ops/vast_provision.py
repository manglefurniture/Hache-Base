#!/usr/bin/env python3
"""VAST-003 fixed SSH deployment channel: VPS -> one authorised running Vast instance.

No Vast rental, start, stop, shell API, HMAC transfer, or miner start.
"""
import argparse
import hashlib
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
REMOTE_BASE = '/root/hache-vast/releases'


class DeployError(Exception):
    pass


def validate_archive(filename, expected_hash):
    file = Path(gateway.safe_file(filename, private=True))
    if not SHA.fullmatch(expected_hash):
        raise DeployError('invalid_bundle_checksum')
    if file.stat().st_size > MAX_BUNDLE:
        raise DeployError('bundle_too_large')
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise DeployError('bundle_sha256_mismatch')
    import io
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        entries = archive.getmembers()
        if (len(entries)!=len(FILES) or
                {e.name for e in entries} != FILES or
                any(not e.isfile() or e.size<=0 or e.size>300000
                    for e in entries)):
            raise DeployError('unexpected_bundle_contents')
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
    parser.add_argument('--bundle-sha256')
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
        bundle=None
        if args.stage:
            if not args.bundle or not args.bundle_sha256:
                raise DeployError('bundle_and_sha256_required')
            bundle=validate_archive(args.bundle,args.bundle_sha256)
        if not args.stage and not args.apply:
            print(json.dumps({'ok':True,'status':'offline_plan_only',
                             'instance_id':args.instance_id,
                             'release_commit':args.release_commit}))
            return 0
        verify_target(p,args.instance_id)
        result=run_remote(p,'stage' if args.stage else 'apply',
                          args.release_commit,bundle=bundle)
        print(json.dumps({'ok':True,'result':result}))
        return 0
    except (gateway.AccessError,DeployError,OSError,ValueError,tarfile.TarError):
        print(json.dumps({'ok':False,'error':'vast_provision_not_ready'}))
        return 2


if __name__=='__main__':
    sys.exit(main())
