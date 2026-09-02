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

assert_failed_record() {
  local out="$1"
  local expected_code="$2"
  local signal_name="$3"
  local record

  assert_contains "$out" "DEPLOY_RECOVERY_REQUIRED failed_phase=tests exit_code=$expected_code signal=$signal_name"
  record="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$out" | tail -n1)"
  [[ -f "$record" ]] || fail "$signal_name deploy record missing"
  assert_contains "$record" "state=code_changed status=passed"
  assert_contains "$record" "state=failed status=failed"
  assert_contains "$record" "failed_phase=tests;exit_code=$expected_code;signal=$signal_name"
  assert_not_contains "$record" "state=tests_passed status=passed"
  assert_not_contains "$record" "state=healthy status=passed"
  [[ "$(git -C "$APP" rev-parse HEAD)" == "$TARGET" ]] || fail "$signal_name must not trigger unsafe automatic rollback"
}

# INT path: child triggers the signal while the runner is waiting in a managed phase.
run_internal_int_case() {
  make_fixture signal-int
  local out="$TMP/signal-int.out"

  set +e
  APP_ROOT="$APP" \
  TARGET_COMMIT="$TARGET" \
  BACKUP_ROOT="$TMP/signal-int-backups" \
  DEPLOY_RECORD_ROOT="$TMP/signal-int-records" \
  TEST_COMMAND='kill -INT "$PPID"; exit 0' \
  bash "$APP/deployment/deploy.sh" >"$out" 2>&1
  local code=$?
  set -e

  [[ "$code" == "130" ]] || fail "INT must exit 130, got $code"
  assert_failed_record "$out" 130 INT
}

# P1 regression: TERM is sent only to the runner PID while its test phase remains active.
# The phase traps TERM for evidence and intentionally keeps running, forcing the runner
# to forward TERM to the process group and escalate after the configured grace period.
run_parent_term_case() {
  make_fixture signal-parent-term

  local out="$TMP/signal-parent-term.out"
  local child_pid_file="$TMP/signal-parent-term-child.pid"
  local child_signal_file="$TMP/signal-parent-term-child.signal"
  local test_command
  test_command="trap 'printf TERM > \"$child_signal_file\"' TERM; printf '%s\\n' \"\$\$\" > \"$child_pid_file\"; while :; do sleep 10; done"

  set +e
  APP_ROOT="$APP" \
  TARGET_COMMIT="$TARGET" \
  BACKUP_ROOT="$TMP/signal-parent-term-backups" \
  DEPLOY_RECORD_ROOT="$TMP/signal-parent-term-records" \
  SIGNAL_GRACE_SECONDS=1 \
  TEST_COMMAND="$test_command" \
  bash "$APP/deployment/deploy.sh" >"$out" 2>&1 &
  local runner_pid=$!
  set -e

  local attempts=100
  while [[ ! -s "$child_pid_file" && "$attempts" -gt 0 ]]; do
    sleep 0.05
    attempts=$((attempts - 1))
  done
  [[ -s "$child_pid_file" ]] || {
    kill -KILL "$runner_pid" 2>/dev/null || true
    wait "$runner_pid" 2>/dev/null || true
    fail "managed test child did not start"
  }

  local child_pid
  child_pid="$(cat "$child_pid_file")"
  kill -TERM "$runner_pid"

  # A watchdog keeps a broken implementation from hanging CI indefinitely.
  (
    sleep 5
    kill -KILL "$runner_pid" 2>/dev/null || true
  ) &
  local watchdog_pid=$!

  set +e
  wait "$runner_pid"
  local code=$?
  set -e
  kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true

  [[ "$code" == "143" ]] || {
    kill -KILL "$child_pid" 2>/dev/null || true
    fail "parent-only TERM must exit 143, got $code"
  }

  [[ -f "$child_signal_file" ]] || fail "TERM was not forwarded to the active phase"
  if kill -0 "$child_pid" 2>/dev/null; then
    kill -KILL "$child_pid" 2>/dev/null || true
    fail "active phase survived parent cancellation"
  fi

  assert_failed_record "$out" 143 TERM
}

run_internal_int_case
run_parent_term_case

echo "DEPLOY_SIGNAL_HANDLING_OK"
