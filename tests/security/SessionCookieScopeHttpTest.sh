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

dump_diagnostics() {
  local status=$?
  local line=${BASH_LINENO[0]:-unknown}
  trap - ERR
  echo "Session cookie HTTP regression failed at line ${line} (status ${status})" >&2
  for file in \
    server.log \
    login.headers login.body cookies.txt \
    touch.headers touch.body \
    anon.headers anon.body \
    migrate.headers migrate.body migrate-cookies.txt \
    check-root.body \
    legacy-anon.headers legacy-anon.body legacy-cookies.txt \
    legacy-login.headers legacy-login.body \
    preactive-login.headers preactive-login.body; do
    if [[ -f "$TMP/$file" ]]; then
      echo "----- $file -----" >&2
      cat "$TMP/$file" >&2 || true
    fi
  done
  exit "$status"
}

trap dump_diagnostics ERR
trap cleanup EXIT

# Start from an explicitly hostile PHP runtime. P0-08 must enable cookie-backed
# sessions itself when Hache Base starts the session.
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

# A login must persist even though the PHP server was launched with use_cookies=0,
# provided Hache Base owns session startup and can impose SEC-007 first.
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

# A legacy anonymous session can exist server-side without Hache metadata. Even when
# Hache Base itself later calls session_start(), an incoming /admin cookie does not
# reveal its historical Path/Domain to PHP. Login must fail closed rather than attach
# auth and emit a second root-scoped cookie that the legacy cookie can shadow.
curl -fsS -D "$TMP/legacy-anon.headers" -c "$TMP/legacy-cookies.txt" \
  "$BASE_URL/admin/legacy-anonymous" -o "$TMP/legacy-anon.body"
grep -qx 'LEGACY_ANON_OK' "$TMP/legacy-anon.body"
grep -Eiq '^Set-Cookie: HACHEBASESCOPE=.*path=/admin([;[:space:]]|$)' "$TMP/legacy-anon.headers"

curl -fsS -D "$TMP/legacy-login.headers" -b "$TMP/legacy-cookies.txt" -c "$TMP/legacy-cookies.txt" \
  "$BASE_URL/admin/legacy-login-root" -o "$TMP/legacy-login.body"
grep -qx 'LEGACY_INCOMING_REJECTED' "$TMP/legacy-login.body"

if grep -Eiq '^Set-Cookie: HACHEBASESCOPE=.*path=/([;[:space:]]|$)' "$TMP/legacy-login.headers"; then
  echo "A rejected legacy incoming session emitted a root session cookie" >&2
  cat "$TMP/legacy-login.headers" >&2
  exit 1
fi

if ! awk '$6 == "HACHEBASESCOPE" && $3 == "/admin" { found=1 } END { exit found ? 0 : 1 }' "$TMP/legacy-cookies.txt"; then
  echo "The legacy /admin cookie unexpectedly disappeared during rejection" >&2
  cat "$TMP/legacy-cookies.txt" >&2
  exit 1
fi

if awk '$6 == "HACHEBASESCOPE" && $3 == "/" { found=1 } END { exit found ? 0 : 1 }' "$TMP/legacy-cookies.txt"; then
  echo "The rejected legacy session created a root cookie in the browser jar" >&2
  cat "$TMP/legacy-cookies.txt" >&2
  exit 1
fi

# A framework that has already started a session under a non-compliant runtime is
# not safely recoverable: PHP collapses same-name cookies from different Path scopes
# in $_COOKIE. SEC-007 therefore rejects this state before authentication instead of
# guessing a tuple. This must be a controlled rejection, with no authenticated cookie.
curl -fsS -D "$TMP/preactive-login.headers" \
  "$BASE_URL/preactive/login" -o "$TMP/preactive-login.body"
grep -qx 'PREACTIVE_REJECTED' "$TMP/preactive-login.body"
if grep -Eiq '^Set-Cookie: HACHEBASESCOPE=' "$TMP/preactive-login.headers"; then
  echo "A rejected insecure pre-active session emitted an authenticated session cookie" >&2
  cat "$TMP/preactive-login.headers" >&2
  exit 1
fi

echo "SESSION_COOKIE_SCOPE_HTTP_OK"
