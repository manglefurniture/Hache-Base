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

stamp="$(date -u +%Y%m%d-%H%M%S)"
destination="${BACKUP_ROOT%/}/deploy-${stamp}"
mkdir -p "$destination"
chmod 700 "$destination"

cd "$APP_ROOT"
git rev-parse HEAD > "$destination/commit.txt"
git status --porcelain=v1 > "$destination/git-status.txt"

export MYSQL_PWD="$DB_PASSWORD"
mysqldump \
  --host="$DB_HOST" \
  --port="${DB_PORT:-3306}" \
  --user="$DB_USER" \
  --single-transaction \
  --routines --triggers --events \
  --default-character-set=utf8mb4 \
  "$DB_NAME" > "$destination/database.sql"
unset MYSQL_PWD

if [[ -f "$APP_ROOT/.env" ]]; then
  cp "$APP_ROOT/.env" "$destination/env.snapshot"
  chmod 600 "$destination/env.snapshot"
fi

sha256sum "$destination"/commit.txt "$destination"/database.sql > "$destination/SHA256SUMS"

printf '%s\n' "$destination"
echo "BACKUP_OK"
