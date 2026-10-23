#!/usr/bin/env bash
# Install private, NO-SPEND Telegram proposal transport from verified GitHub release.
set -Eeuo pipefail
umask 077
fail() { printf 'TELEGRAM_SETUP_FAILED=%s\n' "$1" >&2; exit 1; }

[[ "$EUID" -eq 0 ]] || fail root_required
[[ "$#" -eq 2 && "$1" =~ ^[a-f0-9]{40}$ && "$2" =~ ^[a-f0-9]{16}$ ]] || fail expected_sha_and_pair_code_required
SHA="$1"
PAIR_CODE="$2"
ROOT="/opt/hache-mining-agent"
REPO="$ROOT/releases/$SHA"
SRC="$REPO/extensions/mining-operator"
UNIT="/etc/systemd/system/hache-mining-agent-telegram.service"
TEMPLATE="$SRC/deploy/hache-mining-agent-telegram.service.example"
RECIPIENT="/etc/hache-mining-agent/telegram-recipient.env"
TOKEN="/etc/hache-mining-agent/telegram_token"

[[ -d "$REPO/.git" && -f "$TEMPLATE" ]] || fail missing_versioned_release
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$SHA" ]] || fail release_sha_mismatch
[[ "$(readlink -f "$ROOT/current")" == "$SRC" ]] || fail current_release_mismatch
[[ -f "$TOKEN" && ! -L "$TOKEN" ]] || fail bot_token_not_provisioned
[[ "$(stat -c '%u:%a' "$TOKEN")" == "0:600" ]] || fail token_permissions_invalid
[[ "$(stat -c '%u:%a' "$(dirname "$TOKEN")")" == "0:700" ]] || fail token_directory_permissions_invalid
[[ ! -L "$UNIT" ]] || fail unit_symlink_denied

# Discover recipient only after the owner sends a fresh /pair CODE in the private bot chat.
if [[ ! -e "$RECIPIENT" ]]; then
  /usr/bin/python3 "$SRC/telegram_onboard.py" --write-config --pair-code "$PAIR_CODE" || fail onboarding_not_ready
else
  [[ ! -L "$RECIPIENT" && "$(stat -c '%u:%a' "$RECIPIENT")" == "0:600" ]] \
    || fail recipient_permissions_invalid
  [[ "$(wc -l < "$RECIPIENT")" -eq 2 ]] || fail unexpected_recipient_file
  grep -Eq '^HACHE_TELEGRAM_CHAT_ID=[0-9]+$' "$RECIPIENT" || fail invalid_chat_id
  grep -Eq '^HACHE_TELEGRAM_USER_ID=[0-9]+$' "$RECIPIENT" || fail invalid_user_id
fi

if ! id hache-telegram >/dev/null 2>&1; then
  /usr/sbin/useradd --system --user-group --no-create-home \
    --home-dir /nonexistent --shell /usr/sbin/nologin hache-telegram
fi

if [[ -e "$UNIT" ]]; then
  cmp -s "$TEMPLATE" "$UNIT" || fail preexisting_different_unit
else
  install -o root -g root -m 0644 "$TEMPLATE" "$UNIT"
fi

systemctl daemon-reload
systemctl enable --now hache-mining-agent-telegram.service
sleep 3
if ! systemctl is-active --quiet hache-mining-agent-telegram.service; then
  systemctl disable --now hache-mining-agent-telegram.service || true
  fail telegram_service_failed_safe_shutdown
fi

# Fixed text to already-discovered private chat; token never leaves this process.
SRC_PATH="$SRC" RECIPIENT_PATH="$RECIPIENT" /usr/bin/python3 - <<'PY'
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, os.environ["SRC_PATH"])
from telegram_onboard import read_token
from telegram_proposals import TelegramAPI

raw = Path(os.environ["RECIPIENT_PATH"]).read_text(encoding="ascii")
matches = re.fullmatch(
    r"HACHE_TELEGRAM_CHAT_ID=([0-9]+)\nHACHE_TELEGRAM_USER_ID=([0-9]+)\n", raw)
if not matches:
    raise SystemExit("TELEGRAM_SETUP_FAILED=invalid_recipient_config")
api = TelegramAPI(read_token())
api.call("sendMessage", {
    "chat_id": int(matches.group(1)),
    "text": ("Hache Mining Agent conectado. Canal de propuestas activo en modo "
             "observación. Aceptar una propuesta NO alquila GPUs ni autoriza gastos.")
})
print("TELEGRAM_TEST_MESSAGE_SENT=true RENTAL_PERMITTED=false")
PY

printf 'TELEGRAM_SERVICE='
systemctl is-active hache-mining-agent-telegram.service
printf 'MINING_OPERATOR_SOCKET='
systemctl is-active hache-mining-operator.socket
printf 'VERSIONED_RELEASE=%s\n' "$SHA"
