#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/hache-base-health-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
cat > "$TMP/bin/curl" <<'FAKECURL'
#!/usr/bin/env bash
set -Eeuo pipefail
output=""
while (($#)); do
  case "$1" in
    --output)
      output="$2"
      shift 2
      ;;
    --write-out|--max-time)
      shift 2
      ;;
    --silent|--show-error)
      shift
      ;;
    *)
      shift
      ;;
  esac
done
[[ -n "$output" ]] || { echo "fake curl missing --output" >&2; exit 9; }
printf '%s' "${MOCK_BODY:-}" > "$output"
printf '%s' "${MOCK_STATUS:-200}"
FAKECURL
chmod +x "$TMP/bin/curl"

run_health() {
  PATH="$TMP/bin:$PATH" \
  HEALTHCHECK_URL="https://example.test/ready" \
  "$ROOT/deployment/health-check.sh"
}

run_liveness() {
  PATH="$TMP/bin:$PATH" \
  LIVENESS_URL="https://example.test/live" \
  "$ROOT/deployment/liveness-check.sh"
}

run_smoke() {
  PATH="$TMP/bin:$PATH" \
  "$ROOT/tests/smoke/http-smoke.sh" "https://example.test"
}

MOCK_STATUS=200 MOCK_BODY='READY' EXPECTED_HEALTH_BODY='READY' run_health >/dev/null

if MOCK_STATUS=200 MOCK_BODY='WRONG' EXPECTED_HEALTH_BODY='READY' run_health >/dev/null 2>&1; then
  echo "Expected readiness body mismatch to fail" >&2
  exit 1
fi

MOCK_STATUS=200 MOCK_BODY='{"status":"ready","version":"abc123"}' EXPECTED_HEALTH_VERSION='abc123' run_health >/dev/null

if MOCK_STATUS=200 MOCK_BODY='{"status":"ready","version":"wrong"}' EXPECTED_HEALTH_VERSION='abc123' run_health >/dev/null 2>&1; then
  echo "Expected readiness version mismatch to fail" >&2
  exit 1
fi

MOCK_STATUS=200 MOCK_BODY='legacy' HEALTHCHECK_ALLOW_STATUS_ONLY=1 run_health >/dev/null 2>&1

if MOCK_STATUS=200 MOCK_BODY='legacy' HEALTHCHECK_ALLOW_STATUS_ONLY=0 run_health >/dev/null 2>&1; then
  echo "Expected strict readiness without content contract to fail" >&2
  exit 1
fi

MOCK_STATUS=200 MOCK_BODY='anything' run_liveness >/dev/null

if MOCK_STATUS=503 MOCK_BODY='down' run_liveness >/dev/null 2>&1; then
  echo "Expected liveness status mismatch to fail" >&2
  exit 1
fi

MOCK_STATUS=200 MOCK_BODY='SMOKE_OK_MARKER' SMOKE_PATH='/critical-flow-smoke' EXPECTED_SMOKE_BODY='SMOKE_OK_MARKER' run_smoke >/dev/null

if MOCK_STATUS=200 MOCK_BODY='WRONG' SMOKE_PATH='/critical-flow-smoke' EXPECTED_SMOKE_BODY='SMOKE_OK_MARKER' run_smoke >/dev/null 2>&1; then
  echo "Expected smoke body mismatch to fail" >&2
  exit 1
fi

echo "HEALTH_CHECK_TESTS_OK"
