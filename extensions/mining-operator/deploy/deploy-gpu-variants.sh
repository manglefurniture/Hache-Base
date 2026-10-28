#!/usr/bin/env bash
# Hache Mining Agent: exact-commit root-only deploy for broker and Telegram.
# No provider mutating API calls. Existing finance/watchdog timers remain on.
set -Eeuo pipefail
umask 022
export PYTHONDONTWRITEBYTECODE=1
SHA="${1:-}"
OP=/opt/hache-mining-operator
BOT=/opt/hache-mining-agent
REPO=https://github.com/manglefurniture/Hache-Base.git
OS="$OP/releases/$SHA/extensions/mining-operator"
BS="$BOT/releases/$SHA/extensions/mining-operator"
error(){ echo "DEPLOY_ABORTED=$1" >&2; exit 1; }
[[ "$EUID" == 0 ]] || error 'root_required'
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || error 'invalid_full_commit'
[[ -L "$OP/current" && -L "$BOT/current" ]] || error 'missing_active_links'
OLD_OS="$(readlink "$OP/current")"
OLD_BS="$(readlink "$BOT/current")"
[[ -f "$OLD_OS/broker.py" && -f "$OLD_BS/telegram_proposals.py" ]] || error 'missing_previous_releases'
[[ "$OLD_OS" != "$OS" && "$OLD_BS" != "$BS" ]] || error 'already_installed'
for unit in hache-mining-operator.socket hache-mining-operator.service hache-mining-agent-telegram.service hache-miner-vast-watchdog.timer hache-mining-operator-vast-lease.timer; do
 systemctl is-active --quiet "$unit" || error "inactive_$unit"
done
[[ -f /etc/hache-mining-agent/telegram_token && -f /etc/hache-mining-agent/telegram-recipient.env ]] || error 'missing_telegram_secret'
exec 9>/run/lock/hache-gpu-release.lock
flock -n 9 || error 'another_deploy_in_progress'

check_leases() {
 runuser -u hache-miner -- python3 -c '
import json,sqlite3,sys
from urllib.parse import quote
with open("/etc/hache-mining-operator/config.json",encoding="utf8") as f:
    cfg=json.load(f)
path=cfg["database"]
if not isinstance(path,str) or not path.startswith("/var/lib/hache-mining-operator/"):
    raise SystemExit(2)
with sqlite3.connect("file:"+quote(path,safe="/")+"?mode=ro",uri=True,timeout=5) as db:
    n=int(db.execute("SELECT COUNT(*) FROM vast_leases WHERE phase=?",("armed",)).fetchone()[0])
print("ACTIVE_FINANCIAL_LEASES="+str(n))
sys.exit(0 if n==0 else 3)
'
}
check_clore_leases() {
 local db=/var/lib/hache-mining-operator/clore-cancel.sqlite3
 if [[ ! -e "$db" ]]; then
   return 0  # Clore guard not installed yet.
 fi
 systemctl is-active --quiet hache-mining-operator-clore-cancel.timer || return 2
 runuser -u hache-miner -- python3 - "$db" <<'PY'
import sqlite3,sys
from pathlib import Path
path=Path(sys.argv[1])
if not path.is_file() or path.is_symlink():
    raise SystemExit(2)
with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=5) as conn:
    n=int(conn.execute("SELECT COUNT(*) FROM clore_cancel_leases WHERE phase='armed'").fetchone()[0])
    table_exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='clore_preorders'").fetchone()
    pending=int(conn.execute("SELECT COUNT(*) FROM clore_preorders WHERE phase IN ('reserved','uncertain')").fetchone()[0]) if table_exists else 0
print("CLORE_ARMED_ORDERS="+str(n))
print("CLORE_RESERVED_PREORDERS="+str(pending))
sys.exit(0 if n==0 and pending==0 else 3)
PY
}
check_leases || error 'active_or_unreadable_financial_obligation'
check_clore_leases || error 'active_or_unreadable_clore_financial_obligation'

stage() {
 local root="$1"
 local dst="$root/releases/$SHA"
 install -d -o root -g root -m 0755 "$root/releases"
 if [[ ! -e "$dst" ]]; then
   git init --quiet "$dst" || error 'git_init_failed'
   git -C "$dst" remote add origin "$REPO" || error 'git_remote_failed'
   git -C "$dst" fetch --quiet --no-tags --depth 1 origin "$SHA" || error 'exact_commit_fetch_failed'
   git -C "$dst" -c advice.detachedHead=false checkout --quiet --detach "$SHA" ||
       error 'exact_commit_checkout_failed'
 fi
 [[ -d "$dst/.git" && "$(git -C "$dst" rev-parse HEAD)" == "$SHA" ]] || error 'git_sha_mismatch'
 [[ -z "$(git -C "$dst" status --porcelain=v1 --untracked-files=all)" ]] ||
     error 'modified_or_extra_release_files'
 [[ -z "$(find "$dst" ! -user root -print -quit)" ]] ||
     error 'release_contains_untrusted_owner'
 [[ -f "$dst/extensions/mining-operator/gpu_variant.php" ]] || error 'gpu_module_missing'
 # Root-owned, Git-clean versioned source with no secrets, readable by two
 # different unprivileged service accounts. No modification to code content.
 find "$dst" -type d -exec chmod go+rx,go-w {} +
 find "$dst" -type f -exec chmod go+r,go-w {} +
}
stage "$OP"
stage "$BOT"
php -l "$OS/gpu_variant.php"
php -l "$OS/clore_market.php"
php -l "$OS/provider.php"
php "$OS/test_clore_market.php"
php "$OS/test_provider.php"
python3 -m unittest discover -s "$OS" -p test_mining_advisor.py -q
python3 -m unittest discover -s "$OS" -p test_clore_cancel_guard.py -q
python3 -m unittest discover -s "$OS" -p test_clore_pool_watch.py -q
python3 -m unittest discover -s "$OS" -p test_clore_spot_quote.py -q
python3 -m unittest discover -s "$OS" -p test_clore_preorder.py -q
python3 -m unittest discover -s "$OS" -p test_clore_pending_recovery.py -q
python3 -m unittest discover -s "$OS" -p test_clore_create_journal.py -q
python3 -m unittest discover -s "$BS" -p test_telegram_proposals.py -q
python3 -m unittest discover -s "$BS" -p test_clore_telegram_proposals.py -q
python3 -m unittest discover -s "$BS" -p test_clore_consent_attestation.py -q
python3 -m unittest discover -s "$BS" -p test_clore_consent_exchange.py -q
python3 -m unittest discover -s "$BS" -p test_telegram_menu.py -q
python3 -m unittest discover -s "$BS" -p test_telegram_clore_search.py -q
python3 -m unittest discover -s "$BS" -p test_telegram_clore_competition.py -q
python3 -m unittest discover -s "$BS" -p test_telegram_prl_scenario.py -q
python3 -m unittest discover -s "$BS" -p test_telegram_onboard.py -q
runuser -u hache-miner -- test -r "$OS/broker.py" || error 'broker_release_inaccessible'
runuser -u hache-telegram -- test -r "$BS/telegram_proposals.py" || error 'bot_release_inaccessible'
runuser -u hache-telegram -- test -r "$BS/telegram_clore_search.py" || error 'gpu_search_release_inaccessible'
runuser -u hache-telegram -- test -r "$BS/telegram_clore_competition.py" || error 'gpu_competition_release_inaccessible'
runuser -u hache-telegram -- test -r "$BS/telegram_prl_scenario.py" || error 'gpu_prl_scenario_release_inaccessible'

STARTED=0
rollback() {
 local status="$1"
 trap - ERR INT TERM
 set +e
 if [[ "$STARTED" == 1 ]]; then
   ln -s "$OLD_OS" "$OP/.rollback.$$"
   mv -Tf "$OP/.rollback.$$" "$OP/current"
   ln -s "$OLD_BS" "$BOT/.rollback.$$"
   mv -Tf "$BOT/.rollback.$$" "$BOT/current"
   systemctl start hache-mining-operator.socket
   systemctl restart hache-mining-operator.service
   systemctl restart hache-mining-agent-telegram.service
 fi
 echo "DEPLOY_FAILED_ROLLBACK_ATTEMPTED=true EXIT=$status" >&2
 echo "BROKER_STATE=$(systemctl is-active hache-mining-operator.service)" >&2
 echo "TELEGRAM_STATE=$(systemctl is-active hache-mining-agent-telegram.service)" >&2
 exit 1
}
trap 'rollback "$?"' ERR
trap 'rollback 130' INT
trap 'rollback 143' TERM

# Freeze commercial broker requests; never interrupt real GPUs or watchdogs.
STARTED=1
systemctl stop hache-mining-operator.socket hache-mining-operator.service
check_leases
check_clore_leases
ln -s "$OS" "$OP/.new.$$"
mv -Tf "$OP/.new.$$" "$OP/current"
ln -s "$BS" "$BOT/.new.$$"
mv -Tf "$BOT/.new.$$" "$BOT/current"
systemctl start hache-mining-operator.socket
systemctl start hache-mining-operator.service
systemctl restart hache-mining-agent-telegram.service
sleep 3
for unit in hache-mining-operator.socket hache-mining-operator.service hache-mining-agent-telegram.service hache-miner-vast-watchdog.timer hache-mining-operator-vast-lease.timer; do
 systemctl is-active --quiet "$unit" || false
done

# Read-only broker smoke; do not send an order, bid, rental or root grant.
runuser -u gpt-agent -- python3 /home/gpt-agent/mining-operator/client.py '{"method":"capabilities"}' |
 python3 -c '
import json,sys
o=json.load(sys.stdin)
assert o.get("ok") is True
r=o["result"]
assert "clore.marketplace" in r["reads"]
assert "disabled:" in r.get("vast.rent","")
print("BROKER_OK=true RENTAL_PERMITTED=false")
'
runuser -u gpt-agent -- python3 /home/gpt-agent/mining-operator/client.py '{"method":"query","operation":{"action":"clore.marketplace"}}' |
 python3 -c '
import json,sys
o=json.load(sys.stdin)
assert o.get("ok") is True
r=o["result"]
assert r.get("rental_authorized") is False
assert isinstance(r.get("prl_gpu_models"),list)
assert isinstance(r.get("prl_gpu_models_total"),int)
print("CLORE_GPU_VARIANTS="+str(r["prl_gpu_models_total"]))
'
[[ "$(readlink "$OP/current")" == "$OS" && "$(readlink "$BOT/current")" == "$BS" ]] || false
trap - ERR INT TERM
echo "DEPLOY_SUCCESS=true"
echo "RELEASE_SHA=$SHA"
echo "OPERATOR=$(systemctl is-active hache-mining-operator.service)"
echo "TELEGRAM=$(systemctl is-active hache-mining-agent-telegram.service)"
echo "FINANCIAL_TIMER=$(systemctl is-active hache-mining-operator-vast-lease.timer)"
echo "WATCHDOG=$(systemctl is-active hache-miner-vast-watchdog.timer)"
echo "RENTAL_PERMITTED=false"
