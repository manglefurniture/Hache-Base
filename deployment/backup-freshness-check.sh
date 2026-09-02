#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_ROOT:?BACKUP_ROOT is required}"

RPO_SECONDS="${RPO_SECONDS:-86400}"
BACKUP_CHECK_NOW_EPOCH="${BACKUP_CHECK_NOW_EPOCH:-$(date -u +%s)}"
BACKUP_ALERT_COMMAND="${BACKUP_ALERT_COMMAND:-}"

[[ "$RPO_SECONDS" =~ ^[0-9]+$ ]] && (( RPO_SECONDS > 0 )) || {
  echo "RPO_SECONDS must be a positive integer" >&2
  exit 2
}
[[ "$BACKUP_CHECK_NOW_EPOCH" =~ ^[0-9]+$ ]] || {
  echo "BACKUP_CHECK_NOW_EPOCH must be an integer epoch" >&2
  exit 2
}

alert() {
  local status="$1"
  local backup_path="$2"
  local age_seconds="$3"

  [[ -n "$BACKUP_ALERT_COMMAND" ]] || return 0
  if [[ ! -x "$BACKUP_ALERT_COMMAND" ]]; then
    echo "BACKUP_ALERT_WARNING command_not_executable=$BACKUP_ALERT_COMMAND" >&2
    return 0
  fi
  if ! "$BACKUP_ALERT_COMMAND" "$status" "$backup_path" "$age_seconds" "$RPO_SECONDS"; then
    echo "BACKUP_ALERT_WARNING command_failed=$BACKUP_ALERT_COMMAND status=$status" >&2
  fi
}

latest_epoch=-1
latest_backup=""

shopt -s nullglob
for candidate in "${BACKUP_ROOT%/}"/deploy-*; do
  [[ -d "$candidate" ]] || continue
  [[ -f "$candidate/BACKUP_COMPLETE" ]] || continue
  [[ -f "$candidate/backup-manifest.env" ]] || continue

  epoch="$(awk -F= '$1 == "created_at_epoch" { print $2; exit }' "$candidate/backup-manifest.env")"
  [[ "$epoch" =~ ^[0-9]+$ ]] || continue

  if (( epoch > latest_epoch )); then
    latest_epoch="$epoch"
    latest_backup="$candidate"
  fi
done
shopt -u nullglob

if [[ -z "$latest_backup" ]]; then
  echo "BACKUP_FRESHNESS status=missing backup=none age_seconds=unknown rpo_seconds=$RPO_SECONDS"
  alert "missing" "none" "unknown"
  exit 1
fi

if (( latest_epoch > BACKUP_CHECK_NOW_EPOCH )); then
  echo "BACKUP_FRESHNESS status=invalid_future_timestamp backup=$latest_backup created_at_epoch=$latest_epoch now_epoch=$BACKUP_CHECK_NOW_EPOCH rpo_seconds=$RPO_SECONDS" >&2
  alert "invalid_future_timestamp" "$latest_backup" "unknown"
  exit 1
fi

age_seconds=$(( BACKUP_CHECK_NOW_EPOCH - latest_epoch ))
if (( age_seconds > RPO_SECONDS )); then
  echo "BACKUP_FRESHNESS status=stale backup=$latest_backup age_seconds=$age_seconds rpo_seconds=$RPO_SECONDS"
  alert "stale" "$latest_backup" "$age_seconds"
  exit 1
fi

echo "BACKUP_FRESHNESS status=fresh backup=$latest_backup age_seconds=$age_seconds rpo_seconds=$RPO_SECONDS"
