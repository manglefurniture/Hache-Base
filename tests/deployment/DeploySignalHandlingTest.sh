#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
  echo "DEPLOY_SIGNAL_HANDLING_TEST_FAILED: $*" >&2
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
  cp "$ROOT/deployment/DEPLOY-FAILURE-RUNBOOK.md" "$APP/deployment/DEPLOY-FAILURE-RUNBOOK.md"

  cat > "$APP/deployment/preflight.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
echo PREFLIGHT_OK
SH
  cat > "$APP/deployment/backup.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
echo BACKUP_OK
SH
  cat > "$APP/deployment/health-check.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
echo HEALTHCHECK_OK
SH
  cat > "$APP/tests/smoke/http-smoke.sh" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
echo SMOKE_OK
SH

  echo before > "$APP/version.txt"
  git -C "$APP" add .
  git -C "$APP" commit -q -m "fixture previous"
  PREVIOUS="$(git -C "$APP" rev-parse HEAD)"
  git -C "$APP" push -q origin HEAD:refs/heads/main

  echo after > "$APP/version.txt"
  git -C "$APP" add version.txt
  git -C "$APP" commit -q -m "fixture target"
  TARGET="$(git -C "$APP" rev-parse HEAD)"
  git -C "$APP" push -q origin HEAD:refs/heads/main
  git -C "$APP" checkout -q --detach "$PREVIOUS"
}

run_signal_case() {
  local signal_name="$1"
  local expected_code="$2"
  local name="signal-${signal_name,,}"
  make_fixture "$name"

  local out="$TMP/$name.out"
  set +e
  APP_ROOT="$APP" \
  TARGET_COMMIT="$TARGET" \
  BACKUP_ROOT="$TMP/$name-backups" \
  DEPLOY_RECORD_ROOT="$TMP/$name-records" \
  TEST_COMMAND="kill -${signal_name} \"\$PPID\"; exit 0" \
  bash "$APP/deployment/deploy.sh" >"$out" 2>&1
  local code=$?
  set -e

  [[ "$code" == "$expected_code" ]] || fail "$signal_name must exit $expected_code, got $code"
  assert_contains "$out" "DEPLOY_RECOVERY_REQUIRED failed_phase=tests exit_code=$expected_code signal=$signal_name"

  local record
  record="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$out" | tail -n1)"
  [[ -f "$record" ]] || fail "$signal_name deploy record missing"
  assert_contains "$record" "state=code_changed status=passed"
  assert_contains "$record" "state=failed status=failed"
  assert_contains "$record" "failed_phase=tests;exit_code=$expected_code;signal=$signal_name"
  assert_not_contains "$record" "state=tests_passed status=passed"
  assert_not_contains "$record" "state=healthy status=passed"
  [[ "$(git -C "$APP" rev-parse HEAD)" == "$TARGET" ]] || fail "$signal_name must not trigger unsafe automatic rollback"
}

run_signal_case TERM 143
run_signal_case INT 130

echo "DEPLOY_SIGNAL_HANDLING_OK"
