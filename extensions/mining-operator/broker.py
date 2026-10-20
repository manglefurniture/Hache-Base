#!/usr/bin/env python3
"""Local, peer-authenticated mining command broker with root-issued one-use grants."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import socketserver
import sqlite3
import stat
import struct
import subprocess
import time

from vast_start_guard import arm as arm_financial_lease, install_tables as install_lease_tables

READS = {'vast.list', 'vast.status', 'vast.inspect', 'vast.search', 'vast.analyze', 'vast.rent.quote', 'vast.rent.reconcile', 'salad.targets',
         'salad.groups', 'salad.instances', 'salad.instance', 'telemetry'}
WRITES = {'vast.stop', 'vast.start', 'vast.register', 'vast.provision', 'salad.stop', 'salad.reallocate'}
FIELDS = {
    'vast.list': set(), 'vast.status': {'instance_id'}, 'vast.inspect': {'instance_id'},
    'vast.search': {'gpu_name', 'gpu_count', 'max_hourly_usd'},
    'vast.analyze': {'gpu_name', 'gpu_count', 'max_hourly_usd', 'assumed_prl_per_day'},
    'vast.rent.quote': {'offer_id', 'machine_id', 'host_id', 'gpu_name', 'gpu_count', 'max_hourly_usd', 'max_total_usd', 'max_minutes'},
    'vast.rent.reconcile': {'machine_id', 'host_id', 'gpu_name', 'gpu_count', 'max_hourly_usd'},
    'salad.targets': set(), 'salad.groups': {'organization', 'project'},
    'salad.instances': {'organization', 'project', 'group'},
    'salad.instance': {'organization', 'project', 'group', 'instance_id'},
    'telemetry': set(), 'vast.stop': {'instance_id'},
    'vast.start': {'instance_id', 'max_hourly_usd', 'max_total_usd', 'max_minutes'},
    'vast.register': {'instance_id'},
    'vast.provision': {'instance_id', 'release_commit', 'step'},
    'salad.stop': {'organization', 'project', 'group'},
    'salad.reallocate': {'organization', 'project', 'group', 'instance_id'},
}


class Rejected(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_operation(value):
    if not isinstance(value, dict) or not isinstance(value.get('action'), str):
        raise Rejected('invalid_operation')
    action = value['action']
    if action not in FIELDS or set(value) != FIELDS[action] | {'action'}:
        raise Rejected('unsupported_action_or_fields')
    for name, item in value.items():
        if name == 'action':
            continue
        if name == 'step':
            if action!='vast.provision' or item not in ('stage','configure','apply'):
                raise Rejected('invalid_provision_step')
        elif name == 'release_commit':
            if action!='vast.provision' or type(item) is not str or not re.fullmatch(r'[a-f0-9]{40}',item):
                raise Rejected('invalid_release_commit')
        elif name == 'max_minutes':
            if type(item) is not int or not 1 <= item <= 1440:
                raise Rejected('invalid_duration')
        elif name == 'assumed_prl_per_day':
            if type(item) not in (int, float) or not math.isfinite(item) or not 0 <= item <= 100000:
                raise Rejected('invalid_yield_assumption')
        elif name in ('offer_id', 'machine_id', 'host_id'):
            if type(item) is not int or not 1 <= item <= 999999999999999:
                raise Rejected('invalid_offer_identity')
        elif name == 'gpu_count':
            if type(item) is not int or not 1 <= item <= 16:
                raise Rejected('invalid_gpu_count')
        elif name in ('max_hourly_usd', 'max_total_usd'):
            ceiling = 100 if name == 'max_hourly_usd' else 1000
            if (type(item) not in (int, float) or not math.isfinite(item)
                    or not 0 < item <= ceiling):
                raise Rejected('invalid_price_limit')
        elif name == 'gpu_name':
            if not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9 _-]{1,80}', item):
                raise Rejected('invalid_gpu_name')
        elif name == 'instance_id' and action.startswith('vast.'):
            if not isinstance(item, str) or not re.fullmatch(r'[1-9][0-9]{0,14}', item):
                raise Rejected('invalid_instance_id')
        elif not isinstance(item, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,120}', item):
            raise Rejected('invalid_target')
    return value


def protected_json(path, owner_uid=0, private_directory=False):
    path = Path(path)
    if private_directory:
        parent = path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != owner_uid or parent.st_mode & 0o022:
            raise Rejected('untrusted_grant_directory')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or info.st_mode & 0o022 or info.st_nlink != 1:
            raise Rejected('untrusted_configuration')
        content = stream.read(16385)
        if len(content) > 16384:
            raise Rejected('configuration_too_large')
        return json.loads(content)


def safe_helper(command, mode, operation, snapshot=None, *, timeout=35):
    request = {'mode': mode, 'operation': operation}
    if snapshot is not None:
        request['snapshot'] = snapshot
    result = subprocess.run(command, input=canonical(request), capture_output=True,
                            text=True, timeout=timeout)
    # Helper returns only sanitized projections, never stderr or provider bodies.
    if len(result.stdout) > 131072:
        raise Rejected('provider_response_too_large')
    try:
        answer = json.loads(result.stdout)
    except ValueError:
        raise Rejected('provider_unavailable') from None
    if result.returncode or not isinstance(answer, dict) or answer.get('ok') is not True:
        error = answer.get('error') if isinstance(answer, dict) else None
        allowed = {'credential_unavailable', 'provider_forbidden', 'resource_not_found',
                   'provider_rate_limited', 'provider_unavailable', 'target_not_enabled',
                   'target_state_changed', 'cooldown_active', 'target_not_ready',
                   'price_limit_exceeded', 'estimated_budget_exceeded',
                   'unsupported_action', 'provider_outcome_unknown'}
        raise Rejected(error if error in allowed else 'provider_unavailable')
    return answer.get('result', {})


class Broker:
    def __init__(self, database, grants, helper, *, grant_owner=0, now=time.time):
        self.db = sqlite3.connect(database, isolation_level=None, timeout=5)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS plans(
            id TEXT PRIMARY KEY, operation TEXT NOT NULL, snapshot TEXT NOT NULL,
            digest TEXT NOT NULL, expires INTEGER NOT NULL, phase TEXT NOT NULL,
            result TEXT);
          CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY, plan_id TEXT, phase TEXT NOT NULL, at INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS requests(at INTEGER NOT NULL);
        ''')
        install_lease_tables(self.db)
        self.grants, self.helper = Path(grants), helper
        self.grant_owner, self.now = grant_owner, now

    def close(self):
        self.db.close()

    def charge(self):
        now = int(self.now())
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('DELETE FROM requests WHERE at<?', (now-86400,))
            count = self.db.execute('SELECT COUNT(*) FROM requests WHERE at>?', (now-3600,)).fetchone()[0]
            if count >= 120:
                raise Rejected('request_rate_limited')
            self.db.execute('INSERT INTO requests VALUES(?)', (now,))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def handle(self, request):
        if not isinstance(request, dict) or not isinstance(request.get('method'), str):
            raise Rejected('invalid_request')
        method = request['method']
        if method == 'capabilities' and set(request) == {'method'}:
            return {'reads': sorted(READS), 'writes_with_root_grant': sorted(WRITES),
                    'vast.provision': 'requires active lease, pinned forced-command SSH and root one-use grant',
                    'rent_restart_destroy_ssh': 'not_enabled',
                    'vast.start': 'requires specific root grant, live financial supervisor, price and duration caps',
                    'authorization': 'exact plan, root-owned grant, one use, expires within 5 minutes'}
        if method == 'query' and set(request) == {'method', 'operation'}:
            operation = validate_operation(request['operation'])
            if operation['action'] not in READS:
                raise Rejected('query_cannot_mutate')
            return self.helper('query', operation)
        if method == 'prepare' and set(request) == {'method', 'operation'}:
            operation = validate_operation(request['operation'])
            if operation['action'] not in WRITES:
                raise Rejected('unsupported_mutation')
            snapshot = self.helper('prepare', operation)
            stamp = int(self.now())
            plan = secrets.token_hex(16)
            bound = {'operation': operation, 'snapshot': snapshot}
            plan_digest = digest(bound)
            self.db.execute('DELETE FROM plans WHERE expires<? AND phase=?', (stamp-86400, 'prepared'))
            self.db.execute('INSERT INTO plans VALUES(?,?,?,?,?,?,NULL)',
                            (plan, canonical(operation), canonical(snapshot), plan_digest, stamp+300, 'prepared'))
            self.db.execute('INSERT INTO events(plan_id,phase,at) VALUES(?,?,?)', (plan, 'prepared', stamp))
            return {'plan_id': plan, 'digest': plan_digest, 'expires_at': stamp+300,
                    'operation': operation, 'snapshot': snapshot, 'authorization_required': True}
        if method in {'execute', 'status'} and set(request) == {'method', 'plan_id'}:
            plan = request['plan_id']
            if not isinstance(plan, str) or not re.fullmatch(r'[a-f0-9]{32}', plan):
                raise Rejected('invalid_plan_id')
            row = self.db.execute('SELECT operation,snapshot,digest,expires,phase,result FROM plans WHERE id=?', (plan,)).fetchone()
            if not row:
                raise Rejected('plan_not_found')
            if method == 'status' or row[4] != 'prepared':
                return {'plan_id': plan, 'phase': row[4], 'result': json.loads(row[5]) if row[5] else None}
            stamp = int(self.now())
            if row[3] <= stamp:
                raise Rejected('plan_expired')
            if digest({'operation': json.loads(row[0]), 'snapshot': json.loads(row[1])}) != row[2]:
                raise Rejected('plan_content_changed')
            try:
                grant = protected_json(self.grants / (plan+'.json'), self.grant_owner, True)
            except FileNotFoundError:
                raise Rejected('human_instruction_authorization_required') from None
            if (set(grant) != {'plan_id', 'digest', 'expires_at'} or grant['plan_id'] != plan
                    or grant['digest'] != row[2] or type(grant['expires_at']) is not int
                    or not stamp < grant['expires_at'] <= row[3]):
                raise Rejected('grant_mismatch_or_expired')
            # Consume durably BEFORE the provider call. Never resend an unknown outcome.
            self.db.execute('BEGIN IMMEDIATE')
            changed = self.db.execute("UPDATE plans SET phase='claimed' WHERE id=? AND phase='prepared'", (plan,)).rowcount
            if changed != 1:
                self.db.rollback()
                raise Rejected('plan_already_claimed')
            self.db.execute('INSERT INTO events(plan_id,phase,at) VALUES(?,?,?)', (plan, 'claimed', stamp))
            self.db.commit()
            try:
                op = json.loads(row[0])
                if op['action'] == 'vast.start':
                    # Durable, timer-monitored deadline is installed BEFORE contacting Vast.
                    # Unknown/failed provider responses do not cancel the stop obligation.
                    lease = arm_financial_lease(self.db, plan, op, json.loads(row[1]),
                                               now=int(self.now()))
                response = self.helper('execute', op, json.loads(row[1]))
                if op['action'] == 'vast.start':
                    response = dict(response, financial_lease=lease)
                phase = 'submitted'  # API acceptance is not completed provider state.
            except Exception:
                response = {'error': 'provider_outcome_unknown', 'retry': False}
                phase = 'failed_or_unknown'
            self.db.execute('UPDATE plans SET phase=?,result=? WHERE id=?', (phase, canonical(response), plan))
            self.db.execute('INSERT INTO events(plan_id,phase,at) VALUES(?,?,?)', (plan, phase, int(self.now())))
            return {'plan_id': plan, 'phase': phase, 'result': response}
        raise Rejected('invalid_request_fields')


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(8)
        try:
            uid = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            if uid != self.server.allowed_uid:
                raise Rejected('peer_not_authorized')
            raw = self.rfile.readline(8193)
            if len(raw) > 8192 or not raw.endswith(b'\n'):
                raise Rejected('invalid_request_size')
            request = json.loads(raw)
            self.server.broker.charge()
            answer = {'ok': True, 'result': self.server.broker.handle(request)}
        except Rejected as error:
            answer = {'ok': False, 'error': str(error)}
        except Exception:
            answer = {'ok': False, 'error': 'operator_unavailable'}
        self.wfile.write((canonical(answer)+'\n').encode())


def serve(config):
    cfg = protected_json(config)
    if os.getenv('LISTEN_FDS') != '1' or os.getenv('LISTEN_PID') != str(os.getpid()):
        raise RuntimeError('systemd socket activation required')
    def helper(mode, operation, snapshot=None):
        if operation['action']=='vast.provision':
            return safe_helper(
                ['/usr/bin/python3',
                 '/opt/hache-mining-operator/current/vast_provision_helper.py'],
                mode, operation, snapshot, timeout=290)
        return safe_helper(cfg['helper_command'], mode, operation, snapshot)
    broker = Broker(cfg['database'], cfg['grants'], helper)
    server = socketserver.UnixStreamServer('', Handler, bind_and_activate=False)
    server.socket.close()
    server.socket = socket.socket(fileno=3)
    server.allowed_uid, server.broker = cfg['agent_uid'], broker
    try:
        server.serve_forever()
    finally:
        server.server_close()
        broker.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    serve(parser.parse_args().config)
