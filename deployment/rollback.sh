#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"
ROLLBACK_REF="${1:-${ROLLBACK_REF:-}}"
[[ -n "$ROLLBACK_REF" ]] || { echo "Provide a rollback commit/ref" >&2; exit 2; }

cd "$APP_ROOT"

git diff --quiet && git diff --cached --quiet || {
  echo "Refusing rollback: working tree has uncommitted changes" >&2
  exit 1
}

git fetch origin --prune
git rev-parse --verify "${ROLLBACK_REF}^{commit}" >/dev/null

git checkout --detach "$ROLLBACK_REF"

echo "CODE_ROLLBACK_OK $(git rev-parse HEAD)"
echo "Database restoration is intentionally separate; restore only from a verified backup when required by the migration history."
