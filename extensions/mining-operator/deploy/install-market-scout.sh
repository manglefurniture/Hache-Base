#!/usr/bin/env bash
# Root-run ONLY, after deploying the same SHA to both existing production
# broker and Telegram symlinks with deploy-gpu-variants.sh.
set -Eeuo pipefail
export PYTHONDONTWRITEBYTECODE=1
SHA="${1:-}"
SCRIPT=extensions/mining-operator
ROOT=/opt/hache-mining-operator
BOT=/opt/hache-mining-agent
SRC="$ROOT/releases/$SHA/$SCRIPT"
BOT_SRC="$BOT/releases/$SHA/$SCRIPT"
DIRECTORY=/etc/systemd/system
TIMER=hache-mining-market-scout.timer
SCOUT=hache-mining-market-scout.service
NOTIFIER=hache-mining-market-notifier.service

fail() { echo "MARKET_SCOUT_INSTALL_FAILED=$1" >&2; exit 1; }
[[ "$EUID" == 0 ]] || fail 'root_required'
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || fail 'invalid_release_commit'
[[ "$(readlink "$ROOT/current")" == "$SRC" &&
   "$(readlink "$BOT/current")" == "$BOT_SRC" ]] || fail 'both_releases_must_be_current'
[[ "$(git -C "$ROOT/releases/$SHA" rev-parse HEAD)" == "$SHA" &&
   "$(git -C "$BOT/releases/$SHA" rev-parse HEAD)" == "$SHA" ]] ||
    fail 'commit_identity_mismatch'
[[ -z "$(git -C "$ROOT/releases/$SHA" status --porcelain --untracked-files=all)" &&
   -z "$(git -C "$BOT/releases/$SHA" status --porcelain --untracked-files=all)" ]] ||
    fail 'nonclean_release'
for u in hache-mining-operator.service hache-mining-operator.socket \
         hache-mining-agent-telegram.service hache-mining-operator-vast-lease.timer \
         hache-miner-vast-watchdog.timer; do
    systemctl is-active --quiet "$u" || fail "prerequisite_inactive_$u"
done
[[ -f /etc/hache-mining-agent/telegram_token &&
   -f /etc/hache-mining-agent/telegram-recipient.env ]] ||
    fail 'missing_telegram_configuration'
[[ -f "$SRC/mining_market_scout.py" &&
   -f "$BOT_SRC/mining_market_notifier.py" ]] ||
    fail 'missing_scout_sources'
runuser -u gpt-agent -- test -r "$SRC/mining_market_scout.py" ||
    fail 'scout_release_inaccessible'
runuser -u hache-telegram -- test -r "$BOT_SRC/mining_market_notifier.py" ||
    fail 'notifier_release_inaccessible'

python3 -m unittest discover -s "$SRC" -p test_mining_market_scout.py -q ||
    fail 'market_scout_regression_failed'
python3 -m unittest discover -s "$BOT_SRC" -p test_telegram_menu.py -q ||
    fail 'telegram_menu_regression_failed'
python3 -m unittest discover -s "$SRC" -p test_broker.py -q ||
    fail 'broker_regression_failed'
php "$SRC/test_provider.php" || fail 'vast_projection_regression_failed'
php "$SRC/test_clore_market.php" || fail 'clore_projection_regression_failed'

# Only these three root-owned systemd units. No credentials or existing
# operator/watchdog/Telegram units are modified.
for unit in "$SCOUT" "$NOTIFIER" "$TIMER"; do
    install -o root -g root -m 0644 "$SRC/deploy/$unit" "$DIRECTORY/$unit" ||
        fail 'unit_copy_failed'
done
systemctl daemon-reload
systemctl enable --now "$TIMER" || fail 'scout_timer_failed'

# This performs read-only provider requests and Telegram sendMessage ONLY.
# OnSuccess also schedules notifier; its SQLite state suppresses duplicates.
if ! systemctl start "$SCOUT"; then
    systemctl disable --now "$TIMER" || true
    fail 'first_dual_api_scan_failed_timer_disabled'
fi
if ! systemctl start "$NOTIFIER"; then
    systemctl disable --now "$TIMER" || true
    fail 'first_telegram_notification_failed_timer_disabled'
fi

[[ "$(systemctl show --value -p Result "$SCOUT")" == "success" &&
   "$(systemctl show --value -p Result "$NOTIFIER")" == "success" ]] ||
   fail 'service_result_unhealthy'
systemctl is-active --quiet "$TIMER" || fail 'scout_timer_inactive'
echo "MARKET_SCOUT_INSTALL_OK=true"
echo "PERIODICITY=hourly"
echo "SCOUT_TIMER=active"
echo "BOTH_PROVIDERS=vast,clore"
echo "RENTING_ENABLED=false"
echo "TELEGRAM_ALERTS=deduplicated"
