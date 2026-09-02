#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_DIR:?BACKUP_DIR is required}"
: "${RESTORE_DB_HOST:?RESTORE_DB_HOST is required}"
: "${RESTORE_DB_NAME:?RESTORE_DB_NAME is required}"
: "${RESTORE_DB_USER:?RESTORE_DB_USER is required}"
: "${RESTORE_DB_PASSWORD:?RESTORE_DB_PASSWORD is required}"
: "${RESTORE_DRILL_REPORT_FILE:?RESTORE_DRILL_REPORT_FILE is required}"
: "${RESTORE_VERIFY_COMMAND:?RESTORE_VERIFY_COMMAND is required}"

RPO_SECONDS="${RPO_SECONDS:-86400}"
RTO_SECONDS="${RTO_SECONDS:-3600}"
RESTORE_DB_PORT="${RESTORE_DB_PORT:-3306}"
RESTORE_CONFIRM_ISOLATED="${RESTORE_CONFIRM_ISOLATED:-0}"
RESTORE_CLEANUP="${RESTORE_CLEANUP:-1}"
RESTORE_NOW_EPOCH="${RESTORE_NOW_EPOCH:-$(date -u +%s)}"

for value_name in RPO_SECONDS RTO_SECONDS RESTORE_NOW_EPOCH; do
  value="${!value_name}"
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "$value_name must be an integer" >&2; exit 2; }
done
(( RPO_SECONDS > 0 )) || { echo "RPO_SECONDS must be greater than zero" >&2; exit 2; }
(( RTO_SECONDS > 0 )) || { echo "RTO_SECONDS must be greater than zero" >&2; exit 2; }
[[ "$RESTORE_CLEANUP" == "0" || "$RESTORE_CLEANUP" == "1" ]] || { echo "RESTORE_CLEANUP must be 0 or 1" >&2; exit 2; }
[[ "$RESTORE_CONFIRM_ISOLATED" == "1" ]] || {
  echo "RESTORE_CONFIRM_ISOLATED=1 is required; restore drills must target an isolated database" >&2
  exit 2
}
[[ "$RESTORE_DB_NAME" =~ ^[A-Za-z0-9_]+$ ]] || {
  echo "RESTORE_DB_NAME may contain only letters, numbers and underscore" >&2
  exit 2
}

command -v mysql >/dev/null 2>&1 || { echo "mysql is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 1; }

[[ -d "$BACKUP_DIR" ]] || { echo "backup directory not found: $BACKUP_DIR" >&2; exit 1; }
[[ -f "$BACKUP_DIR/BACKUP_COMPLETE" ]] || { echo "backup is not marked complete" >&2; exit 1; }
[[ -f "$BACKUP_DIR/backup-manifest.env" ]] || { echo "backup manifest missing" >&2; exit 1; }
[[ -s "$BACKUP_DIR/database.sql" ]] || { echo "database.sql missing or empty" >&2; exit 1; }
[[ -f "$BACKUP_DIR/SHA256SUMS" ]] || { echo "SHA256SUMS missing" >&2; exit 1; }

source_db="$(awk -F= '$1 == "database_name" { print $2; exit }' "$BACKUP_DIR/backup-manifest.env")"
created_at_epoch="$(awk -F= '$1 == "created_at_epoch" { print $2; exit }' "$BACKUP_DIR/backup-manifest.env")"
[[ -n "$source_db" ]] || { echo "database_name missing from backup manifest" >&2; exit 1; }
[[ "$created_at_epoch" =~ ^[0-9]+$ ]] || { echo "created_at_epoch invalid in backup manifest" >&2; exit 1; }
[[ "$RESTORE_DB_NAME" != "$source_db" ]] || {
  echo "restore target must differ from source database: $source_db" >&2
  exit 2
}
(( created_at_epoch <= RESTORE_NOW_EPOCH )) || { echo "backup timestamp is in the future" >&2; exit 1; }

(
  cd "$BACKUP_DIR"
  sha256sum -c SHA256SUMS >/dev/null
)

mkdir -p "$(dirname "$RESTORE_DRILL_REPORT_FILE")"
umask 077

start_epoch="$(date -u +%s)"
restore_created=0
report_written=0
result_status="failed"
result_reason="unexpected_failure"
backup_age_seconds=$(( RESTORE_NOW_EPOCH - created_at_epoch ))

write_report() {
  local status="$1"
  local reason="$2"
  local end_epoch="$3"
  local duration_seconds=$(( end_epoch - start_epoch ))
  cat > "$RESTORE_DRILL_REPORT_FILE" <<EOF
RESTORE_DRILL status=$status reason=$reason
backup_dir=$BACKUP_DIR
source_database=$source_db
restore_database=$RESTORE_DB_NAME
backup_created_at_epoch=$created_at_epoch
backup_age_seconds=$backup_age_seconds
rpo_seconds=$RPO_SECONDS
restore_duration_seconds=$duration_seconds
rto_seconds=$RTO_SECONDS
verification_command_configured=yes
cleanup_enabled=$RESTORE_CLEANUP
EOF
  chmod 600 "$RESTORE_DRILL_REPORT_FILE"
}

cleanup_and_report() {
  local rc=$?
  local end_epoch
  end_epoch="$(date -u +%s)"

  if (( restore_created == 1 )) && [[ "$RESTORE_CLEANUP" == "1" ]]; then
    export MYSQL_PWD="$RESTORE_DB_PASSWORD"
    mysql --host="$RESTORE_DB_HOST" --port="$RESTORE_DB_PORT" --user="$RESTORE_DB_USER" \
      -e "DROP DATABASE IF EXISTS \`$RESTORE_DB_NAME\`;" >/dev/null 2>&1 || \
      echo "RESTORE_DRILL_WARNING cleanup_failed database=$RESTORE_DB_NAME" >&2
    unset MYSQL_PWD
  fi

  if (( report_written == 0 )); then
    write_report "$result_status" "$result_reason" "$end_epoch"
  fi
  exit "$rc"
}
trap cleanup_and_report EXIT

export MYSQL_PWD="$RESTORE_DB_PASSWORD"
mysql --host="$RESTORE_DB_HOST" --port="$RESTORE_DB_PORT" --user="$RESTORE_DB_USER" \
  -e "DROP DATABASE IF EXISTS \`$RESTORE_DB_NAME\`; CREATE DATABASE \`$RESTORE_DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
restore_created=1

mysql --host="$RESTORE_DB_HOST" --port="$RESTORE_DB_PORT" --user="$RESTORE_DB_USER" \
  "$RESTORE_DB_NAME" < "$BACKUP_DIR/database.sql"
unset MYSQL_PWD

export RESTORE_DB_HOST RESTORE_DB_PORT RESTORE_DB_NAME RESTORE_DB_USER RESTORE_DB_PASSWORD
if ! bash -c "$RESTORE_VERIFY_COMMAND"; then
  result_reason="verification_failed"
  exit 1
fi

end_epoch="$(date -u +%s)"
duration_seconds=$(( end_epoch - start_epoch ))
rpo_status="passed"
rto_status="passed"
(( backup_age_seconds <= RPO_SECONDS )) || rpo_status="failed"
(( duration_seconds <= RTO_SECONDS )) || rto_status="failed"

if [[ "$rpo_status" == "failed" || "$rto_status" == "failed" ]]; then
  result_status="failed"
  result_reason="recovery_objective_missed"
  write_report "$result_status" "$result_reason" "$end_epoch"
  report_written=1
  echo "RESTORE_DRILL status=failed reason=$result_reason backup_age_seconds=$backup_age_seconds rpo_seconds=$RPO_SECONDS duration_seconds=$duration_seconds rto_seconds=$RTO_SECONDS"
  exit 1
fi

result_status="passed"
result_reason="verified"
write_report "$result_status" "$result_reason" "$end_epoch"
report_written=1
echo "RESTORE_DRILL status=passed backup_age_seconds=$backup_age_seconds rpo_seconds=$RPO_SECONDS duration_seconds=$duration_seconds rto_seconds=$RTO_SECONDS report=$RESTORE_DRILL_REPORT_FILE"
