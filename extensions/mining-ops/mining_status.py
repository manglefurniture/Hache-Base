#!/usr/bin/env python3
"""Bounded read-only diagnostics. No provider credentials or mutation commands."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

TIMERS = (
    'hache-miner-poll.timer', 'hache-miner-vast-watchdog.timer',
    'hache-miner-vast-auto-stop.timer', 'hache-miner-interactive-auto.timer',
    'hache-salad-monitor.timer',
)
# Fixed projections deliberately exclude secrets, logs, personal data and wallets.
QUERIES = {
    'vast': """SELECT JSON_OBJECT('instance_id',v.instance_id,'enabled',v.enabled,
        'gpu_count',v.gpu_count,'hourly_usd',v.hourly_usd,
        'low_ths',v.low_ths,'total_ths',s.total_ths,
        'sample_age_s',TIMESTAMPDIFF(SECOND,s.observed_at,UTC_TIMESTAMP()),
        'receive_age_s',TIMESTAMPDIFF(SECOND,s.received_at,UTC_TIMESTAMP()),
        'reported_gpus',(SELECT COUNT(*) FROM vast_gpu_samples g WHERE g.sample_id=s.id))
        FROM vast_instances v LEFT JOIN vast_samples s ON s.id=
        (SELECT MAX(z.id) FROM vast_samples z WHERE z.instance_id=v.instance_id)
        ORDER BY v.instance_id LIMIT 100""",
    'sync': """SELECT JSON_OBJECT('source',r.source_name,'status',r.status,
        'age_s',TIMESTAMPDIFF(SECOND,r.observed_at,UTC_TIMESTAMP()))
        FROM sync_runs r JOIN (SELECT source_name,MAX(id) id FROM sync_runs
        WHERE source_name LIKE 'salad:%' OR source_name LIKE 'kryptex:%'
        GROUP BY source_name) recent ON r.id=recent.id
        ORDER BY r.source_name LIMIT 200""",
    'salad': """SELECT JSON_OBJECT('organization',t.organization_slug,
        'project',t.project_slug,'enabled',t.enabled,
        'latest_age_s',(SELECT TIMESTAMPDIFF(SECOND,MAX(r.observed_at),UTC_TIMESTAMP())
          FROM sync_runs r WHERE r.source_name=CONCAT('salad:',t.organization_slug,'/',t.project_slug)),
        'recent_groups',(SELECT COUNT(*) FROM group_state g
          WHERE g.organization=t.organization_slug AND g.project_name=t.project_slug
          AND g.last_seen_at>UTC_TIMESTAMP()-INTERVAL 15 MINUTE))
        FROM salad_targets t ORDER BY t.id LIMIT 100""",
}


def run(argv):
    # Never expose stderr: command errors may contain private configuration.
    result = subprocess.run(argv, capture_output=True, text=True, timeout=12,
                            encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError('diagnostic_command_failed')
    return result.stdout


def database_snapshot():
    data = {}
    for name, query in QUERIES.items():
        output = run(['mariadb', '--no-defaults', '--protocol=socket',
                      '--socket=/run/mysqld/mysqld.sock', '--user=gpt-agent',
                      '--batch', '--raw', '--skip-column-names',
                      '--init-command=SET SESSION max_statement_time=5',
                      'hache_miner', '-e', query])
        data[name] = [json.loads(row) for row in output.splitlines() if row.strip()]
    return data


def evaluate(data, timers, resources):
    alerts = []

    def add(code, target):
        alerts.append({'code': code, 'target': str(target)})

    for name, active in timers.items():
        if active != 'active':
            add('timer_not_active', name)
    if resources.get('disk_used_pct', 0) >= 90:
        add('disk_pressure', '/')
    if resources.get('memory_available_mb', 1024) < 80:
        add('memory_pressure', 'vps')
    for item in data.get('vast', []):
        if not item.get('enabled'):
            continue
        target = item['instance_id']
        ages = [item.get('sample_age_s'), item.get('receive_age_s')]
        if any(age is None or float(age) > 180 or float(age) < -30 for age in ages):
            # Registration is not provider state. Never restart on this signal.
            add('vast_telemetry_stale_or_missing', target)
            continue
        if item.get('reported_gpus') != item.get('gpu_count'):
            add('vast_gpu_count_mismatch', target)
        rate, threshold = item.get('total_ths'), item.get('low_ths')
        if rate is None:
            add('vast_hashrate_unknown', target)
        elif threshold is not None and float(rate) < float(threshold):
            add('vast_low_hashrate_snapshot', target)
    for item in data.get('sync', []):
        age = item.get('age_s')
        if age is None or float(age) > 900 or float(age) < -30:
            add('sync_stale', item['source'])
        elif item.get('status') not in ('ok', 'success'):
            add('sync_' + ('partial' if item.get('status') == 'partial' else 'error'),
                item['source'])
    for item in data.get('salad', []):
        if not item.get('enabled'):
            continue
        age = item.get('latest_age_s')
        if age is None or float(age) > 900 or float(age) < -30:
            add('salad_project_not_observed', item['organization'] + '/' + item['project'])
    return sorted(alerts, key=lambda a: (a['code'], a['target']))


def fingerprint(alerts):
    return hashlib.sha256(json.dumps(alerts, sort_keys=True).encode()).hexdigest()


def resources():
    disk = shutil.disk_usage('/')
    result = {'disk_used_pct': round(100 * disk.used / disk.total, 1)}
    try:
        memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        result['memory_available_mb'] = int(memory['MemAvailable'].split()[0]) // 1024
    except (OSError, KeyError, ValueError):
        result['memory_available_mb'] = None
    return result


def write_state(folder, result):
    folder = Path(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / 'latest.json'
    try:
        previous = json.loads(target.read_text())
    except (OSError, ValueError):
        previous = {}
    result['changed'] = previous.get('fingerprint') != result['fingerprint']
    fd, temporary = tempfile.mkstemp(prefix='.status-', dir=folder)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', help='Optional local state; no database writes')
    args = parser.parse_args()
    result = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'provider_live_status': 'not_queried', 'automatic_actions': []}
    try:
        result['data'] = database_snapshot()
        timer_output = run(['systemctl', 'show', *TIMERS, '-p', 'Id', '-p', 'ActiveState'])
        timers = {}
        for block in timer_output.strip().split('\n\n'):
            fields = dict(line.split('=', 1) for line in block.splitlines() if '=' in line)
            if fields.get('Id') in TIMERS:
                timers[fields['Id']] = fields.get('ActiveState', 'unknown')
        result['timers'] = {name: timers.get(name, 'unknown') for name in TIMERS}
        result['resources'] = resources()
        # An unavailable metric is a diagnostic failure, never a healthy default.
        if result['resources']['memory_available_mb'] is None:
            raise RuntimeError('resources_unavailable')
        result['alerts'] = evaluate(result['data'], result['timers'], result['resources'])
        result['status'] = 'attention' if result['alerts'] else 'ok'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        result['status'] = 'unknown'
        result['alerts'] = [{'code': 'diagnostic_unavailable', 'target': 'vps'}]
    result['fingerprint'] = fingerprint(result['alerts'])
    if args.state_dir:
        write_state(args.state_dir, result)
    print(json.dumps(result, indent=2))
    return 2 if result['status'] == 'unknown' else 0


if __name__ == '__main__':
    raise SystemExit(main())
