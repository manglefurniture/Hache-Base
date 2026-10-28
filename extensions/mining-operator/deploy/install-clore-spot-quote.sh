#!/usr/bin/env bash
# Run only as root AFTER an approved exact-commit Hache-Base deployment.
# Installs ONE socket-activated read-only GET service, never modifies active rent.
set -Eeuo pipefail
umask 077

OP=/opt/hache-mining-operator/current
DIR=/etc/systemd/system
NAME=hache-mining-operator-clore-spot-quote

abort(){ echo "SPOT_QUOTE_INSTALL_ABORTED=$1" >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || abort "root_required"
[[ -L "$OP" && -f "$OP/clore_spot_quote.py" &&
   -f "$OP/clore_spot_quote_service.py" ]] || abort "release_not_deployed"
id hache-miner >/dev/null 2>&1 || abort "miner_account_missing"
getent group hache-telegram >/dev/null || abort "telegram_group_missing"
[[ -f /etc/hache-miner/secrets/clore_api_key &&
   ! -L /etc/hache-miner/secrets/clore_api_key ]] || abort "root_clore_api_key_missing"
systemctl is-active --quiet hache-mining-operator-clore-cancel.timer ||
  abort "clore_financial_timer_inactive"

exec 9>/run/lock/hache-clore-spot-quote-install.lock
flock -n 9 || abort "installer_already_running"

for suffix in socket service; do
  src="$OP/deploy/$NAME.$suffix.example"
  dst="$DIR/$NAME.$suffix"
  [[ -f "$src" && ! -L "$src" ]] || abort "missing_reviewed_unit_$suffix"
  if [[ -e "$dst" ]]; then
    cmp -s "$src" "$dst" || abort "conflicting_unit_$suffix"
  else
    install -o root -g root -m 0644 "$src" "$dst"
  fi
done

systemd-analyze verify "$DIR/$NAME.socket" "$DIR/$NAME.service" ||
  abort "systemd_unit_validation_failed"
systemctl daemon-reload
systemctl enable --now "$NAME.socket"
systemctl is-active --quiet "$NAME.socket" || abort "socket_inactive"
# No SSH, rental, bid, or external HTTP calls. Service activates at first GET.
echo "SPOT_QUOTE_SOCKET_INSTALLED=true"
echo "SPOT_QUOTE_AUTH=systemd_private_credential"
echo "RENTAL_PERMITTED=false"
