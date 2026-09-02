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
  printf '%s\n' 'CREATE TABLE recovery_probe (id INT PRIMARY KEY); INSERT INTO recovery_probe VALUES (1);' > "$dir/database.sql"
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

# A digit-only epoch with a leading zero is not canonical decimal input for Bash
# arithmetic and must fail instead of being interpreted as octal or masked.
LEADING_ZERO_ROOT="$TMP/leading-zero-backups"
mkdir -p "$LEADING_ZERO_ROOT"
make_backup_fixture "$LEADING_ZERO_ROOT/deploy-valid" 800 production_db
make_backup_fixture "$LEADING_ZERO_ROOT/deploy-leading-zero" 0900 production_db

set +e
leading_zero_output="$(BACKUP_ROOT="$LEADING_ZERO_ROOT" RPO_SECONDS=300 BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
leading_zero_rc=$?
set -e
[[ "$leading_zero_rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=invalid_backup' <<<"$leading_zero_output"
grep -q 'reason=invalid_created_at_epoch' <<<"$leading_zero_output"
! grep -q 'BACKUP_FRESHNESS status=fresh' <<<"$leading_zero_output"

fake_bin="$TMP/bin"
mkdir -p "$fake_bin"
mysql_log="$TMP/mysql.log"
cat > "$fake_bin/mysql" <<'MYSQL'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MYSQL_LOG"

if [[ " $* " == *'INFORMATION_SCHEMA.SCHEMATA'* ]]; then
  exit 0
fi

if [[ -n "${FAKE_DROP_FAIL_DB:-}" && "$*" == *"DROP DATABASE IF EXISTS \`$FAKE_DROP_FAIL_DB\`;"* ]]; then
  exit 1
fi

if [[ " $* " != *' -e '* ]]; then
  cat >/dev/null
fi
MYSQL
chmod +x "$fake_bin/mysql"
export MYSQL_LOG="$mysql_log"
export PATH="$fake_bin:$PATH"

# The restore path uses the same canonical-decimal contract and must fail before
# touching MySQL when the backup manifest contains a leading-zero epoch.
: > "$mysql_log"
leading_zero_report="$TMP/reports/leading-zero-restore.txt"
set +e
leading_zero_restore_output="$(
  BACKUP_DIR="$LEADING_ZERO_ROOT/deploy-leading-zero" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_leading_zero_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$leading_zero_report" \
  RPO_SECONDS=300 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
leading_zero_restore_rc=$?
set -e
[[ "$leading_zero_restore_rc" -ne 0 ]]
grep -q 'created_at_epoch invalid in backup manifest' <<<"$leading_zero_restore_output"
grep -q '^RESTORE_DRILL status=failed reason=backup_manifest_invalid$' "$leading_zero_report"
[[ ! -s "$mysql_log" ]]

# A successful restore/verify is not a PASS when mandatory cleanup fails. The
# report and process exit must both reflect cleanup_failed.
CLEANUP_ROOT="$TMP/cleanup-backup"
make_backup_fixture "$CLEANUP_ROOT" 900 production_db
cleanup_report="$TMP/reports/cleanup-failure.txt"
: > "$mysql_log"

set +e
cleanup_output="$(
  FAKE_DROP_FAIL_DB=restore_cleanup_fail_db \
  BACKUP_DIR="$CLEANUP_ROOT" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_cleanup_fail_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$cleanup_report" \
  RPO_SECONDS=300 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
cleanup_rc=$?
set -e

[[ "$cleanup_rc" -ne 0 ]]
grep -q 'RESTORE_DRILL_WARNING cleanup_failed database=restore_cleanup_fail_db' <<<"$cleanup_output"
grep -q 'RESTORE_DRILL status=failed reason=cleanup_failed' <<<"$cleanup_output"
! grep -q 'RESTORE_DRILL status=passed' <<<"$cleanup_output"
grep -q '^RESTORE_DRILL status=failed reason=cleanup_failed$' "$cleanup_report"
grep -q '^cleanup_status=failed$' "$cleanup_report"
grep -q '^pre_cleanup_reason=verified$' "$cleanup_report"
grep -q 'CREATE DATABASE `restore_cleanup_fail_db`' "$mysql_log"
grep -q 'DROP DATABASE IF EXISTS `restore_cleanup_fail_db`' "$mysql_log"

# Cleanup failure must remain visible even when the drill was already failing
# for another reason, such as an RPO miss. Preserve that prior reason as evidence.
combined_report="$TMP/reports/rpo-and-cleanup-failure.txt"
: > "$mysql_log"

set +e
combined_output="$(
  FAKE_DROP_FAIL_DB=restore_cleanup_rpo_fail_db \
  BACKUP_DIR="$CLEANUP_ROOT" \
  RESTORE_DB_HOST=staging-db \
  RESTORE_DB_NAME=restore_cleanup_rpo_fail_db \
  RESTORE_DB_USER=restore_user \
  RESTORE_DB_PASSWORD=fixture-secret \
  RESTORE_CONFIRM_ISOLATED=1 \
  RESTORE_VERIFY_COMMAND=true \
  RESTORE_DRILL_REPORT_FILE="$combined_report" \
  RPO_SECONDS=50 \
  RTO_SECONDS=30 \
  RESTORE_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/restore-drill.sh" 2>&1
)"
combined_rc=$?
set -e

[[ "$combined_rc" -ne 0 ]]
grep -q 'RESTORE_DRILL status=failed reason=recovery_objective_missed' <<<"$combined_output"
grep -q 'RESTORE_DRILL_WARNING cleanup_failed database=restore_cleanup_rpo_fail_db' <<<"$combined_output"
grep -q 'RESTORE_DRILL status=failed reason=cleanup_failed pre_cleanup_reason=recovery_objective_missed' <<<"$combined_output"
grep -q '^RESTORE_DRILL status=failed reason=cleanup_failed$' "$combined_report"
grep -q '^cleanup_status=failed$' "$combined_report"
grep -q '^pre_cleanup_reason=recovery_objective_missed$' "$combined_report"
grep -q 'DROP DATABASE IF EXISTS `restore_cleanup_rpo_fail_db`' "$mysql_log"

echo "BACKUP_RECOVERY_NUMERIC_CLEANUP_TEST_OK"
