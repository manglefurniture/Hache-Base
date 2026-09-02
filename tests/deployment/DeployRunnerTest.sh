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

assert_not_contains() {
  local file="$1"
  local text="$2"
  if grep -F -- "$text" "$file" >/dev/null; then
    fail "did not expect '$text' in $file"
  fi
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
next="$((count + 1))"
printf '%s\n' "$next" > "$HEALTH_COUNT_FILE"
if [[ "${FAIL_HEALTH_ON_COUNT:-0}" == "$next" ]]; then
  echo "HEALTHCHECK_FAILED fixture count=$next" >&2
  exit 8
fi
echo "HEALTHCHECK_OK"
SH

  cat > "$APP/tests/smoke/http-smoke.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
: "${SMOKE_COUNT_FILE:?SMOKE_COUNT_FILE is required}"
count=0
[[ -f "$SMOKE_COUNT_FILE" ]] && count="$(cat "$SMOKE_COUNT_FILE")"
next="$((count + 1))"
printf '%s\n' "$next" > "$SMOKE_COUNT_FILE"
if [[ "${FAIL_SMOKE_ON_COUNT:-0}" == "$next" ]]; then
  echo "SMOKE_FAILED fixture count=$next" >&2
  exit 6
fi
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

make_monorepo_fixture() {
  local name="$1"
  MONOREPO_ROOT="$TMP/$name-monorepo"
  APP="$MONOREPO_ROOT/app"
  ORIGIN="$TMP/$name-origin.git"

  git init -q --bare "$ORIGIN"
  git init -q "$MONOREPO_ROOT"
  git -C "$MONOREPO_ROOT" config user.email "fixture@example.test"
  git -C "$MONOREPO_ROOT" config user.name "Deploy Fixture"
  git -C "$MONOREPO_ROOT" remote add origin "$ORIGIN"

  mkdir -p "$APP/deployment"
  cp "$ROOT/deployment/deploy.sh" "$APP/deployment/deploy.sh"
  echo "before" > "$APP/version.txt"
  git -C "$MONOREPO_ROOT" add .
  git -C "$MONOREPO_ROOT" commit -q -m "fixture previous"
  PREVIOUS="$(git -C "$MONOREPO_ROOT" rev-parse HEAD)"
  git -C "$MONOREPO_ROOT" push -q origin HEAD:refs/heads/main

  echo "after" > "$APP/version.txt"
  git -C "$MONOREPO_ROOT" add app/version.txt
  git -C "$MONOREPO_ROOT" commit -q -m "fixture target"
  TARGET="$(git -C "$MONOREPO_ROOT" rev-parse HEAD)"
  git -C "$MONOREPO_ROOT" push -q origin HEAD:refs/heads/main
  git -C "$MONOREPO_ROOT" checkout -q --detach "$PREVIOUS"
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
assert_contains "$SUCCESS_RECORD" "event=code_rollback status=passed"
assert_contains "$SUCCESS_RECORD" "recovery_state=pending_verification"
assert_not_contains "$SUCCESS_RECORD" "state=rolled_back status=passed"
DEPLOY_RECORD_FILE="$SUCCESS_RECORD" APP_ROOT="$APP" ROLLBACK_REF="$ROLLBACK_REF" bash "$APP/deployment/mark-deploy-recovery.sh" rolled_back post_recovery_gates_verified >"$TMP/rollback-verified.out" 2>&1
assert_contains "$SUCCESS_RECORD" "state=rolled_back status=passed"
assert_contains "$SUCCESS_RECORD" "detail=post_recovery_gates_verified"

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

# A readiness failure after an initial pass must be persisted before the runner exits.
make_fixture readiness-failure
READINESS_FAIL_OUT="$TMP/readiness-failure.out"
READINESS_HEALTH_COUNT="$TMP/readiness-failure-health-count"
READINESS_SMOKE_COUNT="$TMP/readiness-failure-smoke-count"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/readiness-failure-backups" \
DEPLOY_RECORD_ROOT="$TMP/readiness-failure-records" \
HEALTH_COUNT_FILE="$READINESS_HEALTH_COUNT" \
SMOKE_COUNT_FILE="$READINESS_SMOKE_COUNT" \
FAIL_HEALTH_ON_COUNT=2 \
TEST_COMMAND='echo TEST_OK' \
SMOKE_BASE_URL='http://fixture.invalid' \
REQUIRE_SMOKE=1 \
OBSERVATION_SECONDS=0.01 \
REQUIRE_OBSERVATION=1 \
bash "$APP/deployment/deploy.sh" >"$READINESS_FAIL_OUT" 2>&1
READINESS_FAIL_CODE=$?
set -e

[[ "$READINESS_FAIL_CODE" == "8" ]] || fail "second readiness failure must preserve exit code 8, got $READINESS_FAIL_CODE"
READINESS_FAIL_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$READINESS_FAIL_OUT" | tail -n1)"
[[ -f "$READINESS_FAIL_RECORD" ]] || fail "readiness failure record missing"
assert_contains "$READINESS_FAIL_RECORD" "gate=readiness status=passed"
assert_contains "$READINESS_FAIL_RECORD" "gate=readiness status=failed"
LATEST_READINESS="$(grep -F 'gate=readiness' "$READINESS_FAIL_RECORD" | tail -n1)"
[[ "$LATEST_READINESS" == *"status=failed"* ]] || fail "latest readiness result must be failed: $LATEST_READINESS"
assert_contains "$READINESS_FAIL_RECORD" "failed_phase=readiness;exit_code=8"
assert_not_contains "$READINESS_FAIL_RECORD" "state=healthy status=passed"

# A smoke failure after an initial pass must also replace stale success evidence.
make_fixture smoke-failure
SMOKE_FAIL_OUT="$TMP/smoke-failure.out"
SMOKE_FAIL_HEALTH_COUNT="$TMP/smoke-failure-health-count"
SMOKE_FAIL_COUNT="$TMP/smoke-failure-smoke-count"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/smoke-failure-backups" \
DEPLOY_RECORD_ROOT="$TMP/smoke-failure-records" \
HEALTH_COUNT_FILE="$SMOKE_FAIL_HEALTH_COUNT" \
SMOKE_COUNT_FILE="$SMOKE_FAIL_COUNT" \
FAIL_SMOKE_ON_COUNT=2 \
TEST_COMMAND='echo TEST_OK' \
SMOKE_BASE_URL='http://fixture.invalid' \
REQUIRE_SMOKE=1 \
OBSERVATION_SECONDS=0.01 \
REQUIRE_OBSERVATION=1 \
bash "$APP/deployment/deploy.sh" >"$SMOKE_FAIL_OUT" 2>&1
SMOKE_FAIL_CODE=$?
set -e

[[ "$SMOKE_FAIL_CODE" == "6" ]] || fail "second smoke failure must preserve exit code 6, got $SMOKE_FAIL_CODE"
SMOKE_FAIL_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$SMOKE_FAIL_OUT" | tail -n1)"
[[ -f "$SMOKE_FAIL_RECORD" ]] || fail "smoke failure record missing"
assert_contains "$SMOKE_FAIL_RECORD" "gate=smoke status=passed"
assert_contains "$SMOKE_FAIL_RECORD" "gate=smoke status=failed"
LATEST_SMOKE="$(grep -F 'gate=smoke' "$SMOKE_FAIL_RECORD" | tail -n1)"
[[ "$LATEST_SMOKE" == *"status=failed"* ]] || fail "latest smoke result must be failed: $LATEST_SMOKE"
assert_contains "$SMOKE_FAIL_RECORD" "failed_phase=smoke;exit_code=6"
assert_not_contains "$SMOKE_FAIL_RECORD" "state=healthy status=passed"

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

# Deploy evidence must never be created anywhere inside the Git working tree.
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
assert_contains "$RECORD_INSIDE_OUT" "DEPLOY_CONFIG_FAILED DEPLOY_RECORD_ROOT must be outside the Git working tree"
assert_contains "$RECORD_INSIDE_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=configuration"
[[ ! -e "$APP/.deploy-records" ]] || fail "rejected record root must not be created inside working tree"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "record-root validation must happen before code change"
[[ -z "$(git -C "$APP" status --porcelain=v1)" ]] || fail "record-root validation must leave working tree clean"

# APP_ROOT may be a monorepo subdirectory; sibling directories are still inside the Git working tree.
make_monorepo_fixture monorepo-record
MONOREPO_OUT="$TMP/monorepo-record.out"
MONOREPO_RECORD_ROOT="$MONOREPO_ROOT/deploy-records"
set +e
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/monorepo-backups" \
DEPLOY_RECORD_ROOT="$MONOREPO_RECORD_ROOT" \
bash "$APP/deployment/deploy.sh" >"$MONOREPO_OUT" 2>&1
MONOREPO_CODE=$?
set -e

[[ "$MONOREPO_CODE" != "0" ]] || fail "record root in monorepo sibling must fail"
assert_contains "$MONOREPO_OUT" "DEPLOY_CONFIG_FAILED DEPLOY_RECORD_ROOT must be outside the Git working tree"
assert_contains "$MONOREPO_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=configuration"
[[ ! -e "$MONOREPO_RECORD_ROOT" ]] || fail "rejected monorepo sibling record root must not be created"
[[ "$(git -C "$MONOREPO_ROOT" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "monorepo validation must happen before code change"
[[ -z "$(git -C "$MONOREPO_ROOT" status --porcelain=v1)" ]] || fail "monorepo validation must leave whole working tree clean"

echo "DEPLOY_RUNNER_OK"
