#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${1:-${SMOKE_BASE_URL:-}}"
[[ -n "$BASE_URL" ]] || { echo "Usage: http-smoke.sh https://staging.example.com" >&2; exit 2; }

HEALTH_PATH="${HEALTH_PATH:-/health}"
EXPECTED_STATUS="${EXPECTED_HEALTH_STATUS:-200}"

status="$(curl --silent --show-error --output /tmp/hache-base-smoke-body --write-out '%{http_code}' --max-time 15 "${BASE_URL%/}${HEALTH_PATH}")"

if [[ "$status" != "$EXPECTED_STATUS" ]]; then
  echo "SMOKE_FAILED expected=$EXPECTED_STATUS actual=$status" >&2
  cat /tmp/hache-base-smoke-body >&2 || true
  exit 1
fi

echo "SMOKE_OK ${BASE_URL%/}${HEALTH_PATH}"
