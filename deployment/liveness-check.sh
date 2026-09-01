#!/usr/bin/env bash
set -Eeuo pipefail

: "${LIVENESS_URL:=${HEALTHCHECK_URL:-}}"
: "${LIVENESS_URL:?LIVENESS_URL or HEALTHCHECK_URL is required}"
EXPECTED_STATUS="${EXPECTED_LIVENESS_STATUS:-200}"
TIMEOUT="${LIVENESS_TIMEOUT:-${HEALTHCHECK_TIMEOUT:-10}}"

body_file="$(mktemp "${TMPDIR:-/tmp}/hache-base-liveness.XXXXXX")"
trap 'rm -f "$body_file"' EXIT

status="$(curl --silent --show-error --output "$body_file" --write-out '%{http_code}' --max-time "$TIMEOUT" "$LIVENESS_URL")"

if [[ "$status" != "$EXPECTED_STATUS" ]]; then
  echo "LIVENESS_FAILED expected=$EXPECTED_STATUS actual=$status" >&2
  exit 1
fi

echo "LIVENESS_OK"
