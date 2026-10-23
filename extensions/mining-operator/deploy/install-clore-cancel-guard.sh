#!/usr/bin/env bash
# Root-only, reviewed-code installer for the idle Clore cancellation watchdog.
# Does NOT rent, bid, arm orders, read wallets, or modify existing leases.
set -Eeuo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
SHA="${1:-}"
KEY="${2:-}"
ROOT=/opt/hache-mining-operator
SRC="$ROOT/releases/$SHA/extensions/mining-operator"
UNIT=/etc/systemd/system/hache-mining-operator-clore-cancel.service
TIMER=/etc/systemd/system/hache-mining-operator-clore-cancel.timer
fail() { printf 'CLORE_GUARD_INSTALL_ABORTED=%s\n' "$1" >&2; exit 1; }

[[ "$EUID" -eq 0 ]] || fail root_required
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || fail invalid_release_sha
[[ "$KEY" =~ ^/etc/[A-Za-z0-9_./-]+$ && "$KEY" != *..* ]] ||
    fail invalid_root_credential_location
[[ -f "$KEY" && ! -L "$KEY" && "$(realpath -e "$KEY")" == "$KEY" ]] || fail root_credential_missing
[[ "$(stat -c %u "$KEY")" == 0 && "$(stat -c %a "$KEY")" == 600 ]] ||
    fail root_credential_must_be_root_0600
[[ -L "$ROOT/current" && "$(readlink "$ROOT/current")" == "$SRC" ]] ||
    fail exact_release_not_active
[[ "$(git -C "$ROOT/releases/$SHA" rev-parse HEAD)" == "$SHA" ]] ||
    fail commit_mismatch
[[ -z "$(git -C "$ROOT/releases/$SHA" status --porcelain --untracked-files=all)" ]] ||
    fail modified_release
[[ -f "$SRC/clore_cancel_guard.py" ]] || fail missing_clore_guard
[[ ! -e "$UNIT" && ! -e "$TIMER" ]] || fail existing_clore_service_must_be_reconciled
# Do not take over an existing financial obligation behind an unknown DB schema.
if [[ -f /var/lib/hache-mining-operator/clore-cancel.sqlite3 ]]; then
    fail existing_guard_state_must_be_reconciled
fi
for u in hache-mining-operator.service hache-mining-operator-vast-lease.timer \
         hache-miner-vast-watchdog.timer hache-mining-agent-telegram.service; do
    systemctl is-active --quiet "$u" || fail "prerequisite_inactive_$u"
done

exec 9>/run/lock/hache-clore-guard-deploy.lock
flock -n 9 || fail another_clore_install
[[ "$(stat -c %U /var/lib/hache-mining-operator)" == hache-miner ]] ||
    fail wrong_operator_state_owner
[[ -x "$(command -v python3)" ]] || fail missing_python
python3 -m unittest discover -s "$SRC" -p test_clore_cancel_guard.py -q ||
    fail clore_financial_tests_failed
bash -n "$SRC/deploy/install-clore-cancel-guard.sh" ||
    fail installer_syntax

# The only substituted value is a strict absolute root-owned credential path.
# Never echo the secret or read the key in a shell.
sed "s#^LoadCredential=clore_key:.*#LoadCredential=clore_key:$KEY#" \
    "$SRC/deploy/hache-mining-operator-clore-cancel.service.example" > "$UNIT.tmp.$$"
install -o root -g root -m 0644 "$UNIT.tmp.$$" "$UNIT"
rm -f "$UNIT.tmp.$$"
install -o root -g root -m 0644 \
    "$SRC/deploy/hache-mining-operator-clore-cancel.timer.example" "$TIMER"
systemctl daemon-reload
systemctl enable --now hache-mining-operator-clore-cancel.timer
if ! systemctl start hache-mining-operator-clore-cancel.service; then
    # Keep installed configuration for diagnosis; do not claim watchdog health.
    systemctl disable --now hache-mining-operator-clore-cancel.timer || true
    fail authenticated_idle_tick_failed_timer_disabled
fi
[[ "$(systemctl show --value -p Result hache-mining-operator-clore-cancel.service)" == success ]] ||
    fail clore_service_failed
systemctl is-active --quiet hache-mining-operator-clore-cancel.timer ||
    fail clore_timer_inactive

# An idle authenticated GET must have recorded a heartbeat.
runuser -u hache-miner -- python3 - "$SRC" <<'PY'
import sqlite3, sys, time
sys.path.insert(0, sys.argv[1])
from clore_cancel_guard import DEFAULT_DB
with sqlite3.connect(f"file:{DEFAULT_DB}?mode=ro", uri=True) as db:
    row = db.execute("SELECT completed_at FROM clore_cancel_heartbeat WHERE id=1").fetchone()
    active = db.execute("SELECT COUNT(*) FROM clore_cancel_leases WHERE phase='armed'").fetchone()[0]
assert row and 0 <= time.time() - row[0] < 100 and active == 0, "clore_guard_preflight_failed"
PY
printf 'CLORE_GUARD_INSTALL_OK=true\nTIMER=active\nHEARTBEAT=recent\nARMED_ORDERS=0\n'
printf 'RENTAL_PERMITTED=false\nNATIVE_CURRENCY_USD_ACCOUNTING_VERIFIED=false\n'
