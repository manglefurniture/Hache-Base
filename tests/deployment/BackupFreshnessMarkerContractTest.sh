#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BACKUP_ROOT="$TMP/backups"
mkdir -p "$BACKUP_ROOT/deploy-valid" "$BACKUP_ROOT/deploy-marker-only"

printf '%s\n' 'CREATE TABLE t (id INT PRIMARY KEY);' > "$BACKUP_ROOT/deploy-valid/database.sql"
printf '%s\n' 'deadbeef' > "$BACKUP_ROOT/deploy-valid/commit.txt"
(
  cd "$BACKUP_ROOT/deploy-valid"
  sha256sum commit.txt database.sql > SHA256SUMS
)
cat > "$BACKUP_ROOT/deploy-valid/backup-manifest.env" <<'EOF'
backup_status=complete
created_at_epoch=900
created_at_utc=1970-01-01T00:00:00Z
database_name=production_db
commit=deadbeef
EOF
: > "$BACKUP_ROOT/deploy-valid/BACKUP_COMPLETE"

# A completion marker without its manifest is inconsistent evidence. It must not
# be ignored in favor of the older valid backup.
: > "$BACKUP_ROOT/deploy-marker-only/BACKUP_COMPLETE"

set +e
output="$(BACKUP_ROOT="$BACKUP_ROOT" RPO_SECONDS=200 BACKUP_CHECK_NOW_EPOCH=1000 \
  bash "$ROOT/deployment/backup-freshness-check.sh" 2>&1)"
rc=$?
set -e

[[ "$rc" -ne 0 ]]
grep -q 'BACKUP_FRESHNESS status=invalid_backup' <<<"$output"
grep -q 'reason=missing_manifest' <<<"$output"
grep -q 'deploy-marker-only' <<<"$output"

if grep -q 'BACKUP_FRESHNESS status=fresh' <<<"$output"; then
  echo "marker-only backup was incorrectly masked by older valid evidence" >&2
  exit 1
fi

echo "BACKUP_FRESHNESS_MARKER_CONTRACT_TEST_OK"
