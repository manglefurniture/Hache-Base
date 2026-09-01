#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/tests/static/php-syntax.sh" "$ROOT"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/static/ProductionReadinessDocsTest.php"
bash "$ROOT/tests/ui/backend-relief.sh"
node "$ROOT/tests/ui/design-system.mjs"
node "$ROOT/tests/ui/design-system-review-regressions.mjs"
node "$ROOT/tests/ui/reuse-hardening-regression.mjs"

php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/audit/AuditSanitizerTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/common/CommonTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/common/DateRangeStateTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/common/AsyncOperationStateTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/integration/AsyncPersistenceContractTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/integration/ResendMailerTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/integration/WebhookHmacTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/integration/CredentialCipherTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/security/ProductionReadinessCoreTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/security/StructuredLoggerStandaloneTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/security/HeadersTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/security/SessionSecurityTest.php"
php -d zend.assertions=1 -d assert.exception=1 "$ROOT/tests/security/SessionCookieDomainValidationTest.php"
bash "$ROOT/tests/deployment/HealthCheckTest.sh"

if [[ -n "${SMOKE_BASE_URL:-}" ]]; then
  bash "$ROOT/tests/smoke/http-smoke.sh" "$SMOKE_BASE_URL"
fi

echo "TESTS_OK"
