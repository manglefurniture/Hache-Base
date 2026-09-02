#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_ROOT:?BACKUP_ROOT is required}"

RPO_SECONDS="${RPO_SECONDS:-86400}"
BACKUP_CHECK_NOW_EPOCH="${BACKUP_CHECK_NOW_EPOCH:-$(date -u +%s)}"
BACKUP_ALERT_COMMAND="${BACKUP_ALERT_COMMAND:-}"
BASH_ARITH_MAX="9223372036854775807"

is_bash_decimal() {
  local value="$1"
  local value_len max_len

  [[ "$value" =~ ^(0|[1-9][0-9]*)$ ]] || return 1
  value_len=${#value}
  max_len=${#BASH_ARITH_MAX}

  (( value_len < max_len )) && return 0
  (( value_len > max_len )) && return 1
  [[ "$value" == "$BASH_ARITH_MAX" || "$value" < "$BASH_ARITH_MAX" ]]
}

is_positive_bash_decimal() {
  is_bash_decimal "$1" && [[ "$1" != "0" ]]
}

is_positive_bash_decimal "$RPO_SECONDS" || {
  echo "RPO_SECONDS must be a positive decimal integer within Bash arithmetic range" >&2
  exit 2
}
is_bash_decimal "$BACKUP_CHECK_NOW_EPOCH" || {
  echo "BACKUP_CHECK_NOW_EPOCH must be a decimal integer epoch within Bash arithmetic range" >&2
  exit 2
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "sha256sum is required" >&2
  exit 1
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

checksum_manifest_complete() {
  local dir="$1"
  local sums="$dir/SHA256SUMS"

  grep -Eq '^[[:xdigit:]]{64}[[:space:]][ *]commit\.txt$' "$sums" &&
    grep -Eq '^[[:xdigit:]]{64}[[:space:]][ *]database\.sql$' "$sums"
}

latest_valid_epoch=-1
latest_valid_backup=""
latest_seen_epoch=-1
latest_seen_backup=""
latest_seen_valid=0
latest_seen_reason=""
unrankable_invalid_backup=""
unrankable_invalid_reason=""

shopt -s nullglob
for candidate in "${BACKUP_ROOT%/}"/deploy-*; do
  [[ -d "$candidate" ]] || continue
  [[ -f "$candidate/BACKUP_COMPLETE" ]] || continue

  if [[ ! -f "$candidate/backup-manifest.env" ]]; then
    unrankable_invalid_backup="$candidate"
    unrankable_invalid_reason="missing_manifest"
    continue
  fi

  epoch="$(awk -F= '$1 == "created_at_epoch" { print $2; exit }' "$candidate/backup-manifest.env")"
  if ! is_bash_decimal "$epoch"; then
    unrankable_invalid_backup="$candidate"
    unrankable_invalid_reason="invalid_created_at_epoch"
    continue
  fi

  candidate_valid=1
  candidate_reason=""
  manifest_status="$(awk -F= '$1 == "backup_status" { print $2; exit }' "$candidate/backup-manifest.env")"

  if [[ "$manifest_status" != "complete" ]]; then
    candidate_valid=0
    candidate_reason="manifest_status"
  elif [[ ! -f "$candidate/commit.txt" ]]; then
    candidate_valid=0
    candidate_reason="missing_commit"
  elif [[ ! -s "$candidate/database.sql" ]]; then
    candidate_valid=0
    candidate_reason="missing_database_sql"
  elif [[ ! -f "$candidate/SHA256SUMS" ]]; then
    candidate_valid=0
    candidate_reason="missing_checksums"
  elif ! checksum_manifest_complete "$candidate"; then
    candidate_valid=0
    candidate_reason="checksum_manifest_incomplete"
  elif ! (
    cd "$candidate"
    sha256sum --check --strict SHA256SUMS >/dev/null 2>&1
  ); then
    candidate_valid=0
    candidate_reason="checksum_failed"
  fi

  if (( epoch > latest_seen_epoch )); then
    latest_seen_epoch="$epoch"
    latest_seen_backup="$candidate"
    latest_seen_valid="$candidate_valid"
    latest_seen_reason="$candidate_reason"
  elif (( epoch == latest_seen_epoch && candidate_valid == 0 )); then
    latest_seen_backup="$candidate"
    latest_seen_valid=0
    latest_seen_reason="$candidate_reason"
  fi

  if (( candidate_valid == 1 && epoch > latest_valid_epoch )); then
    latest_valid_epoch="$epoch"
    latest_valid_backup="$candidate"
  fi
done
shopt -u nullglob

if [[ -n "$unrankable_invalid_backup" ]]; then
  echo "BACKUP_FRESHNESS status=invalid_backup backup=$unrankable_invalid_backup reason=$unrankable_invalid_reason age_seconds=unknown rpo_seconds=$RPO_SECONDS" >&2
  alert "invalid_backup" "$unrankable_invalid_backup" "unknown"
  exit 1
fi

if [[ -z "$latest_seen_backup" ]]; then
  echo "BACKUP_FRESHNESS status=missing backup=none age_seconds=unknown rpo_seconds=$RPO_SECONDS"
  alert "missing" "none" "unknown"
  exit 1
fi

if (( latest_seen_valid == 0 && latest_seen_epoch >= latest_valid_epoch )); then
  echo "BACKUP_FRESHNESS status=invalid_backup backup=$latest_seen_backup reason=$latest_seen_reason created_at_epoch=$latest_seen_epoch rpo_seconds=$RPO_SECONDS" >&2
  alert "invalid_backup" "$latest_seen_backup" "unknown"
  exit 1
fi

if [[ -z "$latest_valid_backup" ]]; then
  echo "BACKUP_FRESHNESS status=missing backup=none age_seconds=unknown rpo_seconds=$RPO_SECONDS"
  alert "missing" "none" "unknown"
  exit 1
fi

if (( latest_valid_epoch > BACKUP_CHECK_NOW_EPOCH )); then
  echo "BACKUP_FRESHNESS status=invalid_future_timestamp backup=$latest_valid_backup created_at_epoch=$latest_valid_epoch now_epoch=$BACKUP_CHECK_NOW_EPOCH rpo_seconds=$RPO_SECONDS" >&2
  alert "invalid_future_timestamp" "$latest_valid_backup" "unknown"
  exit 1
fi

age_seconds=$(( BACKUP_CHECK_NOW_EPOCH - latest_valid_epoch ))
if (( age_seconds > RPO_SECONDS )); then
  echo "BACKUP_FRESHNESS status=stale backup=$latest_valid_backup age_seconds=$age_seconds rpo_seconds=$RPO_SECONDS"
  alert "stale" "$latest_valid_backup" "$age_seconds"
  exit 1
fi

echo "BACKUP_FRESHNESS status=fresh backup=$latest_valid_backup age_seconds=$age_seconds rpo_seconds=$RPO_SECONDS"
