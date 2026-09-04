#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROUTER="$ROOT/tests/form-b/fixture-router.php"
TMP="$(mktemp -d)"
HOST="127.0.0.1"
PORT="$(php -r '$s=stream_socket_server("tcp://127.0.0.1:0", $errno, $errstr); if (!$s) { exit(1); } $name=stream_socket_get_name($s, false); echo substr(strrchr($name, ":"), 1); fclose($s);')"
BASE="http://$HOST:$PORT"
SERVER_PID=""
MAIN_COOKIE="$TMP/main.cookies"
RATE_COOKIE="$TMP/rate.cookies"

touch "$MAIN_COOKIE" "$RATE_COOKIE"

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

fail() {
  echo "FORM_B_FIXTURE_TEST_ERROR $*" >&2
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
  local cookie="$1" name="$2" method="$3" path="$4"
  shift 4
  local headers="$TMP/$name.headers"
  local body="$TMP/$name.body"
  local code
  code="$(curl -sS --max-time 5 -c "$cookie" -b "$cookie" -X "$method" -D "$headers" -o "$body" -w '%{http_code}' "$@" "$BASE$path")" \
    || fail "curl_failed name=$name method=$method path=$path"
  printf '%s' "$code"
}

extract_csrf() {
  grep -oE 'name="_csrf" value="[a-f0-9]{64}"' "$1" | head -n1 | sed -E 's/.*value="([a-f0-9]{64})"/\1/'
}

extract_submission() {
  grep -oE 'name="submission_id" value="[a-f0-9]{32}"' "$1" | head -n1 | sed -E 's/.*value="([a-f0-9]{32})"/\1/'
}

command -v curl >/dev/null 2>&1 || fail "curl_not_available"
[[ -n "$PORT" && "$PORT" =~ ^[0-9]+$ ]] || fail "invalid_dynamic_port=$PORT"

php -S "$HOST:$PORT" "$ROUTER" >"$TMP/server.log" 2>&1 &
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

code="$(request "$MAIN_COOKIE" form-get GET /form-b)"
[[ "$code" == "200" ]] || fail "form_get_status=$code"
assert_header "$TMP/form-get.headers" '^Content-Type:[[:space:]]*text/html;[[:space:]]*charset=utf-8$'
assert_header "$TMP/form-get.headers" '^Cache-Control:[[:space:]]*no-store$'
assert_header "$TMP/form-get.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*0$'
grep -Fq 'data-form-state="idle"' "$TMP/form-get.body" || fail "missing_idle_state"
grep -Fq 'id="form-status" role="status" aria-live="polite"' "$TMP/form-get.body" || fail "missing_live_status"
grep -Fq '<label for="name">Nombre</label>' "$TMP/form-get.body" || fail "missing_name_label"
grep -Fq 'name="email" type="email" required maxlength="254" autocomplete="email" inputmode="email"' "$TMP/form-get.body" || fail "missing_email_contract"
grep -Fq 'name="message" required minlength="10" maxlength="1000"' "$TMP/form-get.body" || fail "missing_message_contract"
grep -Fq 'name="company_website" type="text" tabindex="-1" autocomplete="off"' "$TMP/form-get.body" || fail "missing_honeypot"
grep -Fq 'f.dataset.formState="loading"' "$TMP/form-get.body" || fail "missing_loading_state"
grep -Fq 'b.disabled=true' "$TMP/form-get.body" || fail "missing_double_submit_guard"
if grep -Eqi 'recaptcha|hcaptcha|turnstile|captcha' "$TMP/form-get.body"; then
  fail "captcha_provider_should_not_be_required"
fi

csrf="$(extract_csrf "$TMP/form-get.body")"
submission="$(extract_submission "$TMP/form-get.body")"
[[ "$csrf" =~ ^[a-f0-9]{64}$ ]] || fail "invalid_csrf_shape"
[[ "$submission" =~ ^[a-f0-9]{32}$ ]] || fail "invalid_submission_shape"

code="$(request "$MAIN_COOKIE" csrf-missing POST /form-b \
  --data-urlencode "submission_id=$submission" \
  --data-urlencode 'name=Ariel Example' \
  --data-urlencode 'email=ariel@example.test' \
  --data-urlencode 'message=Mensaje válido para la prueba.')"
[[ "$code" == "419" ]] || fail "csrf_missing_status=$code"
grep -Fq 'data-form-state="error"' "$TMP/csrf-missing.body" || fail "csrf_missing_not_error_state"
assert_header "$TMP/csrf-missing.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*0$'

code="$(request "$MAIN_COOKIE" validation POST /form-b \
  --data-urlencode "_csrf=$csrf" \
  --data-urlencode "submission_id=$submission" \
  --data-urlencode 'name=A' \
  --data-urlencode 'email=not-an-email' \
  --data-urlencode 'message=short')"
[[ "$code" == "422" ]] || fail "validation_status=$code"
grep -Fq 'data-form-state="error"' "$TMP/validation.body" || fail "validation_not_error_state"
grep -Fq 'role="alert"' "$TMP/validation.body" || fail "validation_missing_alert"
grep -Fq 'aria-invalid="true" aria-describedby="name-error"' "$TMP/validation.body" || fail "name_error_not_accessible"
grep -Fq 'value="A"' "$TMP/validation.body" || fail "valid_input_not_preserved"
grep -Fq 'value="not-an-email"' "$TMP/validation.body" || fail "email_input_not_preserved"
grep -Fq '>short</textarea>' "$TMP/validation.body" || fail "message_input_not_preserved"
assert_header "$TMP/validation.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*0$'

code="$(request "$MAIN_COOKIE" honeypot POST /form-b \
  --data-urlencode "_csrf=$csrf" \
  --data-urlencode "submission_id=$submission" \
  --data-urlencode 'name=Ariel Example' \
  --data-urlencode 'email=ariel@example.test' \
  --data-urlencode 'message=Mensaje válido para la prueba.' \
  --data-urlencode 'company_website=https://bot.invalid')"
[[ "$code" == "200" ]] || fail "honeypot_status=$code"
grep -Fq 'data-form-state="success"' "$TMP/honeypot.body" || fail "honeypot_not_generic_success"
assert_header "$TMP/honeypot.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*0$'
assert_no_header "$TMP/honeypot.headers" '^X-Hache-Fixture-Deduplicated:'

code="$(request "$MAIN_COOKIE" accepted POST /form-b \
  --data-urlencode "_csrf=$csrf" \
  --data-urlencode "submission_id=$submission" \
  --data-urlencode 'name=Ariel Example' \
  --data-urlencode 'email=ariel@example.test' \
  --data-urlencode 'message=Mensaje válido para la prueba.')"
[[ "$code" == "201" ]] || fail "accepted_status=$code"
grep -Fq 'data-form-state="success"' "$TMP/accepted.body" || fail "accepted_not_success_state"
assert_header "$TMP/accepted.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*1$'
assert_no_header "$TMP/accepted.headers" '^X-Hache-Fixture-Deduplicated:'

code="$(request "$MAIN_COOKIE" duplicate POST /form-b \
  --data-urlencode "_csrf=$csrf" \
  --data-urlencode "submission_id=$submission" \
  --data-urlencode 'name=Ariel Example' \
  --data-urlencode 'email=ariel@example.test' \
  --data-urlencode 'message=Mensaje válido para la prueba.')"
[[ "$code" == "200" ]] || fail "duplicate_status=$code"
assert_header "$TMP/duplicate.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*1$'
assert_header "$TMP/duplicate.headers" '^X-Hache-Fixture-Deduplicated:[[:space:]]*true$'
grep -Fq 'data-form-state="success"' "$TMP/duplicate.body" || fail "duplicate_not_success_state"

# Separate anonymous session proves the fixture's deterministic rate-limit contract.
code="$(request "$RATE_COOKIE" rate-get GET /form-b)"
[[ "$code" == "200" ]] || fail "rate_get_status=$code"
rate_csrf="$(extract_csrf "$TMP/rate-get.body")"
rate_submission="$(extract_submission "$TMP/rate-get.body")"
[[ "$rate_csrf" =~ ^[a-f0-9]{64}$ ]] || fail "rate_invalid_csrf_shape"
[[ "$rate_submission" =~ ^[a-f0-9]{32}$ ]] || fail "rate_invalid_submission_shape"

for attempt in 1 2 3 4 5 6; do
  code="$(request "$RATE_COOKIE" "rate-$attempt" POST /form-b \
    --data-urlencode "_csrf=$rate_csrf" \
    --data-urlencode "submission_id=$rate_submission" \
    --data-urlencode 'name=Bot Example' \
    --data-urlencode 'email=bot@example.test' \
    --data-urlencode 'message=Mensaje suficiente para el honeypot.' \
    --data-urlencode 'company_website=https://bot.invalid')"
  [[ "$code" == "200" ]] || fail "rate_allowed_attempt=$attempt status=$code"
done

code="$(request "$RATE_COOKIE" rate-blocked POST /form-b \
  --data-urlencode "_csrf=$rate_csrf" \
  --data-urlencode "submission_id=$rate_submission" \
  --data-urlencode 'name=Bot Example' \
  --data-urlencode 'email=bot@example.test' \
  --data-urlencode 'message=Mensaje suficiente para el honeypot.' \
  --data-urlencode 'company_website=https://bot.invalid')"
[[ "$code" == "429" ]] || fail "rate_blocked_status=$code"
assert_header "$TMP/rate-blocked.headers" '^Retry-After:[[:space:]]*[1-9][0-9]*$'
grep -Fq 'data-form-state="error"' "$TMP/rate-blocked.body" || fail "rate_limit_not_error_state"
assert_header "$TMP/rate-blocked.headers" '^X-Hache-Fixture-Accepted-Count:[[:space:]]*0$'

echo "PRODUCTION_READINESS_FORM_B_OK"
