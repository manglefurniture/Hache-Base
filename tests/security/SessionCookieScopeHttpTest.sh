#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIXTURE="$ROOT/tests/security/fixtures/session-cookie-scope.php"
TMP="$(mktemp -d)"
PORT="$((18000 + RANDOM % 1000))"
BASE_URL="http://127.0.0.1:${PORT}"
mkdir -p "$TMP/sessions"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

php -d session.save_path="$TMP/sessions" -S "127.0.0.1:${PORT}" "$FIXTURE" >"$TMP/server.log" 2>&1 &
SERVER_PID=$!

ready=0
for _ in $(seq 1 40); do
  if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.1
done

if [[ "$ready" -ne 1 ]]; then
  cat "$TMP/server.log" >&2 || true
  echo "Session cookie scope fixture did not start" >&2
  exit 1
fi

curl -fsS -D "$TMP/login.headers" -c "$TMP/cookies.txt" \
  "$BASE_URL/admin/login" -o "$TMP/login.body"
grep -qx 'LOGIN_OK' "$TMP/login.body"
grep -Eiq '^Set-Cookie: HACHEBASESCOPE=.*path=/admin([;[:space:]]|$)' "$TMP/login.headers"

curl -fsS -D "$TMP/touch.headers" -b "$TMP/cookies.txt" -c "$TMP/cookies.txt" \
  "$BASE_URL/admin/touch" -o "$TMP/touch.body"
grep -qx 'TOUCH_OK' "$TMP/touch.body"
grep -Eiq '^Set-Cookie: HACHEBASESCOPE=.*path=/admin([;[:space:]]|$)' "$TMP/touch.headers"

if grep -Eiq '^Set-Cookie: HACHEBASESCOPE=deleted;.*path=/([;[:space:]]|$)' "$TMP/touch.headers"; then
  echo "A no-config request expired an inferred root cookie scope" >&2
  cat "$TMP/touch.headers" >&2
  exit 1
fi

echo "SESSION_COOKIE_SCOPE_HTTP_OK"
