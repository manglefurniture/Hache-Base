#!/usr/bin/env bash
# Owner-operated temporary sudo administration for the already-connected gpt-agent.
# True NOPASSWD: ALL for the chosen window. Root commands may survive revocation.
set -Eeuo pipefail
if (( EUID != 0 )); then echo "ROOT_ONLY" >&2; exit 2; fi
umask 077
SUDOERS=/etc/sudoers.d/91-hache-gpt-agent-window
STATE_DIR=/var/lib/hache-gpt-sudo-window
STATE=$STATE_DIR/current
AGENT=gpt-agent
MAIN=/usr/local/sbin/hache-gpt-sudo-window
say(){ printf '%s\n' "$*"; }
check_owner(){
  getent passwd "$AGENT" >/dev/null || { say "MISSING_AGENT"; exit 2; }
  test -x /usr/sbin/visudo || { say "MISSING_VISUDO"; exit 2; }
  test -d /etc/sudoers.d || { say "MISSING_SUDOERS_DIR"; exit 2; }
  test -f "$MAIN" && test "$(stat -c %u:%a "$MAIN")" = "0:755" || { say "UNTRUSTED_HELPER"; exit 2; }
}
remove_grant(){
  /usr/bin/rm -f -- "$SUDOERS" "$STATE"
}
expire(){
  local expected="${1:-}" nonce end
  if [[ -f "$STATE" ]]; then
    read -r nonce end < "$STATE" || true
    if [[ "$nonce" == "$expected" ]]; then
      remove_grant
      say "TEMPORARY_SUDO_EXPIRED"
    fi
  fi
}
start(){
  local minutes="$1" nonce unit end tmp sudo_tmp
  [[ "$minutes" =~ ^[0-9]+$ ]] || { say "INVALID_MINUTES"; exit 2; }
  (( minutes >= 1 && minutes <= 1440 )) || { say "MINUTES_OUT_OF_RANGE_1_TO_1440"; exit 2; }
  check_owner
  /usr/bin/install -d -o root -g root -m 0700 "$STATE_DIR"
  nonce="$(/usr/bin/od -An -tx1 -N12 /dev/urandom | /usr/bin/tr -d ' \n')"
  unit="hache-gpt-sudo-expire-$nonce"
  end="$(( $(date +%s) + minutes*60 ))"
  if [[ -e "$SUDOERS" || -e "$STATE" ]]; then
    say "ALREADY_ARMED_USE_STOP_FIRST"; exit 2
  fi
  tmp="$(mktemp "$STATE_DIR/.state.XXXXXXXX")"
  sudo_tmp="$(mktemp /etc/sudoers.d/.hache-sudo.XXXXXXXX)"
  printf '%s %s\n' "$nonce" "$end" > "$tmp"
  printf '%s\n' '# Managed temporary permission, revoke using hache-gpt-sudo-window stop' \
    "$AGENT ALL=(ALL:ALL) NOPASSWD: ALL" > "$sudo_tmp"
  chmod 0600 "$sudo_tmp"
  /usr/sbin/visudo -cf "$sudo_tmp" >/dev/null || { rm -f "$tmp" "$sudo_tmp"; say "BAD_SUDOERS"; exit 2; }
  # Separate root-owned systemd timer, independent of chat, Work and broker.
  if ! /usr/bin/systemd-run --quiet --unit="$unit" --on-active="${minutes}m" \
      "$MAIN" expire "$nonce"; then
    rm -f "$tmp" "$sudo_tmp"
    say "REVOCATION_TIMER_FAILED"; exit 2
  fi
  /usr/bin/install -o root -g root -m 0600 "$tmp" "$STATE"
  /usr/bin/install -o root -g root -m 0440 "$sudo_tmp" "$SUDOERS"
  rm -f "$tmp" "$sudo_tmp"
  /usr/sbin/visudo -cf "$SUDOERS" >/dev/null || { remove_grant; say "INSTALLED_SUDOERS_INVALID"; exit 2; }
  say "TEMPORARY_SUDO_ACTIVE"
  say "EXPIRES_UTC=$(date -u -d "@$end" +%FT%TZ)"
  say "DURATION_MINUTES=$minutes"
  say "REVOKE_NOW=$MAIN stop"
}
stop(){ remove_grant; say "TEMPORARY_SUDO_REVOKED"; }
status(){
  if [[ ! -f "$STATE" || ! -f "$SUDOERS" ]]; then say "TEMPORARY_SUDO_OFF"; return; fi
  local nonce end
  read -r nonce end < "$STATE" || { stop; return; }
  if [[ ! "$end" =~ ^[0-9]+$ ]] || (( $(date +%s) >= end )); then stop; return; fi
  say "TEMPORARY_SUDO_ON"
  say "EXPIRES_UTC=$(date -u -d "@$end" +%FT%TZ)"
}
case "${1:-}" in
  start) [[ $# == 2 ]] || exit 2; start "$2" ;;
  stop) [[ $# == 1 ]] || exit 2; stop ;;
  expire) [[ $# == 2 ]] || exit 2; expire "$2" ;;
  status) [[ $# == 1 ]] || exit 2; status ;;
  *) say "USAGE: $MAIN {start MINUTES|stop|status}"; exit 2 ;;
esac
