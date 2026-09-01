#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
  echo "DEPLOY_RUNNER_TEST_FAILED: $*" >&2
  exit 1
}

assert_contains() {
  local file="$1"
  local text="$2"
  grep -F -- "$text" "$file" >/dev/null || fail "expected '$text' in $file"
}

make_fixture() {
  local name="$1"
  APP="$TMP/$name-app"
  ORIGIN="$TMP/$name-origin.git"

  git init -q --bare "$ORIGIN"
  git init -q "$APP"
  git -C "$APP" config user.email "fixture@example.test"
  git -C "$APP" config user.name "Deploy Fixture"
  git -C "$APP" remote add origin "$ORIGIN"

  mkdir -p "$APP/deployment" "$APP/tests/smoke"
  cp "$ROOT/deployment/deploy.sh" "$APP/deployment/deploy.sh"
  cp "$ROOT/deployment/rollback.sh" "$APP/deployment/rollback.sh"
  cp "$ROOT/deployment/mark-deploy-recovery.sh" "$APP/deployment/mark-deploy-recovery.sh"
  cp "$ROOT/deployment/DEPLOY-FAILURE-RUNBOOK.md" "$APP/deployment/DEPLOY-FAILURE-RUNBOOK.md"

  cat > "$APP/deployment/preflight.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
echo "PREFLIGHT_OK"
SH

  cat > "$APP/deployment/backup.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
echo "BACKUP_OK"
SH

  cat > "$APP/deployment/health-check.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
: "${HEALTH_COUNT_FILE:?HEALTH_COUNT_FILE is required}"
count=0
[[ -f "$HEALTH_COUNT_FILE" ]] && count="$(cat "$HEALTH_COUNT_FILE")"
printf '%s\n' "$((count + 1))" > "$HEALTH_COUNT_FILE"
echo "HEALTHCHECK_OK"
SH

  cat > "$APP/tests/smoke/http-smoke.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
: "${SMOKE_COUNT_FILE:?SMOKE_COUNT_FILE is required}"
count=0
[[ -f "$SMOKE_COUNT_FILE" ]] && count="$(cat "$SMOKE_COUNT_FILE")"
printf '%s\n' "$((count + 1))" > "$SMOKE_COUNT_FILE"
echo "SMOKE_OK"
SH

  echo "before" > "$APP/version.txt"
  git -C "$APP" add .
  git -C "$APP" commit -q -m "fixture previous"
  PREVIOUS="$(git -C "$APP" rev-parse HEAD)"
  git -C "$APP" push -q origin HEAD:refs/heads/main

  echo "after" > "$APP/version.txt"
  git -C "$APP" add version.txt
  git -C "$APP" commit -q -m "fixture target"
  TARGET="$(git -C "$APP" rev-parse HEAD)"
  git -C "$APP" push -q origin HEAD:refs/heads/main
  git -C "$APP" checkout -q --detach "$PREVIOUS"
}

# Success path: canonical phases, smoke and the end-of-window recheck are recorded.
make_fixture success
SUCCESS_OUT="$TMP/success.out"
SUCCESS_RECORD_ROOT="$TMP/success-records"
HEALTH_COUNT_FILE="$TMP/success-health-count"
SMOKE_COUNT_FILE="$TMP/success-smoke-count"

APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/success-backups" \
DEPLOY_RECORD_ROOT="$SUCCESS_RECORD_ROOT" \
HEALTH_COUNT_FILE="$HEALTH_COUNT_FILE" \
SMOKE_COUNT_FILE="$SMOKE_COUNT_FILE" \
MIGRATION_COMMAND='echo MIGRATION_OK' \
TEST_COMMAND='echo TEST_OK' \
SMOKE_BASE_URL='http://fixture.invalid' \
REQUIRE_SMOKE=1 \
OBSERVATION_SECONDS=0.01 \
REQUIRE_OBSERVATION=1 \
bash "$APP/deployment/deploy.sh" >"$SUCCESS_OUT" 2>&1

assert_contains "$SUCCESS_OUT" "DEPLOY_OK $TARGET"
assert_contains "$SUCCESS_OUT" "DEPLOY_OBSERVATION status=passed seconds=0.01"
[[ "$(cat "$HEALTH_COUNT_FILE")" == "2" ]] || fail "readiness must run before and after observation"
[[ "$(cat "$SMOKE_COUNT_FILE")" == "2" ]] || fail "smoke must run before and after observation"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$TARGET" ]] || fail "successful deploy must leave target commit active"

SUCCESS_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$SUCCESS_OUT" | tail -n1)"
[[ -f "$SUCCESS_RECORD" ]] || fail "success deploy record missing"
EXPECTED_STATES=$'started\ncode_changed\nmigrations_applied\ntests_passed\nhealthy'
ACTUAL_STATES="$(sed -n 's/.* state=\([^ ]*\).*/\1/p' "$SUCCESS_RECORD")"
[[ "$ACTUAL_STATES" == "$EXPECTED_STATES" ]] || fail "unexpected success states: $ACTUAL_STATES"
assert_contains "$SUCCESS_RECORD" "state=migrations_applied status=passed"

ROLLBACK_REF="$(sed -n 's/^ROLLBACK_REF=//p' "$SUCCESS_OUT" | tail -n1)"
[[ -n "$ROLLBACK_REF" ]] || fail "rollback ref missing"
DEPLOY_RECORD_FILE="$SUCCESS_RECORD" APP_ROOT="$APP" bash "$APP/deployment/rollback.sh" "$ROLLBACK_REF" >"$TMP/rollback.out" 2>&1
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "rollback must restore previous code commit"
assert_contains "$SUCCESS_RECORD" "state=rolled_back status=passed"

# Failure path: partial deploy remains visible and manual recovery can close the record explicitly.
make_fixture failure
FAIL_OUT="$TMP/failure.out"
FAIL_RECORD_ROOT="$TMP/failure-records"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/failure-backups" \
DEPLOY_RECORD_ROOT="$FAIL_RECORD_ROOT" \
TEST_COMMAND='exit 9' \
OBSERVATION_SECONDS=0 \
bash "$APP/deployment/deploy.sh" >"$FAIL_OUT" 2>&1
FAIL_CODE=$?
set -e

[[ "$FAIL_CODE" == "9" ]] || fail "failed test phase must preserve exit code 9, got $FAIL_CODE"
assert_contains "$FAIL_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=tests exit_code=9"
FAIL_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$FAIL_OUT" | tail -n1)"
[[ -f "$FAIL_RECORD" ]] || fail "failure deploy record missing"
assert_contains "$FAIL_RECORD" "state=code_changed status=passed"
assert_contains "$FAIL_RECORD" "state=migrations_applied status=not_applicable"
assert_contains "$FAIL_RECORD" "state=failed status=failed"
assert_contains "$FAIL_RECORD" "failed_phase=tests;exit_code=9"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$TARGET" ]] || fail "runner must not perform an unsafe automatic rollback"

DEPLOY_RECORD_FILE="$FAIL_RECORD" APP_ROOT="$APP" bash "$APP/deployment/mark-deploy-recovery.sh" manual_recovery operator_verified_fix >"$TMP/manual.out"
assert_contains "$FAIL_RECORD" "state=manual_recovery status=passed"
assert_contains "$FAIL_RECORD" "detail=operator_verified_fix"

# Required smoke must fail before code changes when no smoke contract is configured.
make_fixture smoke-required
SMOKE_REQUIRED_OUT="$TMP/smoke-required.out"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/smoke-required-backups" \
REQUIRE_SMOKE=1 \
bash "$APP/deployment/deploy.sh" >"$SMOKE_REQUIRED_OUT" 2>&1
SMOKE_REQUIRED_CODE=$?
set -e

[[ "$SMOKE_REQUIRED_CODE" != "0" ]] || fail "required smoke without configuration must fail"
assert_contains "$SMOKE_REQUIRED_OUT" "DEPLOY_CONFIG_FAILED smoke is required"
assert_contains "$SMOKE_REQUIRED_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=started"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "configuration failure must happen before code change"

echo "DEPLOY_RUNNER_OK"
