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

mkdir -p "$(dirname "$RESTORE_DRILL_REPORT_FILE")"
umask 077

start_epoch="$(date -u +%s)"
restore_created=0
report_written=0
result_status="failed"
result_reason="preflight_failed"
source_db="unknown"
created_at_epoch="unknown"
backup_age_seconds="unknown"

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
  trap - EXIT
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

# Replace any previous evidence immediately so a stale PASS cannot remain visible
# while a new drill is validating the backup.
write_report "running" "started" "$start_epoch"

fail_drill() {
  local reason="$1"
  local message="$2"
  local code="${3:-1}"
  result_status="failed"
  result_reason="$reason"
  echo "$message" >&2
  exit "$code"
}

checksum_manifest_complete() {
  local dir="$1"
  local sums="$dir/SHA256SUMS"

  grep -Eq '^[[:xdigit:]]{64}[[:space:]][ *]commit\.txt$' "$sums" &&
    grep -Eq '^[[:xdigit:]]{64}[[:space:]][ *]database\.sql$' "$sums"
}

[[ -d "$BACKUP_DIR" ]] || fail_drill "backup_directory_missing" "backup directory not found: $BACKUP_DIR"
[[ -f "$BACKUP_DIR/BACKUP_COMPLETE" ]] || fail_drill "backup_incomplete" "backup is not marked complete"
[[ -f "$BACKUP_DIR/backup-manifest.env" ]] || fail_drill "backup_manifest_missing" "backup manifest missing"
[[ -s "$BACKUP_DIR/database.sql" ]] || fail_drill "database_sql_missing" "database.sql missing or empty"
[[ -f "$BACKUP_DIR/SHA256SUMS" ]] || fail_drill "checksums_missing" "SHA256SUMS missing"

manifest_status="$(awk -F= '$1 == "backup_status" { print $2; exit }' "$BACKUP_DIR/backup-manifest.env")"
source_db="$(awk -F= '$1 == "database_name" { print $2; exit }' "$BACKUP_DIR/backup-manifest.env")"
created_at_epoch="$(awk -F= '$1 == "created_at_epoch" { print $2; exit }' "$BACKUP_DIR/backup-manifest.env")"

[[ "$manifest_status" == "complete" ]] || fail_drill "backup_manifest_incomplete" "backup manifest is not complete"
[[ -n "$source_db" ]] || fail_drill "backup_manifest_invalid" "database_name missing from backup manifest"
[[ "$created_at_epoch" =~ ^[0-9]+$ ]] || fail_drill "backup_manifest_invalid" "created_at_epoch invalid in backup manifest"
[[ "$RESTORE_DB_NAME" != "$source_db" ]] || \
  fail_drill "source_target_match" "restore target must differ from source database: $source_db" 2
(( created_at_epoch <= RESTORE_NOW_EPOCH )) || fail_drill "backup_future_timestamp" "backup timestamp is in the future"

backup_age_seconds=$(( RESTORE_NOW_EPOCH - created_at_epoch ))

if ! checksum_manifest_complete "$BACKUP_DIR"; then
  fail_drill "checksum_manifest_incomplete" "backup checksum manifest does not cover required files"
fi

result_reason="checksum_failed"
if ! (
  cd "$BACKUP_DIR"
  sha256sum --check --strict SHA256SUMS >/dev/null 2>&1
); then
  fail_drill "checksum_failed" "backup checksum validation failed"
fi

export MYSQL_PWD="$RESTORE_DB_PASSWORD"
result_reason="target_exists_check_failed"
if ! existing_target="$(
  mysql --host="$RESTORE_DB_HOST" --port="$RESTORE_DB_PORT" --user="$RESTORE_DB_USER" \
    --batch --skip-column-names \
    -e "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '$RESTORE_DB_NAME';"
)"; then
  unset MYSQL_PWD
  fail_drill "target_exists_check_failed" "could not verify restore target existence"
fi

if [[ -n "$existing_target" ]]; then
  unset MYSQL_PWD
  fail_drill "target_preexisting" "restore target already exists; refusing to modify preexisting database: $RESTORE_DB_NAME" 2
fi

result_reason="target_create_failed"
if ! mysql --host="$RESTORE_DB_HOST" --port="$RESTORE_DB_PORT" --user="$RESTORE_DB_USER" \
  -e "CREATE DATABASE \`$RESTORE_DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"; then
  unset MYSQL_PWD
  fail_drill "target_create_failed" "failed to create isolated restore target"
fi
restore_created=1

result_reason="restore_import_failed"
if ! mysql --host="$RESTORE_DB_HOST" --port="$RESTORE_DB_PORT" --user="$RESTORE_DB_USER" \
  "$RESTORE_DB_NAME" < "$BACKUP_DIR/database.sql"; then
  unset MYSQL_PWD
  fail_drill "restore_import_failed" "failed to import backup into isolated restore target"
fi
unset MYSQL_PWD

export RESTORE_DB_HOST RESTORE_DB_PORT RESTORE_DB_NAME RESTORE_DB_USER RESTORE_DB_PASSWORD
result_reason="verification_failed"
if ! bash -c "$RESTORE_VERIFY_COMMAND"; then
  fail_drill "verification_failed" "restore verification command failed"
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
