#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${1:-${SMOKE_BASE_URL:-}}"
[[ -n "$BASE_URL" ]] || { echo "Usage: http-smoke.sh https://staging.example.com" >&2; exit 2; }

SMOKE_PATH="${SMOKE_PATH:-${HEALTH_PATH:-/health}}"
EXPECTED_STATUS="${EXPECTED_SMOKE_STATUS:-${EXPECTED_HEALTH_STATUS:-200}}"
EXPECTED_BODY="${EXPECTED_SMOKE_BODY:-}"
TIMEOUT="${SMOKE_TIMEOUT:-15}"

body_file="$(mktemp "${TMPDIR:-/tmp}/hache-base-smoke.XXXXXX")"
trap 'rm -f "$body_file"' EXIT

url="${BASE_URL%/}${SMOKE_PATH}"
status="$(curl --silent --show-error --output "$body_file" --write-out '%{http_code}' --max-time "$TIMEOUT" "$url")"

if [[ "$status" != "$EXPECTED_STATUS" ]]; then
  echo "SMOKE_FAILED reason=status expected=$EXPECTED_STATUS actual=$status" >&2
  cat "$body_file" >&2 || true
  exit 1
fi

if [[ -n "$EXPECTED_BODY" && "$(cat "$body_file")" != "$EXPECTED_BODY" ]]; then
  echo "SMOKE_FAILED reason=body_mismatch" >&2
  exit 1
fi

echo "SMOKE_OK $url"
