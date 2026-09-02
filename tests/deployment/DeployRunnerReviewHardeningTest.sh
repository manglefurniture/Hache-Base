#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
  echo "DEPLOY_REVIEW_HARDENING_TEST_FAILED: $*" >&2
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
  cp "$ROOT/deployment/mark-deploy-recovery.sh" "$APP/deployment/mark-deploy-recovery.sh"
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

# Restrictive record creation must not leak umask=077 into migrations/tests/runtime gates.
make_fixture umask
UMASK_OUT="$TMP/umask.out"
UMASK_CAPTURE="$TMP/child-umask.txt"
TEST_ARTIFACT="$TMP/test-artifact.txt"
(
  umask 0022
  APP_ROOT="$APP" \
  TARGET_COMMIT="$TARGET" \
  BACKUP_ROOT="$TMP/umask-backups" \
  DEPLOY_RECORD_ROOT="$TMP/umask-records" \
  UMASK_CAPTURE="$UMASK_CAPTURE" \
  TEST_ARTIFACT="$TEST_ARTIFACT" \
  TEST_COMMAND='umask > "$UMASK_CAPTURE"; touch "$TEST_ARTIFACT"' \
  bash "$APP/deployment/deploy.sh" >"$UMASK_OUT" 2>&1
)

assert_contains "$UMASK_OUT" "DEPLOY_OK $TARGET"
[[ -f "$UMASK_CAPTURE" ]] || fail "test command did not capture inherited umask"
CHILD_UMASK="$(tr -d '[:space:]' < "$UMASK_CAPTURE")"
[[ "$CHILD_UMASK" == "0022" || "$CHILD_UMASK" == "022" ]] || fail "child inherited unexpected umask: $CHILD_UMASK"
[[ "$(stat -c '%a' "$TEST_ARTIFACT")" == "644" ]] || fail "test artifact should be 0644 under umask 0022"

# A failed rollback-ref creation must never publish a ref that does not exist.
make_fixture rollback-ref-failure
FAKE_BIN="$TMP/fake-git-bin"
mkdir -p "$FAKE_BIN"
REAL_GIT="$(command -v git)"
cat > "$FAKE_BIN/git" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "branch" ]]; then
  echo "fixture: refusing rollback branch creation" >&2
  exit 13
fi
exec "$REAL_GIT" "$@"
SH
chmod +x "$FAKE_BIN/git"

ROLLBACK_FAIL_OUT="$TMP/rollback-ref-failure.out"
set +e
PATH="$FAKE_BIN:$PATH" \
REAL_GIT="$REAL_GIT" \
APP_ROOT="$APP" \
TARGET_COMMIT="$TARGET" \
BACKUP_ROOT="$TMP/rollback-ref-failure-backups" \
DEPLOY_RECORD_ROOT="$TMP/rollback-ref-failure-records" \
bash "$APP/deployment/deploy.sh" >"$ROLLBACK_FAIL_OUT" 2>&1
ROLLBACK_FAIL_CODE=$?
set -e

[[ "$ROLLBACK_FAIL_CODE" == "13" ]] || fail "rollback-ref failure must preserve exit code 13, got $ROLLBACK_FAIL_CODE"
assert_contains "$ROLLBACK_FAIL_OUT" "DEPLOY_RECOVERY_REQUIRED failed_phase=rollback_ref exit_code=13"
assert_contains "$ROLLBACK_FAIL_OUT" "rollback_ref=unavailable"
if grep -q '^ROLLBACK_REF=' "$ROLLBACK_FAIL_OUT"; then
  fail "runner published ROLLBACK_REF even though branch creation failed"
fi
ROLLBACK_FAIL_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$ROLLBACK_FAIL_OUT" | tail -n1)"
[[ -f "$ROLLBACK_FAIL_RECORD" ]] || fail "rollback-ref failure record missing"
assert_contains "$ROLLBACK_FAIL_RECORD" "state=failed status=failed"
assert_contains "$ROLLBACK_FAIL_RECORD" "rollback_ref=none"
[[ -z "$(git -C "$APP" branch --list 'rollback/pre-deploy-*')" ]] || fail "failed rollback ref must not exist"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$PREVIOUS" ]] || fail "rollback-ref failure must happen before code change"

# Recovery evidence must resolve HEAD when APP_ROOT is a Git worktree (.git is a file).
make_fixture recovery-worktree
WORKTREE="$TMP/recovery-worktree-checkout"
git -C "$APP" worktree add -q --detach "$WORKTREE" "$PREVIOUS"
[[ -f "$WORKTREE/.git" ]] || fail "fixture did not create a Git worktree"
WORKTREE_RECORD="$TMP/worktree-recovery-record.log"
printf 'DEPLOY_STATE timestamp=2026-09-01T00:00:00Z state=started status=running target_commit=%s current_commit=%s rollback_ref=none detail=fixture\n' "$TARGET" "$PREVIOUS" > "$WORKTREE_RECORD"
DEPLOY_RECORD_FILE="$WORKTREE_RECORD" \
APP_ROOT="$WORKTREE" \
bash "$WORKTREE/deployment/mark-deploy-recovery.sh" manual_recovery worktree_verified > "$TMP/worktree-recovery.out"

assert_contains "$WORKTREE_RECORD" "state=manual_recovery status=passed"
assert_contains "$WORKTREE_RECORD" "current_commit=$PREVIOUS"
assert_contains "$WORKTREE_RECORD" "detail=worktree_verified"

echo "DEPLOY_REVIEW_HARDENING_OK"
