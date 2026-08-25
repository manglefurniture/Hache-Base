#!/usr/bin/env bash
set -Eeuo pipefail

: "${HEALTHCHECK_URL:?HEALTHCHECK_URL is required}"
EXPECTED="${EXPECTED_HEALTH_STATUS:-200}"

status="$(curl --silent --show-error --output /tmp/hache-base-health-body --write-out '%{http_code}' --max-time "${HEALTHCHECK_TIMEOUT:-15}" "$HEALTHCHECK_URL")"

if [[ "$status" != "$EXPECTED" ]]; then
  echo "HEALTHCHECK_FAILED expected=$EXPECTED actual=$status" >&2
  cat /tmp/hache-base-health-body >&2 || true
  exit 1
fi

echo "HEALTHCHECK_OK"
