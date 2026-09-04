#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROUTER="$ROOT/tests/http/fixture-router.php"
TMP="$(mktemp -d)"
HOST="127.0.0.1"
PORT="$(php -r '$s=stream_socket_server("tcp://127.0.0.1:0", $errno, $errstr); if (!$s) { exit(1); } $name=stream_socket_get_name($s, false); echo substr(strrchr($name, ":"), 1); fclose($s);')"
BASE="http://$HOST:$PORT"
SERVER_PID=""
CACHE_VERSION_FILE="$TMP/cache-version.txt"

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

fail() {
  echo "HTTP_FIXTURE_TEST_ERROR $*" >&2
  if [[ -f "$TMP/server.log" ]]; then
    cat "$TMP/server.log" >&2 || true
  fi
  exit 1
}

assert_header() {
  local file="$1" pattern="$2"
  tr -d '\r' < "$file" | grep -Eiq "$pattern" || fail "missing_header pattern=$pattern file=$file"
}

assert_no_header() {
  local file="$1" pattern="$2"
  if tr -d '\r' < "$file" | grep -Eiq "$pattern"; then
    fail "unexpected_header pattern=$pattern file=$file"
  fi
}

request() {
  local name="$1" path="$2"
  shift 2
  local headers="$TMP/$name.headers"
  local body="$TMP/$name.body"
  local code
  code="$(curl -sS --max-time 5 -D "$headers" -o "$body" -w '%{http_code}' "$@" "$BASE$path")" \
    || fail "curl_failed name=$name path=$path"
  printf '%s' "$code"
}

command -v curl >/dev/null 2>&1 || fail "curl_not_available"
[[ -n "$PORT" && "$PORT" =~ ^[0-9]+$ ]] || fail "invalid_dynamic_port=$PORT"
printf 'v1\n' > "$CACHE_VERSION_FILE"

HB_CACHE_VERSION_FILE="$CACHE_VERSION_FILE" php -S "$HOST:$PORT" "$ROUTER" >"$TMP/server.log" 2>&1 &
SERVER_PID=$!

ready=0
for ((attempt = 0; attempt < 50; attempt++)); do
  if curl -fsS --max-time 1 "$BASE/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    fail "fixture_server_exited"
  fi
  sleep 0.1
done
[[ "$ready" -eq 1 ]] || fail "fixture_server_not_ready"

code="$(request headers /headers)"
[[ "$code" == "200" ]] || fail "headers_status=$code"
assert_header "$TMP/headers.headers" '^X-Content-Type-Options:[[:space:]]*nosniff$'
assert_header "$TMP/headers.headers" '^X-Frame-Options:[[:space:]]*SAMEORIGIN$'
assert_header "$TMP/headers.headers" '^Referrer-Policy:[[:space:]]*strict-origin-when-cross-origin$'
assert_header "$TMP/headers.headers" '^Permissions-Policy:[[:space:]]*geolocation=\(\), microphone=\(\), camera=\(\)$'
assert_header "$TMP/headers.headers" "^Content-Security-Policy-Report-Only:[[:space:]]*default-src 'self'; object-src 'none'; base-uri 'self'$"
assert_no_header "$TMP/headers.headers" '^Content-Security-Policy:'
assert_no_header "$TMP/headers.headers" '^Strict-Transport-Security:'
[[ "$(cat "$TMP/headers.body")" == "headers fixture" ]] || fail "headers_body_mismatch"

code="$(request cookie /cookie)"
[[ "$code" == "200" ]] || fail "cookie_status=$code"
assert_header "$TMP/cookie.headers" '^Set-Cookie:[[:space:]]*HB_HTTP_FIXTURE=1; path=/; HttpOnly; SameSite=Lax$'
assert_no_header "$TMP/cookie.headers" '^Set-Cookie:.*; Secure(;|$)'

code="$(request cache-public /cache/public)"
[[ "$code" == "200" ]] || fail "cache_public_status=$code"
assert_header "$TMP/cache-public.headers" '^Cache-Control:[[:space:]]*public, max-age=60$'

code="$(request cache-private /cache/private)"
[[ "$code" == "200" ]] || fail "cache_private_status=$code"
assert_header "$TMP/cache-private.headers" '^Cache-Control:[[:space:]]*private, no-store, max-age=0$'
assert_header "$TMP/cache-private.headers" '^Pragma:[[:space:]]*no-cache$'

# P1-06 / PERF-011 cache matrix fixture.
code="$(request cache-html-v1 /cache/html)"
[[ "$code" == "200" ]] || fail "cache_html_v1_status=$code"
assert_header "$TMP/cache-html-v1.headers" '^Content-Type:[[:space:]]*text/html;[[:space:]]*charset=utf-8$'
assert_header "$TMP/cache-html-v1.headers" '^Cache-Control:[[:space:]]*no-cache$'
assert_header "$TMP/cache-html-v1.headers" '^ETag:[[:space:]]*"hb-v1"$'
[[ "$(cat "$TMP/cache-html-v1.body")" == '<!doctype html><html lang="en"><body>html cache fixture v1</body></html>' ]] || fail "cache_html_v1_body_mismatch"

code="$(request cache-html-304 /cache/html -H 'If-None-Match: "hb-v1"')"
[[ "$code" == "304" ]] || fail "cache_html_revalidation_status=$code"
assert_header "$TMP/cache-html-304.headers" '^Content-Type:[[:space:]]*text/html;[[:space:]]*charset=utf-8$'
assert_header "$TMP/cache-html-304.headers" '^Cache-Control:[[:space:]]*no-cache$'
assert_header "$TMP/cache-html-304.headers" '^ETag:[[:space:]]*"hb-v1"$'
[[ ! -s "$TMP/cache-html-304.body" ]] || fail "cache_html_304_has_body"

printf 'v2\n' > "$CACHE_VERSION_FILE"
code="$(request cache-html-v2 /cache/html -H 'If-None-Match: "hb-v1"')"
[[ "$code" == "200" ]] || fail "cache_html_invalidation_status=$code"
assert_header "$TMP/cache-html-v2.headers" '^Content-Type:[[:space:]]*text/html;[[:space:]]*charset=utf-8$'
assert_header "$TMP/cache-html-v2.headers" '^Cache-Control:[[:space:]]*no-cache$'
assert_header "$TMP/cache-html-v2.headers" '^ETag:[[:space:]]*"hb-v2"$'
[[ "$(cat "$TMP/cache-html-v2.body")" == '<!doctype html><html lang="en"><body>html cache fixture v2</body></html>' ]] || fail "cache_html_v2_body_mismatch"

code="$(request cache-hashed-asset /assets/app.abc123.js)"
[[ "$code" == "200" ]] || fail "cache_hashed_asset_status=$code"
assert_header "$TMP/cache-hashed-asset.headers" '^Cache-Control:[[:space:]]*public, max-age=31536000, immutable$'

code="$(request cache-unversioned-asset /assets/app.js)"
[[ "$code" == "200" ]] || fail "cache_unversioned_asset_status=$code"
assert_header "$TMP/cache-unversioned-asset.headers" '^Cache-Control:[[:space:]]*no-cache$'
assert_no_header "$TMP/cache-unversioned-asset.headers" '^Cache-Control:.*immutable'

code="$(request cache-public-api /api/public)"
[[ "$code" == "200" ]] || fail "cache_public_api_status=$code"
assert_header "$TMP/cache-public-api.headers" '^Cache-Control:[[:space:]]*public, max-age=60$'
assert_no_header "$TMP/cache-public-api.headers" '^Set-Cookie:'

code="$(request cache-private-api /api/private)"
[[ "$code" == "200" ]] || fail "cache_private_api_status=$code"
assert_header "$TMP/cache-private-api.headers" '^Cache-Control:[[:space:]]*private, no-store, max-age=0$'
assert_header "$TMP/cache-private-api.headers" '^Pragma:[[:space:]]*no-cache$'
assert_no_header "$TMP/cache-private-api.headers" '^Cache-Control:.*public'

code="$(request cache-private-html /account)"
[[ "$code" == "200" ]] || fail "cache_private_html_status=$code"
assert_header "$TMP/cache-private-html.headers" '^Content-Type:[[:space:]]*text/html;[[:space:]]*charset=utf-8$'
assert_header "$TMP/cache-private-html.headers" '^Cache-Control:[[:space:]]*private, no-store, max-age=0$'
assert_header "$TMP/cache-private-html.headers" '^Pragma:[[:space:]]*no-cache$'
assert_no_header "$TMP/cache-private-html.headers" '^Cache-Control:.*public'
[[ "$(cat "$TMP/cache-private-html.body")" == '<!doctype html><html lang="en"><body>private html fixture</body></html>' ]] || fail "cache_private_html_body_mismatch"

code="$(request compressed /compressed -H 'Accept-Encoding: gzip')"
[[ "$code" == "200" ]] || fail "compressed_status=$code"
assert_header "$TMP/compressed.headers" '^Content-Encoding:[[:space:]]*gzip$'
assert_header "$TMP/compressed.headers" '^Vary:[[:space:]]*Accept-Encoding$'
php -r '$raw=file_get_contents($argv[1]); $decoded=is_string($raw) ? gzdecode($raw) : false; exit($decoded === "compressed fixture\n" ? 0 : 1);' "$TMP/compressed.body" \
  || fail "gzip_body_invalid"

code="$(request plain /compressed)"
[[ "$code" == "200" ]] || fail "plain_status=$code"
assert_no_header "$TMP/plain.headers" '^Content-Encoding:'
[[ "$(cat "$TMP/plain.body")" == "compressed fixture" ]] || fail "plain_body_mismatch"

code="$(request redirect /redirect)"
[[ "$code" == "302" ]] || fail "redirect_status=$code"
assert_header "$TMP/redirect.headers" '^Location:[[:space:]]*/target$'
follow_body="$(curl -fsS --max-time 5 -L "$BASE/redirect")" || fail "redirect_follow_failed"
[[ "$follow_body" == "redirect target" ]] || fail "redirect_target_mismatch"

code="$(request no-content /status/204)"
[[ "$code" == "204" ]] || fail "status_204=$code"
[[ ! -s "$TMP/no-content.body" ]] || fail "status_204_has_body"

code="$(request not-found /missing-route)"
[[ "$code" == "404" ]] || fail "status_404=$code"
[[ "$(cat "$TMP/not-found.body")" == "Not Found" ]] || fail "status_404_body_mismatch"
assert_header "$TMP/not-found.headers" '^Cache-Control:[[:space:]]*no-store$'

code="$(request server-error /error)"
[[ "$code" == "500" ]] || fail "status_500=$code"
[[ "$(cat "$TMP/server-error.body")" == "Internal Server Error" ]] || fail "status_500_body_mismatch"
assert_header "$TMP/server-error.headers" '^Cache-Control:[[:space:]]*no-store$'
if grep -Eqi 'stack trace|fatal error|tests/http|/home/|/var/www/' "$TMP/server-error.body"; then
  fail "status_500_leaks_internal_detail"
fi

echo "PRODUCTION_READINESS_HTTP_OK"
