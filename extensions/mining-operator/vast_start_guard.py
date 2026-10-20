#!/usr/bin/env python3
"""Durable, independent financial lease for explicitly approved Vast starts.

The root-issued broker grant authorises the start; the independent timer enforces
the expiration even when the agent, chat, or command broker is offline.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

TIMER = 'hache-mining-operator-vast-lease.timer'
HEARTBEAT_MAX_AGE = 90

SCHEMA = """
CREATE TABLE IF NOT EXISTS vast_leases(
  plan_id TEXT PRIMARY KEY, instance_id TEXT NOT NULL,
  operation TEXT NOT NULL, snapshot TEXT NOT NULL,
  created INTEGER NOT NULL, deadline INTEGER NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('armed','closed')),
  last_attempt INTEGER, last_outcome TEXT
);
CREATE INDEX IF NOT EXISTS vast_leases_active ON vast_leases(phase,deadline);
CREATE TABLE IF NOT EXISTS lease_guard_heartbeat(
  id INTEGER PRIMARY KEY CHECK(id=1), completed_at INTEGER NOT NULL
);
"""


class LeaseError(Exception):
    pass


def install_tables(connection):
    connection.executescript(SCHEMA)


def timer_active(runner=subprocess.run):
    try:
        result = runner(['systemctl', 'is-active', '--quiet', TIMER],
                        timeout=3, capture_output=True)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def arm(connection, plan_id, operation, snapshot, now=None, timer_check=timer_active):
    now = int(time.time() if now is None else now)
    if operation.get('action') != 'vast.start':
        raise LeaseError('not_a_guarded_start')
    duration = operation['max_minutes']
    identity = operation['instance_id']
    if type(duration) is not int or not 1 <= duration <= 1440:
        raise LeaseError('invalid_duration')
    if not timer_check():
        raise LeaseError('independent_stop_timer_inactive')
    # Transaction protects against duplicate leases across simultaneous processes.
    connection.execute('BEGIN IMMEDIATE')
    try:
        hb = connection.execute('SELECT completed_at FROM lease_guard_heartbeat WHERE id=1').fetchone()
        if not hb or not 0 <= now - hb[0] <= HEARTBEAT_MAX_AGE:
            raise LeaseError('independent_stop_supervisor_unhealthy')
        conflict = connection.execute(
            "SELECT 1 FROM vast_leases WHERE phase='armed' LIMIT 1").fetchone()
        # Only one financial lease at a time until more robust multi-host operation is certified.
        if conflict:
            raise LeaseError('active_financial_lease')
        connection.execute(
            'INSERT INTO vast_leases(plan_id,instance_id,operation,snapshot,created,deadline,phase) '
            "VALUES(?,?,?,?,?,?,'armed')",
            (plan_id, identity, canonical(operation), canonical(snapshot), now, now+duration*60))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {'deadline_unix': now+duration*60, 'max_minutes': duration}



def arm_rental(connection, plan_id, operation, snapshot, now=None, timer_check=timer_active):
    """Arm a durable cutoff BEFORE submitting an approved new rental.

    This helper does not rent; it reserves a single active financial obligation.
    An unknown provider result must leave the obligation armed until reconciled.
    """
    now = int(time.time() if now is None else now)
    if operation.get('action') != 'vast.rent':
        raise LeaseError('not_a_guarded_rental')
    duration = operation.get('max_minutes')
    if type(duration) is not int or not 1 <= duration <= 1440:
        raise LeaseError('invalid_duration')
    hourly = operation.get('max_hourly_usd')
    total = operation.get('max_total_usd')
    if (type(hourly) not in (int,float) or type(total) not in (int,float)
            or not (0 < hourly <= 100 and 0 < total <= 1000)
            or hourly * duration / 60 > total):
        raise LeaseError('budget_exceeded')
    if not timer_check():
        raise LeaseError('independent_stop_timer_inactive')
    connection.execute('BEGIN IMMEDIATE')
    try:
        hb = connection.execute('SELECT completed_at FROM lease_guard_heartbeat WHERE id=1').fetchone()
        if not hb or not 0 <= now - hb[0] <= HEARTBEAT_MAX_AGE:
            raise LeaseError('independent_stop_supervisor_unhealthy')
        if connection.execute("SELECT 1 FROM vast_leases WHERE phase='armed' LIMIT 1").fetchone():
            raise LeaseError('active_financial_lease')
        # Rental offer IDs are NOT instance IDs. The guard must reconcile the
        # newly assigned instance before it can issue a provider stop.
        connection.execute(
            'INSERT INTO vast_leases(plan_id,instance_id,operation,snapshot,created,deadline,phase,last_outcome) '
            "VALUES(?,?,?,?,?,?,'armed','rental_identity_pending')",
            (plan_id, 'pending:'+str(operation['offer_id']), canonical(operation),
             canonical(snapshot), now, now+duration*60))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {'deadline_unix': now+duration*60, 'identity_pending': True}

def check_expired(connection, helper, now=None):
    now = int(time.time() if now is None else now)
    # The guard does NOT start, create, destroy, or restart instances.
    rows = connection.execute(
        "SELECT plan_id,operation,snapshot FROM vast_leases "
        "WHERE phase='armed' AND deadline<=? ORDER BY deadline,created LIMIT 50",
        (now,)).fetchall()
    failed = 0
    stopped = 0
    pending = 0
    for plan_id, op_json, snap_json in rows:
        try:
            op = json.loads(op_json)
            snap = json.loads(snap_json)
            if op.get('action') == 'vast.rent':
                # Never pass an offer ID as an instance ID to the stop helper.
                # Fail closed until a verified provider instance is bound.
                raise LeaseError('rental_identity_reconciliation_required')
            response = helper('guard_stop', op, snap)
            if response.get('status') == 'already_stopped':
                connection.execute(
                    "UPDATE vast_leases SET phase='closed',last_attempt=?,last_outcome='already_stopped' "
                    "WHERE plan_id=? AND phase='armed'", (now, plan_id))
                stopped += 1
            elif response.get('status') == 'accepted':
                # Provider acknowledgement is not proof the instance has stopped.
                connection.execute(
                    "UPDATE vast_leases SET last_attempt=?,last_outcome='stop_requested' "
                    "WHERE plan_id=? AND phase='armed'", (now, plan_id))
                pending += 1
            else:
                raise LeaseError('unknown_stop_outcome')
        except Exception:
            failed += 1
            connection.execute(
                "UPDATE vast_leases SET last_attempt=?,last_outcome='verification_required' "
                "WHERE plan_id=? AND phase='armed'", (now, plan_id))
    connection.commit()
    # A failed financial stop suppresses healthy heartbeat: no further leases.
    if failed:
        raise LeaseError('financial_stop_unconfirmed')
    connection.execute(
        'INSERT INTO lease_guard_heartbeat(id,completed_at) VALUES(1,?) '
        'ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at', (now,))
    connection.commit()
    return {'closed': stopped, 'stop_requested': pending,
            'active': connection.execute(
                "SELECT COUNT(*) FROM vast_leases WHERE phase='armed'").fetchone()[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('do not run lease supervisor as root')
    from broker import protected_json, safe_helper
    cfg = protected_json(args.config)
    required = {'database', 'helper_command', 'grants', 'agent_uid'}
    if not required.issubset(cfg):
        parser.error('invalid broker configuration')
    db = sqlite3.connect(cfg['database'], timeout=5, isolation_level=None)
    try:
        install_tables(db)
        answer = check_expired(
            db, lambda mode, op, snap: safe_helper(cfg['helper_command'], mode, op, snap))
        print(canonical({'ok': True, 'result': answer}))
    except Exception:
        # Never expose provider responses, credentials, raw DB, or stack traces.
        print(canonical({'ok': False, 'error': 'lease_supervisor_failed'}))
        return 1
    finally:
        db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
