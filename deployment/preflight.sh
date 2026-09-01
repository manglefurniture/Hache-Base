#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"

for command in git php curl mysqldump sha256sum realpath; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "PREFLIGHT_FAILED missing command: $command" >&2
    exit 1
  }
done

cd "$APP_ROOT"
git rev-parse --is-inside-work-tree >/dev/null

if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "PREFLIGHT_FAILED working tree is not clean" >&2
  exit 1
fi

[[ -f "$APP_ROOT/tests/run.sh" ]] || { echo "PREFLIGHT_FAILED tests/run.sh missing" >&2; exit 1; }
[[ -f "$APP_ROOT/deployment/backup.sh" ]] || { echo "PREFLIGHT_FAILED backup.sh missing" >&2; exit 1; }

: "${BACKUP_ROOT:?BACKUP_ROOT is required}"
mkdir -p "$BACKUP_ROOT"
[[ -w "$BACKUP_ROOT" ]] || { echo "PREFLIGHT_FAILED backup root is not writable" >&2; exit 1; }

echo "PREFLIGHT_OK"
