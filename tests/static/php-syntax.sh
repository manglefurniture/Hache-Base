#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"

command -v php >/dev/null 2>&1 || { echo "php is required" >&2; exit 1; }

status=0
while IFS= read -r -d '' file; do
  if ! php -l "$file" >/dev/null; then
    php -l "$file" || true
    status=1
  fi
done < <(find "$ROOT" -type f -name '*.php' \
  -not -path '*/vendor/*' \
  -not -path '*/node_modules/*' -print0)

if [[ "$status" -ne 0 ]]; then
  echo "PHP_SYNTAX_FAILED" >&2
  exit "$status"
fi

echo "PHP_SYNTAX_OK"
