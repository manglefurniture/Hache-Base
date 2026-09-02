#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

make_backup_fixture() {
  local dir="$1"
  local epoch="$2"
  local db_name="$3"
  local status="${4:-complete}"

  mkdir -p "$dir"
  printf '%s\n' 'CREATE TABLE recovery_probe (id INT PRIMARY KEY); INSERT INTO recovery_probe VALUES (1);' > "$dir/database.sql"
  printf '%s\n' 'deadbeef' > "$dir/commit.txt"
  (
    cd "$dir"
    sha256sum commit.txt database.sql > SHA256SUMS
  )
  cat > "$dir/backup-manifest.env" <<EOF
backup_status=$status
created_at_epoch=$epoch
created_at_utc=1970-01-01T00:00:00Z
database_name=$db_name
commit=deadbeef
EOF
  : > "$dir/BACKUP_COMPLETE"
}

BACKUP_ROOT="$TMP/backups"
mkdir -p "$BACKUP_ROOT"
make_backup_fixture "$BACKUP_ROOT/deploy-fresh" 900 production_db

fresh_output="$(BACKUP_ROOT="$BACKUP_ROOT" RPO_SECONDS=200 BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh")"
grep -q 'BACKUP_FRESHNESS status=fresh' <<<"$fresh_output"
grep -q 'age_seconds=100' <<<"$fresh_output"

alert_log="$TMP/alert.log"
alert_hook="$TMP/alert-hook.sh"
cat > "$alert_hook" <<'HOOK'
#!/usr/bin/env bash
printf '%s|%s|%s|%s\n' "$1" "$2" "$3" "$4" >> "$ALERT_LOG"
HOOK
chmod +x "$alert_hook"
export ALERT_LOG="$alert_log"

set +e
stale_output="$(BACKUP_ROOT="$BACKUP_ROOT" RPO_SECONDS=50 BACKUP_CHECK_NOW_EPOCH=1000 \
  BACKUP_ALERT_COMMAND="$alert_hook" bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
stale_rc=$?
set -e
[[ "$stale_rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=stale' <<<"$stale_output"
grep -q '^stale|' "$alert_log"

INVALID_ROOT="$TMP/invalid-backups"
mkdir -p "$INVALID_ROOT"
make_backup_fixture "$INVALID_ROOT/deploy-valid" 900 production_db
make_backup_fixture "$INVALID_ROOT/deploy-corrupt" 950 production_db
printf '%s\n' '-- corruption after checksum' >> "$INVALID_ROOT/deploy-corrupt/database.sql"

set +e
invalid_output="$(BACKUP_ROOT="$INVALID_ROOT" RPO_SECONDS=200 BACKUP_CHECK_NOW_EPOCH=1000 \
  BACKUP_ALERT_COMMAND="$alert_hook" bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
invalid_rc=$?
set -e
[[ "$invalid_rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=invalid_backup' <<<"$invalid_output"
grep -q 'reason=checksum_failed' <<<"$invalid_output"
grep -q '^invalid_backup|' "$alert_log"

FAILED_ROOT="$TMP/failed-manifest-backups"
mkdir -p "$FAILED_ROOT"
make_backup_fixture "$FAILED_ROOT/deploy-failed" 950 production_db failed

set +e
failed_manifest_output="$(BACKUP_ROOT="$FAILED_ROOT" RPO_SECONDS=200 BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
failed_manifest_rc=$?
set -e
[[ "$failed_manifest_rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=invalid_backup' <<<"$failed_manifest_output"
grep -q 'reason=manifest_status' <<<"$failed_manifest_output"

mkdir -p "$TMP/empty-backups"
set +e
missing_output="$(BACKUP_ROOT="$TMP/empty-backups" RPO_SECONDS=50 BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
missing_rc=$?
set -e
[[ "$missing_rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=missing' <<<"$missing_output"

REAL_SHA256SUM="$(command -v sha256sum)"
export REAL_SHA256SUM

fake_bin="$TMP/bin"
mkdir -p "$fake_bin"
mysql_log="$TMP/mysql.log"
cat > "$fake_bin/mysql" <<'MYSQL'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MYSQL_LOG"

if [[ " $* " == *'INFORMATION_SCHEMA.SCHEMATA'* ]]; then
  if [[ -n "${FAKE_EXISTING_DB:-}" && "$*" == *"SCHEMA_NAME = '$FAKE_EXISTING_DB'"* ]]; then
    printf '%s\n' "$FAKE_EXISTING_DB"
  fi
  exit 0
fi

if [[ " $* " != *' -e '* ]]; then
  cat >/dev/null
fi
MYSQL
chmod +x "$fake_bin/mysql"

cat > "$fake_bin/sha256sum" <<'SHA'
#!/usr/bin/env bash
if [[ -n "${SHA256_DELAY_SECONDS:-}" ]]; then
  sleep "$SHA256_DELAY_SECONDS"
fi
exec "$REAL_SHA256SUM" "$@"
SHA
chmod +x "$fake_bin/sha256sum"

export MYSQL_LOG="$mysql_log"
export PATH="$fake_bin:$PATH"

verify_file="$TMP/verified.txt"
export VERIFY_FILE="$verify_file"
report_file="$TMP/reports/restore.txt"

restore_output="$(
  BACKUP_DIR="$BACKUP_ROOT/deploy-fresh" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_drill_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND='printf "verified\n" > "$VERIFY_FILE"' \
  RESTORE_DRILL_REPORT_FILE="$report_file" \
  RPO_SECONDS=200 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh"
)"
grep -q 'RESTORE_DRILL status=passed' <<<"$restore_output"
grep -q '^RESTORE_DRILL status=passed reason=verified$' "$report_file"
grep -q '^backup_age_seconds=100$' "$report_file"
grep -q '^rpo_seconds=200$' "$report_file"
[[ -f "$verify_file" ]]
grep -q 'INFORMATION_SCHEMA.SCHEMATA' "$mysql_log"
grep -q 'CREATE DATABASE `restore_drill_db`' "$mysql_log"
grep -q 'DROP DATABASE IF EXISTS `restore_drill_db`' "$mysql_log"

: > "$mysql_log"
set +e
same_db_output="$(
  BACKUP_DIR="$BACKUP_ROOT/deploy-fresh" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=production_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$TMP/reports/same-db.txt" \
  RPO_SECONDS=200 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
same_db_rc=$?
set -e
[[ "$same_db_rc" -ne 0 ]]
grep -q 'restore target must differ from source database' <<<"$same_db_output"
[[ ! -s "$mysql_log" ]]

: > "$mysql_log"
preexisting_report="$TMP/reports/preexisting.txt"
export FAKE_EXISTING_DB=preexisting_db
set +e
preexisting_output="$(
  BACKUP_DIR="$BACKUP_ROOT/deploy-fresh" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=preexisting_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$preexisting_report" \
  RPO_SECONDS=200 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
preexisting_rc=$?
set -e
unset FAKE_EXISTING_DB
[[ "$preexisting_rc" -ne 0 ]]
grep -q 'restore target already exists' <<<"$preexisting_output"
grep -q '^RESTORE_DRILL status=failed reason=target_preexisting$' "$preexisting_report"
grep -q 'INFORMATION_SCHEMA.SCHEMATA' "$mysql_log"
! grep -q 'CREATE DATABASE `preexisting_db`' "$mysql_log"
! grep -q 'DROP DATABASE IF EXISTS `preexisting_db`' "$mysql_log"

CORRUPT_RESTORE="$TMP/corrupt-restore"
make_backup_fixture "$CORRUPT_RESTORE" 900 production_db
printf '%s\n' '-- corrupted after checksum' >> "$CORRUPT_RESTORE/database.sql"

: > "$mysql_log"
checksum_report="$TMP/reports/checksum-failure.txt"
printf '%s\n' 'RESTORE_DRILL status=passed reason=stale_evidence' > "$checksum_report"
set +e
checksum_output="$(
  BACKUP_DIR="$CORRUPT_RESTORE" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_checksum_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$checksum_report" \
  RPO_SECONDS=200 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
checksum_rc=$?
set -e
[[ "$checksum_rc" -ne 0 ]]
grep -q 'backup checksum validation failed' <<<"$checksum_output"
grep -q '^RESTORE_DRILL status=failed reason=checksum_failed$' "$checksum_report"
[[ ! -s "$mysql_log" ]]

stale_report="$TMP/reports/stale-restore.txt"
set +e
stale_restore_output="$(
  BACKUP_DIR="$BACKUP_ROOT/deploy-fresh" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_stale_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$stale_report" \
  RPO_SECONDS=50 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
stale_restore_rc=$?
set -e
[[ "$stale_restore_rc" -ne 0 ]]
grep -q 'RESTORE_DRILL status=failed reason=recovery_objective_missed' <<<"$stale_restore_output"
grep -q '^RESTORE_DRILL status=failed reason=recovery_objective_missed$' "$stale_report"

rto_report="$TMP/reports/rto-restore.txt"
set +e
rto_restore_output="$(
  SHA256_DELAY_SECONDS=2 \
  BACKUP_DIR="$BACKUP_ROOT/deploy-fresh" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_rto_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$rto_report" \
  RPO_SECONDS=200 \
  RTO_SECONDS=1 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
rto_restore_rc=$?
set -e
[[ "$rto_restore_rc" -ne 0 ]]
grep -q 'RESTORE_DRILL status=failed reason=recovery_objective_missed' <<<"$rto_restore_output"
grep -q '^RESTORE_DRILL status=failed reason=recovery_objective_missed$' "$rto_report"
duration="$(awk -F= '$1 == "restore_duration_seconds" { print $2; exit }' "$rto_report")"
[[ "$duration" =~ ^[0-9]+$ ]]
(( duration >= 2 ))

echo "BACKUP_RECOVERY_TEST_OK"
