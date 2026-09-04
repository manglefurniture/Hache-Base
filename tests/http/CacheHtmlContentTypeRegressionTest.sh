#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROUTER="$ROOT/tests/http/fixture-router.php"
TMP="$(mktemp -d)"
HOST="127.0.0.1"
PORT="$(php -r '$s=stream_socket_server("tcp://127.0.0.1:0", $errno, $errstr); if (!$s) { exit(1); } $name=stream_socket_get_name($s, false); echo substr(strrchr($name, ":"), 1); fclose($s);')"
BASE="http://$HOST:$PORT"
SERVER_PID=""
VERSION_FILE="$TMP/cache-version.txt"

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

fail() {
  echo "CACHE_HTML_CONTENT_TYPE_TEST_ERROR $*" >&2
  if [[ -f "$TMP/server.log" ]]; then
    cat "$TMP/server.log" >&2 || true
  fi
  exit 1
}

request() {
  local name="$1" path="$2"
  local headers="$TMP/$name.headers"
  local body="$TMP/$name.body"
  local code
  code="$(curl -sS --max-time 5 -D "$headers" -o "$body" -w '%{http_code}' "$BASE$path")" \
    || fail "curl_failed name=$name path=$path"
  [[ "$code" == "200" ]] || fail "unexpected_status name=$name code=$code"
}

assert_html() {
  local name="$1"
  tr -d '\r' < "$TMP/$name.headers" | grep -Eiq '^Content-Type:[[:space:]]*text/html;[[:space:]]*charset=utf-8$' \
    || fail "missing_html_content_type name=$name"
  grep -Fq '<!doctype html>' "$TMP/$name.body" || fail "missing_html_document name=$name"
}

printf 'v1\n' > "$VERSION_FILE"
HB_CACHE_VERSION_FILE="$VERSION_FILE" php -S "$HOST:$PORT" "$ROUTER" >"$TMP/server.log" 2>&1 &
SERVER_PID=$!

for ((attempt = 0; attempt < 50; attempt++)); do
  if curl -fsS --max-time 1 "$BASE/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
curl -fsS --max-time 1 "$BASE/health" >/dev/null 2>&1 || fail "fixture_server_not_ready"

request public-html /cache/html
assert_html public-html

grep -Fq 'html cache fixture v1' "$TMP/public-html.body" || fail "public_html_body_mismatch"

request private-html /account
assert_html private-html

grep -Fq 'private html fixture' "$TMP/private-html.body" || fail "private_html_body_mismatch"

echo "CACHE_HTML_CONTENT_TYPE_OK"
