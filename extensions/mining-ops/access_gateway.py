#!/usr/bin/env python3
"""HACHE-MINER entrypoint: bounded diagnostics, provider reads, pinned SSH probes."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

DEFAULT_SOCKET = '/run/hache-mining-operator/agent.sock'
DEFAULT_PROFILES = '~/.config/hminer-access/profiles.json'
READ_FIELDS = {
    'vast.list': (),
    'vast.status': ('instance_id',),
    'salad.targets': (),
    'salad.groups': ('organization', 'project'),
    'salad.instances': ('organization', 'project', 'group'),
    'salad.instance': ('organization', 'project', 'group', 'instance_id'),
    'telemetry': (),
}
PROBES = {
    'gpu': 'nvidia-smi --query-gpu=index,name,temperature.gpu,power.draw,utilization.gpu --format=csv,noheader,nounits',
    'miner': 'pgrep -c -x SRBMiner-MULTI || true',
    'clock': 'date -u +%Y-%m-%dT%H:%M:%SZ',
}
IDENT = re.compile(r'[A-Za-z0-9_-]{1,120}\Z')
HOST = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,252}\Z')
VAST_ID = re.compile(r'[1-9][0-9]{0,14}\Z')


class AccessError(Exception):
    pass


def operation(action, args):
    if action not in READ_FIELDS:
        raise AccessError('read_action_not_allowed')
    fields = READ_FIELDS[action]
    if set(args) != set(fields):
        raise AccessError('read_fields_mismatch')
    for key, value in args.items():
        if not isinstance(value, str) or not IDENT.fullmatch(value):
            raise AccessError('invalid_target')
        if key == 'instance_id' and action.startswith('vast.') and not VAST_ID.fullmatch(value):
            raise AccessError('invalid_vast_id')
    return {'action': action, **args}


def broker(request, socket_path=DEFAULT_SOCKET):
    raw = json.dumps(request, separators=(',', ':')).encode() + b'\n'
    if len(raw) > 8192:
        raise AccessError('request_too_large')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(42)
            conn.connect(socket_path)
            conn.sendall(raw)
            data = conn.makefile('rb').readline(131073)
        if len(data) > 131072 or not data.endswith(b'\n'):
            raise AccessError('invalid_provider_response')
        result = json.loads(data)
    except (OSError, ValueError, TimeoutError):
        raise AccessError('provider_connection_unavailable') from None
    if not isinstance(result, dict) or result.get('ok') is not True:
        # No raw errors from providers, no credentials or tracebacks.
        allowed = {'target_not_enabled', 'resource_not_found', 'provider_unavailable',
                   'provider_forbidden', 'provider_rate_limited', 'request_rate_limited',
                   'unsupported_action_or_fields', 'target_state_changed'}
        reason = result.get('error') if isinstance(result, dict) else None
        raise AccessError(reason if reason in allowed else 'provider_query_failed')
    return result['result']


def safe_file(path, private=False):
    path = Path(path).expanduser()
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise AccessError('unsafe_access_file')
        if hasattr(os, 'getuid') and info.st_uid != os.getuid():
            raise AccessError('wrong_access_file_owner')
        if info.st_mode & (0o077 if private else 0o022):
            raise AccessError('unsafe_access_file_permissions')
    except OSError:
        raise AccessError('access_file_missing') from None
    return str(path)


def profile_from_file(path, name):
    filename = safe_file(path, private=True)
    with open(filename, encoding='utf-8') as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or set(value) != {'profiles'} or not isinstance(value['profiles'], dict):
        raise AccessError('invalid_profiles')
    target = value['profiles'].get(name)
    if not isinstance(target, dict):
        raise AccessError('profile_not_registered')
    return target


def verify_profile(p):
    base = {'provider', 'instance_id', 'host', 'port', 'user', 'identity_file', 'known_hosts'}
    salad = {'organization', 'project', 'group'}
    if not isinstance(p, dict) or p.get('provider') not in ('vast', 'salad'):
        raise AccessError('invalid_profile')
    if set(p) != base | (salad if p['provider'] == 'salad' else set()):
        raise AccessError('invalid_profile_fields')
    if not isinstance(p['host'], str) or not HOST.fullmatch(p['host']):
        raise AccessError('invalid_ssh_host')
    if p['user'] != 'root' or type(p['port']) is not int or not 1 <= p['port'] <= 65535:
        raise AccessError('invalid_ssh_endpoint')
    for key in ('instance_id',) + (('organization', 'project', 'group') if p['provider'] == 'salad' else ()):
        if not isinstance(p[key], str) or not IDENT.fullmatch(p[key]):
            raise AccessError('invalid_ssh_identity')
    if p['provider'] == 'vast' and not VAST_ID.fullmatch(p['instance_id']):
        raise AccessError('invalid_vast_id')
    if not isinstance(p['identity_file'], str) or not isinstance(p['known_hosts'], str):
        raise AccessError('invalid_ssh_files')
    return p


def require_running(p, send=broker):
    if p['provider'] == 'vast':
        result = send({'method': 'query', 'operation': operation(
            'vast.status', {'instance_id': p['instance_id']})})
        if str(result.get('id')) != p['instance_id'] or result.get('actual_status') != 'running':
            raise AccessError('vast_not_running_or_identity_changed')
    else:
        fields = {name: p[name] for name in ('organization', 'project', 'group', 'instance_id')}
        result = send({'method': 'query', 'operation': operation('salad.instance', fields)})
        if (str(result.get('instance_id') or result.get('id')) != p['instance_id'] or
                str(result.get('state', '')).lower() != 'running' or
                result.get('ready') is not True or result.get('started') is not True):
            raise AccessError('salad_not_ready_or_identity_changed')


def ssh_args(p, probe):
    verify_profile(p)
    if probe not in PROBES:
        raise AccessError('probe_not_allowed')
    key = safe_file(p['identity_file'], private=True)
    hosts = safe_file(p['known_hosts'])
    return ['ssh', '-F', '/dev/null', '-T', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'ClearAllForwardings=yes', '-o', 'ForwardAgent=no',
            '-o', 'PermitLocalCommand=no', '-o', 'ConnectTimeout=6',
            '-o', 'ConnectionAttempts=1', '-o', 'LogLevel=ERROR',
            '-o', 'UserKnownHostsFile=' + hosts, '-i', key, '-p', str(p['port']),
            '--', p['user'] + '@' + p['host'], PROBES[probe]]


def remote_probe(p, probe, send=broker, runner=subprocess.run):
    # API confirmation first. SSH is a read-only fixed diagnostic, never a shell bridge.
    verify_profile(p)
    require_running(p, send)
    command = ssh_args(p, probe)
    try:
        result = runner(command, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise AccessError('ssh_unavailable') from None
    if result.returncode:
        raise AccessError('ssh_probe_failed')
    if len(result.stdout) > 16384:
        raise AccessError('ssh_response_too_large')
    return {'provider': p['provider'], 'instance_id': p['instance_id'],
            'probe': probe, 'output': result.stdout.strip()}


def local_status(path=None, runner=subprocess.run):
    path = str(Path(path or Path(__file__).with_name('mining_status.py')))
    try:
        r = runner([sys.executable, path], capture_output=True, text=True, timeout=60)
        value = json.loads(r.stdout)
        if not isinstance(value, dict) or value.get('status') not in ('ok', 'attention', 'unknown'):
            raise ValueError('invalid result')
        return value
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise AccessError('local_diagnostics_unavailable') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', default=DEFAULT_SOCKET)
    sub = parser.add_subparsers(dest='verb', required=True)
    sub.add_parser('status')
    q = sub.add_parser('query')
    q.add_argument('action', choices=sorted(READ_FIELDS))
    for field in ('instance_id', 'organization', 'project', 'group'):
        q.add_argument('--' + field.replace('_', '-'))
    p = sub.add_parser('probe')
    p.add_argument('--profiles', default=DEFAULT_PROFILES)
    p.add_argument('--profile', required=True)
    p.add_argument('--test', choices=sorted(PROBES), required=True)
    args = parser.parse_args(argv)
    try:
        if args.verb == 'status':
            result = local_status()
        elif args.verb == 'query':
            provided = {field: getattr(args, field) for field in
                        ('instance_id', 'organization', 'project', 'group')
                        if getattr(args, field) is not None}
            result = broker({'method': 'query', 'operation': operation(args.action, provided)},
                            socket_path=args.socket)
        else:
            p = profile_from_file(args.profiles, args.profile)
            result = remote_probe(p, args.test,
                send=lambda request: broker(request, socket_path=args.socket))
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False, indent=2))
        return 0
    except (AccessError, ValueError, TypeError, json.JSONDecodeError) as err:
        code = str(err) if isinstance(err, AccessError) else 'invalid_access_configuration'
        print(json.dumps({'ok': False, 'error': code}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
