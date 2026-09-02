#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
  echo "DEPLOY_RECORD_UNIQUENESS_TEST_FAILED: $*" >&2
  exit 1
}

APP="$TMP/app"
ORIGIN="$TMP/origin.git"
RECORD_ROOT="$TMP/records"
FAKE_BIN="$TMP/fake-bin"

mkdir -p "$APP/deployment" "$APP/tests/smoke" "$FAKE_BIN"
git init -q --bare "$ORIGIN"
git init -q "$APP"
git -C "$APP" config user.email "fixture@example.test"
git -C "$APP" config user.name "Deploy Fixture"
git -C "$APP" remote add origin "$ORIGIN"

cp "$ROOT/deployment/deploy.sh" "$APP/deployment/deploy.sh"
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

REAL_DATE="$(command -v date)"
cat > "$FAKE_BIN/date" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "$*" == "-u +%Y%m%d-%H%M%S" ]]; then
  printf '%s\n' '20260902-010203'
  exit 0
fi
exec "$REAL_DATE" "$@"
SH
chmod +x "$FAKE_BIN/date"

run_deploy() {
  local output="$1"
  PATH="$FAKE_BIN:$PATH" \
  REAL_DATE="$REAL_DATE" \
  APP_ROOT="$APP" \
  TARGET_COMMIT="$TARGET" \
  BACKUP_ROOT="$TMP/backups" \
  DEPLOY_RECORD_ROOT="$RECORD_ROOT" \
  TEST_COMMAND='echo TEST_OK' \
  bash "$APP/deployment/deploy.sh" >"$output" 2>&1
}

FIRST_OUT="$TMP/first.out"
SECOND_OUT="$TMP/second.out"
run_deploy "$FIRST_OUT"
FIRST_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$FIRST_OUT" | tail -n1)"
FIRST_REF="$(sed -n 's/^ROLLBACK_REF=//p' "$FIRST_OUT" | tail -n1)"
[[ -f "$FIRST_RECORD" ]] || fail "first deploy record missing"
[[ -n "$FIRST_REF" ]] || fail "first rollback ref missing"
FIRST_SUM="$(sha256sum "$FIRST_RECORD" | awk '{print $1}')"

git -C "$APP" checkout -q --detach "$PREVIOUS"
run_deploy "$SECOND_OUT"
SECOND_RECORD="$(sed -n 's/^DEPLOY_RECORD_FILE=//p' "$SECOND_OUT" | tail -n1)"
SECOND_REF="$(sed -n 's/^ROLLBACK_REF=//p' "$SECOND_OUT" | tail -n1)"
[[ -f "$SECOND_RECORD" ]] || fail "second deploy record missing"
[[ -n "$SECOND_REF" ]] || fail "second rollback ref missing"

[[ "$FIRST_RECORD" != "$SECOND_RECORD" ]] || fail "deploy records collided under the same timestamp"
[[ "$FIRST_REF" != "$SECOND_REF" ]] || fail "rollback refs collided under the same timestamp"
[[ "$(sha256sum "$FIRST_RECORD" | awk '{print $1}')" == "$FIRST_SUM" ]] || fail "second deploy modified the first deploy record"

grep -F 'state=healthy status=passed' "$FIRST_RECORD" >/dev/null || fail "first record lost healthy evidence"
grep -F 'state=healthy status=passed' "$SECOND_RECORD" >/dev/null || fail "second record missing healthy evidence"
git -C "$APP" rev-parse --verify "${FIRST_REF}^{commit}" >/dev/null || fail "first rollback ref missing"
git -C "$APP" rev-parse --verify "${SECOND_REF}^{commit}" >/dev/null || fail "second rollback ref missing"

FIRST_BASENAME="${FIRST_RECORD##*/}"
FIRST_ID="${FIRST_BASENAME%.log}"
SECOND_BASENAME="${SECOND_RECORD##*/}"
SECOND_ID="${SECOND_BASENAME%.log}"
[[ "$FIRST_REF" == "rollback/pre-${FIRST_ID}" ]] || fail "first rollback ref is not derived from its record id"
[[ "$SECOND_REF" == "rollback/pre-${SECOND_ID}" ]] || fail "second rollback ref is not derived from its record id"

echo "DEPLOY_RECORD_UNIQUENESS_OK"
