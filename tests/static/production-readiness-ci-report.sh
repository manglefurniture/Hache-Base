#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPORTER="$ROOT/tools/production-readiness/report.php"

cleanup=0
if [[ -n "${READINESS_REPORT_DIR:-}" ]]; then
  OUT_DIR="$READINESS_REPORT_DIR"
  mkdir -p "$OUT_DIR"
else
  OUT_DIR="$(mktemp -d)"
  cleanup=1
fi

if [[ "$cleanup" -eq 1 ]]; then
  trap 'rm -rf "$OUT_DIR"' EXIT
fi

for level in A B C; do
  php "$REPORTER" \
    --level "$level" \
    --json "$OUT_DIR/level-$level.json" \
    --markdown "$OUT_DIR/level-$level.md"

  test -s "$OUT_DIR/level-$level.json"
  test -s "$OUT_DIR/level-$level.md"
  grep -q '"decision": "NOT_A_PRODUCTION_READY_DECLARATION"' "$OUT_DIR/level-$level.json"
  grep -q "Production Readiness CI report — Level $level" "$OUT_DIR/level-$level.md"
done

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "# Hache Base — Production Readiness projections"
    echo ""
    echo "> P1-01 genera evidencia derivada; un CI verde no declara Production Ready."
    for level in A B C; do
      echo ""
      echo "---"
      echo ""
      cat "$OUT_DIR/level-$level.md"
    done
  } >> "$GITHUB_STEP_SUMMARY"
fi

echo "PRODUCTION_READINESS_CI_REPORT_OK"
