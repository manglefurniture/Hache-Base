#!/usr/bin/env bash
set -Eeuo pipefail

: "${HEALTHCHECK_URL:?HEALTHCHECK_URL is required}"
EXPECTED_STATUS="${EXPECTED_HEALTH_STATUS:-200}"
EXPECTED_BODY="${EXPECTED_HEALTH_BODY:-}"
EXPECTED_VERSION="${EXPECTED_HEALTH_VERSION:-}"
ALLOW_STATUS_ONLY="${HEALTHCHECK_ALLOW_STATUS_ONLY:-1}"
TIMEOUT="${HEALTHCHECK_TIMEOUT:-15}"

body_file="$(mktemp "${TMPDIR:-/tmp}/hache-base-health.XXXXXX")"
trap 'rm -f "$body_file"' EXIT

status="$(curl --silent --show-error --output "$body_file" --write-out '%{http_code}' --max-time "$TIMEOUT" "$HEALTHCHECK_URL")"

if [[ "$status" != "$EXPECTED_STATUS" ]]; then
  echo "HEALTHCHECK_FAILED reason=status expected=$EXPECTED_STATUS actual=$status" >&2
  cat "$body_file" >&2 || true
  exit 1
fi

if [[ -n "$EXPECTED_BODY" ]]; then
  actual_body="$(cat "$body_file")"
  if [[ "$actual_body" != "$EXPECTED_BODY" ]]; then
    echo "HEALTHCHECK_FAILED reason=body_mismatch" >&2
    exit 1
  fi
fi

if [[ -n "$EXPECTED_VERSION" ]]; then
  if ! actual_version="$(php -r '
    $raw = file_get_contents($argv[1]);
    $data = json_decode($raw, true);
    if (!is_array($data) || !array_key_exists("version", $data) || !is_scalar($data["version"])) {
        fwrite(STDERR, "HEALTHCHECK_FAILED reason=version_unreadable\n");
        exit(3);
    }
    echo (string)$data["version"];
  ' "$body_file")"; then
    exit 1
  fi

  if [[ "$actual_version" != "$EXPECTED_VERSION" ]]; then
    echo "HEALTHCHECK_FAILED reason=version_mismatch expected=$EXPECTED_VERSION actual=$actual_version" >&2
    exit 1
  fi
fi

if [[ -z "$EXPECTED_BODY" && -z "$EXPECTED_VERSION" ]]; then
  if [[ "$ALLOW_STATUS_ONLY" != "1" ]]; then
    echo "HEALTHCHECK_FAILED reason=no_content_contract Configure EXPECTED_HEALTH_BODY or EXPECTED_HEALTH_VERSION." >&2
    exit 1
  fi
  echo "HEALTHCHECK_WARNING status-only compatibility mode; configure body/version validation for readiness." >&2
fi

echo "HEALTHCHECK_OK"
