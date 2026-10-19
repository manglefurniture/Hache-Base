#!/usr/bin/env bash
# One-time, root-only installation of the reviewed Vast financial lease service.
# Does not create a plan, issue a grant, start an instance or run any SSH command.
set -Eeuo pipefail
if [ "$(id -u)" -ne 0 ]; then echo 'RUN_AS_ROOT_REQUIRED'; exit 1; fi

ROOT=/opt/hache-mining-operator
REV=4493d0e26517ff7066c4effff85dce4fa021415e
SRC=/home/gpt-agent/mining-ops/staging/$REV
NEW=$ROOT/releases/$REV
DEST=$NEW/extensions/mining-operator
OLD=$(readlink -f "$ROOT/current")

if [ "$OLD" != "$ROOT/releases/b06c2817eea136be4f9c17ca081c9b0238ba5bbd/extensions/mining-operator" ]; then
  echo 'STOP: unexpected current operator release'; exit 2
fi
if [ "$(git hash-object "$OLD/provider.php")" != 553bded902cf5e6e26f142a16024440e3983f320 ]; then
  echo 'STOP: unexpected current provider'; exit 2
fi
if [ -e "$NEW" ] || [ -e /etc/systemd/system/hache-mining-operator-vast-lease.service ] ||
   [ -e /etc/systemd/system/hache-mining-operator-vast-lease.timer ]; then
  echo 'STOP: already installed or conflicting target'; exit 2
fi

verify() {
  local actual
  actual=$(git hash-object "$SRC/$1")
  if [ "$actual" != "$2" ]; then
    echo "STOP: Git blob mismatch: $1"; exit 3
  fi
}
verify broker.py 362d2a832a547dcefd7da63eaa46a7cebf141fea
verify provider.php 7480e0f53f32f60fd92992714bde5bf3a0fc642c
verify vast_start_guard.py 5a975552818b9a09050fd9855320277b15ac9aac
verify README.md 041438e14028338debb12b415e68914b5a990bdb
verify test_broker.py 6e3f8a6d051937b244410691afb64441e601b527
verify test_vast_start_guard.py bbf28440f2ce66d32db031297ec75552c67544b9
verify test_provider.php e0658d248345b3124a768969cc7847224acced2b
verify deploy/hache-mining-operator-vast-lease.service.example 4974793fac4d701ffce3311f015ea1bdeab498d1
verify deploy/hache-mining-operator-vast-lease.timer.example 3ef9307fb83e1f8deba824b3534996ecbb8c639d

echo 'VERIFIED: all files match merged GitHub release'
cp -a "$(dirname "$(dirname "$OLD")")" "$NEW"
for f in broker.py provider.php vast_start_guard.py README.md test_broker.py test_vast_start_guard.py test_provider.php; do
  install -o root -g root -m 0644 "$SRC/$f" "$DEST/$f"
done
for f in hache-mining-operator-vast-lease.service hache-mining-operator-vast-lease.timer; do
  install -o root -g root -m 0644 "$SRC/deploy/$f.example" "$DEST/deploy/$f.example"
  install -o root -g root -m 0644 "$SRC/deploy/$f.example" "/etc/systemd/system/$f"
done
php -l "$DEST/provider.php"
php "$DEST/test_provider.php"
python3 -m unittest discover -s "$DEST" -p 'test_*.py' -q
echo 'STAGED: release passes tests'

switched=0
rollback() {
  local rc=$?
  trap - ERR
  if [ "$switched" = 1 ]; then
    # Never disarm a financial lease on a rollback. Unexpected state requires
    # supervised recovery rather than a dangerous automatic timer shutdown.
    local armed
    armed=$(python3 - <<'PYARM'
import json,sqlite3
try:
    cfg=json.load(open('/etc/hache-mining-operator/config.json'))
    db=sqlite3.connect('file:'+cfg['database']+'?mode=ro',uri=True)
    print(db.execute("SELECT COUNT(*) FROM vast_leases WHERE phase='armed'").fetchone()[0])
except Exception:
    print('UNKNOWN')
PYARM
)
    if [ "$armed" != 0 ]; then
      echo "STOP: $armed leases could still be armed; keep supervisor active."
      exit "$rc"
    fi
    systemctl disable --now hache-mining-operator-vast-lease.timer || true
    ln -s "$OLD" "$ROOT/.current-guarded-restore"
    mv -Tf "$ROOT/.current-guarded-restore" "$ROOT/current"
    systemctl restart hache-mining-operator.service || true
  fi
  exit "$rc"
}
trap rollback ERR

ln -s "$DEST" "$ROOT/.current-guarded-install"
mv -Tf "$ROOT/.current-guarded-install" "$ROOT/current"
switched=1
systemctl daemon-reload
systemctl enable --now hache-mining-operator-vast-lease.timer
systemctl start hache-mining-operator-vast-lease.service
systemctl restart hache-mining-operator.service
systemctl is-active --quiet hache-mining-operator.service
systemctl is-active --quiet hache-mining-operator.socket
systemctl is-active --quiet hache-mining-operator-vast-lease.timer
test "$(systemctl show -p Result --value hache-mining-operator-vast-lease.service)" = success

runuser -u gpt-agent -- python3 /home/gpt-agent/mining-operator/client.py '{"method":"capabilities"}' |
  python3 -c 'import sys,json;x=json.load(sys.stdin);assert x["ok"];assert "vast.start" in x["result"]["writes_with_root_grant"];print("BROKER_START_GATED_OK")'

python3 - <<'PYCHK'
import json,sqlite3,time
cfg=json.load(open('/etc/hache-mining-operator/config.json'))
db=sqlite3.connect('file:'+cfg['database']+'?mode=ro',uri=True)
hb=db.execute('SELECT completed_at FROM lease_guard_heartbeat WHERE id=1').fetchone()
assert hb and 0<=time.time()-hb[0]<90, 'guard heartbeat missing'
assert db.execute("SELECT COUNT(*) FROM vast_leases WHERE phase='armed'").fetchone()[0]==0
print('LEASE_TIMER_HEALTHY_NO_ACTIVE_STARTS')
PYCHK

runuser -u gpt-agent -- python3 /home/gpt-agent/mining-ops/current/access_gateway.py query vast.status --instance-id 56667162 |
  python3 -c 'import sys,json;d=json.load(sys.stdin);assert d["ok"];r=d["result"];assert r["actual_status"]=="exited" and r["intended_status"]=="stopped";print("VAST_REMAINS_STOPPED")'

trap - ERR
echo 'STEP4_DEPLOY_OK: independent guard active; no GPU started'
