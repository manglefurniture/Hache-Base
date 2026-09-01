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

# Start from an explicitly hostile PHP runtime. P0-08 must enable cookie-backed
# sessions itself rather than relying on php.ini having session.use_cookies=1.
php -d session.use_cookies=0 -d session.save_path="$TMP/sessions" \
  -S "127.0.0.1:${PORT}" "$FIXTURE" >"$TMP/server.log" 2>&1 &
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

# A login must persist even though the PHP server was launched with use_cookies=0.
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

# Reproduce an explicit migration on a new request: an anonymous session is stored
# at /admin, then login changes the policy to /. The stored /admin tuple must be
# deleted even though runtime params were already initialized with the / candidate.
curl -fsS -D "$TMP/anon.headers" -c "$TMP/migrate-cookies.txt" \
  "$BASE_URL/admin/anonymous" -o "$TMP/anon.body"
grep -qx 'ANON_OK' "$TMP/anon.body"
grep -Eiq '^Set-Cookie: HACHEBASESCOPE=.*path=/admin([;[:space:]]|$)' "$TMP/anon.headers"

curl -fsS -D "$TMP/migrate.headers" -b "$TMP/migrate-cookies.txt" -c "$TMP/migrate-cookies.txt" \
  "$BASE_URL/admin/migrate-root" -o "$TMP/migrate.body"
grep -qx 'MIGRATE_OK' "$TMP/migrate.body"
grep -Eiq '^Set-Cookie: HACHEBASESCOPE=deleted;.*path=/admin([;[:space:]]|$)' "$TMP/migrate.headers"
grep -Eiq '^Set-Cookie: HACHEBASESCOPE=.*path=/([;[:space:]]|$)' "$TMP/migrate.headers"

if awk '$6 == "HACHEBASESCOPE" && $3 == "/admin" { found=1 } END { exit found ? 0 : 1 }' "$TMP/migrate-cookies.txt"; then
  echo "The migrated cookie jar still contains the old /admin tuple" >&2
  cat "$TMP/migrate-cookies.txt" >&2
  exit 1
fi

if ! awk '$6 == "HACHEBASESCOPE" && $3 == "/" { found=1 } END { exit found ? 0 : 1 }' "$TMP/migrate-cookies.txt"; then
  echo "The migrated cookie jar is missing the root session tuple" >&2
  cat "$TMP/migrate-cookies.txt" >&2
  exit 1
fi

curl -fsS -b "$TMP/migrate-cookies.txt" \
  "$BASE_URL/admin/check-root" -o "$TMP/check-root.body"
grep -qx 'MIGRATED_AUTH_OK' "$TMP/check-root.body"

echo "SESSION_COOKIE_SCOPE_HTTP_OK"
