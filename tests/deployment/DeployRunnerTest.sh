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
if [[ "${FAIL_BACKUP:-0}" == "1" ]]; then
  echo "BACKUP_FAILED fixture" >&2
  exit 7
fi
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
assert_contains "$SUCCESS_OUT" "gate=observation status=passed"
[[ "$(cat "$HEALTH_COUNT_FILE")" == "2" ]] || fail "readiness must run before and after observation"
[[ "$(cat "$SMOKE_COUNT_FILE")" == "2" ]] || fail "smoke must run before and after observation"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$TARGET" ]] || fail "successful deploy must leave target commit active"

SUCCESS_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$SUCCESS_OUT" | tail -n1)"
[[ -f "$SUCCESS_RECORD" ]] || fail "success deploy record missing"
EXPECTED_STATES=$'started\ncode_changed\nmigrations_applied\ntests_passed\nhealthy'
ACTUAL_STATES="$(sed -n 's/.* state=\([^ ]*\).*/\1/p' "$SUCCESS_RECORD")"
[[ "$ACTUAL_STATES" == "$EXPECTED_STATES" ]] || fail "unexpected success states: $ACTUAL_STATES"
assert_contains "$SUCCESS_RECORD" "state=migrations_applied status=passed"
assert_contains "$SUCCESS_RECORD" "gate=readiness status=passed"
assert_contains "$SUCCESS_RECORD" "gate=smoke status=passed"
assert_contains "$SUCCESS_RECORD" "gate=observation status=passed"

ROLLBACK_REF="$(sed -n 's/^ROLLBACK_REF=//p' "$SUCCESS_OUT" | tail -n1)"
[[ -n "$ROLLBACK_REF" ]] || fail "rollback ref missing"
DEPLOY_RECORD_FILE="$SUCCESS_RECORD" APP_ROOT="$APP" bash "$APP/deployment/rollback.sh" "$ROLLBACK_REF" >"$TMP/rollback.out" 2>&1
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "rollback must restore previous code commit"
assert_contains "$SUCCESS_RECORD" "state=rolled_back status=passed"

# Backward-compatible defaults stay visible as NOT_EVALUATED in the persistent record.
make_fixture optional-gates
OPTIONAL_OUT="$TMP/optional-gates.out"
OPTIONAL_HEALTH_COUNT="$TMP/optional-health-count"
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/optional-backups" \
DEPLOY_RECORD_ROOT="$TMP/optional-records" \
HEALTH_COUNT_FILE="$OPTIONAL_HEALTH_COUNT" \
TEST_COMMAND='echo TEST_OK' \
bash "$APP/deployment/deploy.sh" >"$OPTIONAL_OUT" 2>&1

OPTIONAL_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$OPTIONAL_OUT" | tail -n1)"
[[ -f "$OPTIONAL_RECORD" ]] || fail "optional-gates deploy record missing"
assert_contains "$OPTIONAL_RECORD" "gate=smoke status=not_evaluated"
assert_contains "$OPTIONAL_RECORD" "gate=observation status=not_evaluated"
assert_contains "$OPTIONAL_RECORD" "evidence=NOT_EVALUATED"
assert_contains "$OPTIONAL_RECORD" "state=healthy status=passed"

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

# Backup failure is named precisely and happens before the target code is activated.
make_fixture backup-failure
BACKUP_FAIL_OUT="$TMP/backup-failure.out"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/backup-failure-backups" \
DEPLOY_RECORD_ROOT="$TMP/backup-failure-records" \
FAIL_BACKUP=1 \
bash "$APP/deployment/deploy.sh" >"$BACKUP_FAIL_OUT" 2>&1
BACKUP_FAIL_CODE=$?
set -e

[[ "$BACKUP_FAIL_CODE" == "7" ]] || fail "backup failure must preserve exit code 7, got $BACKUP_FAIL_CODE"
assert_contains "$BACKUP_FAIL_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=backup exit_code=7"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "backup failure must happen before code change"
BACKUP_FAIL_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$BACKUP_FAIL_OUT" | tail -n1)"
[[ -f "$BACKUP_FAIL_RECORD" ]] || fail "backup failure record missing"
assert_contains "$BACKUP_FAIL_RECORD" "state=failed status=failed"
assert_contains "$BACKUP_FAIL_RECORD" "failed_phase=backup;exit_code=7"

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
assert_contains "$SMOKE_REQUIRED_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=configuration"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "configuration failure must happen before code change"

# Deploy evidence must never be created inside the application working tree.
make_fixture record-inside
RECORD_INSIDE_OUT="$TMP/record-inside.out"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/record-inside-backups" \
DEPLOY_RECORD_ROOT="$APP/.deploy-records" \
bash "$APP/deployment/deploy.sh" >"$RECORD_INSIDE_OUT" 2>&1
RECORD_INSIDE_CODE=$?
set -e

[[ "$RECORD_INSIDE_CODE" != "0" ]] || fail "record root inside working tree must fail"
assert_contains "$RECORD_INSIDE_OUT" "DEPLOY_CONFIG_FAILED DEPLOY_RECORD_ROOT must be outside APP_ROOT"
assert_contains "$RECORD_INSIDE_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=configuration"
[[ ! -e "$APP/.deploy-records" ]] || fail "rejected record root must not be created inside working tree"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "record-root validation must happen before code change"
[[ -z "$(git -C "$APP" status --porcelain=v1)" ]] || fail "record-root validation must leave working tree clean"

echo "DEPLOY_RUNNER_OK"
