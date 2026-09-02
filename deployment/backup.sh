#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required}"
: "${DB_HOST:?DB_HOST is required}"
: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }
command -v mysqldump >/dev/null 2>&1 || { echo "mysqldump is required" >&2; exit 1; }
command -v mktemp >/dev/null 2>&1 || { echo "mktemp is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 1; }

stamp="$(date -u +%Y%m%d-%H%M%S)"
created_at_epoch="$(date -u +%s)"
created_at_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"
destination="$(mktemp -d "${BACKUP_ROOT%/}/deploy-${stamp}-XXXXXX")"
chmod 700 "$destination"

cd "$APP_ROOT"
commit="$(git rev-parse HEAD)"
printf '%s\n' "$commit" > "$destination/commit.txt"
git status --porcelain=v1 > "$destination/git-status.txt"

export MYSQL_PWD="$DB_PASSWORD"
if ! mysqldump \
  --host="$DB_HOST" \
  --port="${DB_PORT:-3306}" \
  --user="$DB_USER" \
  --single-transaction \
  --routines --triggers --events \
  --default-character-set=utf8mb4 \
  "$DB_NAME" > "$destination/database.sql"; then
  unset MYSQL_PWD
  echo "BACKUP_FAILED destination=$destination phase=database_dump" >&2
  exit 1
fi
unset MYSQL_PWD

if [[ -f "$APP_ROOT/.env" ]]; then
  cp "$APP_ROOT/.env" "$destination/env.snapshot"
  chmod 600 "$destination/env.snapshot"
fi

(
  cd "$destination"
  sha256sum commit.txt database.sql > SHA256SUMS
)

cat > "$destination/backup-manifest.env" <<EOF
backup_status=complete
created_at_epoch=$created_at_epoch
created_at_utc=$created_at_utc
database_name=$DB_NAME
commit=$commit
EOF
chmod 600 "$destination/backup-manifest.env"
: > "$destination/BACKUP_COMPLETE"
chmod 600 "$destination/BACKUP_COMPLETE"

printf '%s\n' "$destination"
echo "BACKUP_OK created_at_epoch=$created_at_epoch commit=$commit"
