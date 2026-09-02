#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
  echo "ROLLBACK_RECOVERY_STATE_TEST_FAILED: $*" >&2
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

APP="$TMP/app"
ORIGIN="$TMP/origin.git"
RECORD="$TMP/deploy.record"

git init -q --bare "$ORIGIN"
git init -q "$APP"
git -C "$APP" config user.email "fixture@example.test"
git -C "$APP" config user.name "Rollback Fixture"
git -C "$APP" remote add origin "$ORIGIN"

mkdir -p "$APP/deployment"
cp "$ROOT/deployment/rollback.sh" "$APP/deployment/rollback.sh"
cp "$ROOT/deployment/mark-deploy-recovery.sh" "$APP/deployment/mark-deploy-recovery.sh"

echo before > "$APP/version.txt"
git -C "$APP" add .
git -C "$APP" commit -q -m "previous"
PREVIOUS="$(git -C "$APP" rev-parse HEAD)"
git -C "$APP" branch rollback/pre-test "$PREVIOUS"

echo after > "$APP/version.txt"
git -C "$APP" add version.txt
git -C "$APP" commit -q -m "target"
TARGET="$(git -C "$APP" rev-parse HEAD)"
git -C "$APP" push -q origin HEAD:refs/heads/main

printf 'DEPLOY_STATE timestamp=2026-09-01T00:00:00Z state=started status=running target_commit=%s current_commit=%s rollback_ref=none detail=deploy_started\n' "$TARGET" "$PREVIOUS" > "$RECORD"

DEPLOY_RECORD_FILE="$RECORD" APP_ROOT="$APP" \
  bash "$APP/deployment/rollback.sh" rollback/pre-test > "$TMP/rollback.out" 2>&1

[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "code rollback did not restore previous commit"
assert_contains "$TMP/rollback.out" "CODE_ROLLBACK_OK $PREVIOUS"
assert_contains "$RECORD" "DEPLOY_RECOVERY_EVENT"
assert_contains "$RECORD" "event=code_rollback status=passed"
assert_contains "$RECORD" "recovery_state=pending_verification"
assert_not_contains "$RECORD" "state=rolled_back status=passed"

DEPLOY_RECORD_FILE="$RECORD" APP_ROOT="$APP" ROLLBACK_REF="rollback/pre-test" \
  bash "$APP/deployment/mark-deploy-recovery.sh" rolled_back post_recovery_gates_verified > "$TMP/verified.out" 2>&1

assert_contains "$RECORD" "state=rolled_back status=passed"
assert_contains "$RECORD" "detail=post_recovery_gates_verified"

echo "ROLLBACK_RECOVERY_STATE_OK"
