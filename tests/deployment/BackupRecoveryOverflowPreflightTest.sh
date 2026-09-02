#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

make_backup_fixture() {
  local dir="$1"
  local epoch="$2"
  local db_name="$3"

  mkdir -p "$dir"
  printf '%s\n' 'CREATE TABLE recovery_probe (id INT PRIMARY KEY);' > "$dir/database.sql"
  printf '%s\n' 'deadbeef' > "$dir/commit.txt"
  (
    cd "$dir"
    sha256sum commit.txt database.sql > SHA256SUMS
  )
  cat > "$dir/backup-manifest.env" <<EOF
backup_status=complete
created_at_epoch=$epoch
created_at_utc=1970-01-01T00:00:00Z
database_name=$db_name
commit=deadbeef
EOF
  : > "$dir/BACKUP_COMPLETE"
}

HUGE_DECIMAL=18446744073709551616

# Values beyond signed 64-bit arithmetic must never reach Bash arithmetic or be
# masked by an older valid backup.
OVERFLOW_ROOT="$TMP/overflow-backups"
mkdir -p "$OVERFLOW_ROOT"
make_backup_fixture "$OVERFLOW_ROOT/deploy-valid" 900 production_db
make_backup_fixture "$OVERFLOW_ROOT/deploy-overflow" "$HUGE_DECIMAL" production_db

set +e
overflow_output="$(BACKUP_ROOT="$OVERFLOW_ROOT" RPO_SECONDS=2000 BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
overflow_rc=$?
set -e
[[ "$overflow_rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=invalid_backup' <<<"$overflow_output"
grep -q 'reason=invalid_created_at_epoch' <<<"$overflow_output"
! grep -q 'BACKUP_FRESHNESS status=fresh' <<<"$overflow_output"

set +e
huge_rpo_output="$(BACKUP_ROOT="$OVERFLOW_ROOT" RPO_SECONDS="$HUGE_DECIMAL" BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
huge_rpo_rc=$?
set -e
[[ "$huge_rpo_rc" -eq 2 ]]
grep -q 'within Bash arithmetic range' <<<"$huge_rpo_output"

# Provide a harmless mysql stub so restore tests can prove they fail before any
# database operation when manifest/config values are invalid.
fake_bin="$TMP/bin"
mkdir -p "$fake_bin"
mysql_log="$TMP/mysql.log"
cat > "$fake_bin/mysql" <<'MYSQL'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MYSQL_LOG"
exit 0
MYSQL
chmod +x "$fake_bin/mysql"
export MYSQL_LOG="$mysql_log"
export PATH="$fake_bin:$PATH"

restore_report="$TMP/reports/overflow-restore.txt"
printf '%s\n' 'RESTORE_DRILL status=passed reason=stale_evidence' > "$restore_report"
: > "$mysql_log"

set +e
restore_overflow_output="$(
  BACKUP_DIR="$OVERFLOW_ROOT/deploy-overflow" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_overflow_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$restore_report" \
  RPO_SECONDS=2000 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
restore_overflow_rc=$?
set -e
[[ "$restore_overflow_rc" -ne 0 ]]
grep -q 'created_at_epoch invalid in backup manifest' <<<"$restore_overflow_output"
grep -q '^RESTORE_DRILL status=failed reason=backup_manifest_invalid$' "$restore_report"
! grep -q 'stale_evidence' "$restore_report"
[[ ! -s "$mysql_log" ]]

# A failure in configuration preflight must also replace a stale PASS because
# the report/trap is installed before validating RPO/isolation/tooling.
preflight_report="$TMP/reports/preflight.txt"
printf '%s\n' 'RESTORE_DRILL status=passed reason=stale_evidence' > "$preflight_report"

set +e
preflight_output="$(
  BACKUP_DIR="$OVERFLOW_ROOT/deploy-valid" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_preflight_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$preflight_report" \
  RPO_SECONDS=0900 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
preflight_rc=$?
set -e
[[ "$preflight_rc" -eq 2 ]]
grep -q 'RPO_SECONDS must be a positive decimal integer within Bash arithmetic range' <<<"$preflight_output"
grep -q '^RESTORE_DRILL status=failed reason=configuration_invalid$' "$preflight_report"
! grep -q 'stale_evidence' "$preflight_report"

isolation_report="$TMP/reports/isolation-preflight.txt"
printf '%s\n' 'RESTORE_DRILL status=passed reason=stale_evidence' > "$isolation_report"
set +e
isolation_output="$(
  BACKUP_DIR="$OVERFLOW_ROOT/deploy-valid" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_isolation_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=0 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$isolation_report" \
  RPO_SECONDS=2000 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
isolation_rc=$?
set -e
[[ "$isolation_rc" -eq 2 ]]
grep -q 'RESTORE_CONFIRM_ISOLATED=1 is required' <<<"$isolation_output"
grep -q '^RESTORE_DRILL status=failed reason=isolation_not_confirmed$' "$isolation_report"
! grep -q 'stale_evidence' "$isolation_report"

echo "BACKUP_RECOVERY_OVERFLOW_PREFLIGHT_TEST_OK"
