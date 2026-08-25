#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/tests/static/php-syntax.sh" "$ROOT"

php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/audit/AuditSanitizerTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/common/CommonTest.php"

if [[ -n "${SMOKE_BASE_URL:-}" ]]; then
  bash "$ROOT/tests/smoke/http-smoke.sh" "$SMOKE_BASE_URL"
fi

echo "TESTS_OK"
