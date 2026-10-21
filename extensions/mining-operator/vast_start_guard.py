#!/usr/bin/env python3
"""Durable, independent financial lease for explicitly approved Vast starts.

The root-issued broker grant authorises the start; the independent timer enforces
the expiration even when the agent, chat, or command broker is offline.
"""
import argparse
import json
import math
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
RENTAL_RECONCILIATION_GRACE_SECONDS = 300

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



def capture_rental_baseline(connection, plan_id, instance_rows, now=None):
    """Persist an independently fetched complete inventory before renting.

    A caller-supplied baseline is never authoritative. Store it in the lease
    snapshot, bound to the approved plan, exactly once.
    """
    now = int(time.time() if now is None else now)
    if type(instance_rows) is not list or len(instance_rows)>1000:
        raise LeaseError('invalid_rental_inventory')
    ids=[]
    for item in instance_rows:
        if type(item) is not dict or type(item.get('id')) is not int or item['id']<=0:
            raise LeaseError('invalid_rental_inventory')
        ids.append(item['id'])
    if len(set(ids)) != len(ids):
        raise LeaseError('duplicate_rental_inventory')
    connection.execute('BEGIN IMMEDIATE')
    try:
        row=connection.execute(
            "SELECT instance_id,operation,snapshot,deadline FROM vast_leases WHERE plan_id=? AND phase='armed'",
            (plan_id,)).fetchone()
        if not row:
            raise LeaseError('rental_lease_not_armed')
        pending, op_json, snap_json, deadline=row
        if json.loads(op_json).get('action')!='vast.rent' or not pending.startswith('pending:'):
            raise LeaseError('not_pending_rental')
        if now>deadline:
            raise LeaseError('rental_lease_expired')
        snapshot=json.loads(snap_json)
        if 'baseline_instance_ids' in snapshot:
            if snapshot['baseline_instance_ids']!=sorted(ids):
                raise LeaseError('rental_baseline_conflict')
            connection.commit()
            return {'baseline_instance_ids':sorted(ids),'already_captured':True}
        snapshot['baseline_instance_ids']=sorted(ids)
        snapshot['baseline_captured_at']=now
        connection.execute(
            "UPDATE vast_leases SET snapshot=?,last_outcome='rental_baseline_captured' "
            "WHERE plan_id=? AND phase='armed'",
            (canonical(snapshot),plan_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {'baseline_instance_ids':sorted(ids),'already_captured':False}

def bind_rental_instance(connection, plan_id, instance, now=None):
    """Bind a single provider-confirmed instance to an already armed rental.

    Caller MUST supply independently fetched provider inventory, not a response
    assembled from the original rental request. Ambiguity leaves lease armed.
    """
    now = int(time.time() if now is None else now)
    if not isinstance(instance, dict):
        raise LeaseError('invalid_provider_instance')
    instance_id = instance.get('id')
    if type(instance_id) is not int or instance_id <= 0:
        raise LeaseError('invalid_provider_instance')
    connection.execute('BEGIN IMMEDIATE')
    try:
        row = connection.execute(
            'SELECT instance_id,operation,snapshot,deadline FROM vast_leases '
            "WHERE plan_id=? AND phase='armed'", (plan_id,)).fetchone()
        if not row:
            raise LeaseError('rental_lease_not_armed')
        existing, op_json, snap_json, deadline = row
        op = json.loads(op_json)
        original_snapshot=json.loads(snap_json)
        if 'baseline_instance_ids' not in original_snapshot:
            raise LeaseError('rental_baseline_missing')
        if instance_id in original_snapshot['baseline_instance_ids']:
            raise LeaseError('rental_instance_preexisting')
        if op.get('action') != 'vast.rent':
            raise LeaseError('not_a_rental_lease')
        # After this bounded window, a matching host/GPU could be a later,
        # unrelated rental. Leave the obligation unresolved for operator review.
        if now > deadline + RENTAL_RECONCILIATION_GRACE_SECONDS:
            raise LeaseError('rental_reconciliation_window_expired')
        if not existing.startswith('pending:'):
            if existing == str(instance_id):
                connection.commit()
                return {'instance_id': instance_id, 'already_bound': True}
            raise LeaseError('rental_instance_conflict')
        if str(op.get('offer_id')) != existing.removeprefix('pending:'):
            raise LeaseError('offer_identity_mismatch')
        for field in ('machine_id', 'host_id'):
            expected = op.get(field)
            if type(expected) is not int or str(instance.get(field)) != str(expected):
                raise LeaseError('rental_identity_mismatch')
        if str(instance.get('gpu_name')) != str(op.get('gpu_name')):
            raise LeaseError('rental_gpu_mismatch')
        if type(instance.get('num_gpus')) is not int or instance['num_gpus'] != op.get('gpu_count'):
            raise LeaseError('rental_gpu_count_mismatch')
        hourly = instance.get('dph_total')
        price_violation = (type(hourly) not in (int,float) or not math.isfinite(hourly)
                           or hourly <= 0 or hourly > op.get('max_hourly_usd',0))
        if connection.execute(
            "SELECT 1 FROM vast_leases WHERE instance_id=? AND plan_id<>? AND phase='armed'",
            (str(instance_id),plan_id)).fetchone():
            raise LeaseError('instance_already_leased')
        # Snapshot is replaced with the verified identity for the stop guard.
        snapshot = dict(original_snapshot)
        snapshot.update(instance)
        snapshot['rental_price_violation'] = price_violation
        connection.execute(
            "UPDATE vast_leases SET instance_id=?,snapshot=?,deadline=CASE WHEN ? THEN MIN(deadline,?) ELSE deadline END,"
            "last_outcome=? WHERE plan_id=? AND phase='armed' AND instance_id=?",
            (str(instance_id),canonical(snapshot),int(price_violation),now,
             'rental_price_violation_stop_due' if price_violation else 'rental_identity_bound',
             plan_id,existing))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {'instance_id':instance_id,'already_bound':False,
            'price_violation':price_violation}

def check_expired(connection, helper, now=None, reconcile_pending=None):
    use_wall_clock = now is None
    now = int(time.time() if use_wall_clock else now)
    # The guard does NOT create or start instances. It reconciles pending rent
    # obligations from complete provider inventory on each independent timer tick.
    pending_rows = connection.execute(
        "SELECT plan_id,operation,snapshot FROM vast_leases "
        "WHERE phase='armed' AND instance_id LIKE 'pending:%' ORDER BY created LIMIT 50"
    ).fetchall()
    for plan_id, op_json, snap_json in pending_rows:
        if reconcile_pending is None:
            continue
        try:
            candidate = reconcile_pending(plan_id, json.loads(op_json), json.loads(snap_json))
            if isinstance(candidate, dict):
                bind_now = int(time.time()) if use_wall_clock else now
                bind_rental_instance(connection, plan_id, candidate, now=bind_now)
        except Exception:
            # Keep the durable lease pending; never repeat the create request.
            connection.execute(
                "UPDATE vast_leases SET last_attempt=?,last_outcome='rental_reconciliation_pending' "
                "WHERE plan_id=? AND phase='armed'", (now, plan_id))
    connection.commit()
    if use_wall_clock:
        now = int(time.time())
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
                # The stop helper only understands an existing instance. A bound
                # rental is converted to a stop-only operation with verified ID.
                bound = connection.execute('SELECT instance_id FROM vast_leases WHERE plan_id=?', (plan_id,)).fetchone()
                if not bound or bound[0].startswith('pending:'):
                    raise LeaseError('rental_identity_reconciliation_required')
                op = {'action':'vast.start','instance_id':bound[0],
                      'max_hourly_usd':op['max_hourly_usd'],
                      'max_total_usd':op['max_total_usd'],
                      'max_minutes':op['max_minutes']}
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
    completed_at = int(time.time()) if use_wall_clock else now
    connection.execute(
        'INSERT INTO lease_guard_heartbeat(id,completed_at) VALUES(1,?) '
        'ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at', (completed_at,))
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
        def reconcile_pending(plan_id, operation, snapshot):
            baseline = snapshot.get('baseline_instance_ids')
            if type(baseline) is not list:
                raise LeaseError('rental_baseline_missing')
            query = {'action':'vast.rent.reconcile',
                     'machine_id':operation['machine_id'],'host_id':operation['host_id'],
                     'gpu_name':operation['gpu_name'],'gpu_count':operation['gpu_count'],
                     'max_hourly_usd':operation['max_hourly_usd'],
                     'baseline_instance_ids':baseline}
            result = safe_helper(cfg['helper_command'], 'query', query, timeout=100)
            if result.get('inventory_complete') is not True or not isinstance(result.get('candidate'), dict):
                raise LeaseError('rental_inventory_incomplete')
            return result['candidate']
        answer = check_expired(
            db, lambda mode, op, snap: safe_helper(cfg['helper_command'], mode, op, snap),
            reconcile_pending=reconcile_pending)
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