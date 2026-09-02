#!/usr/bin/env bash
set -Eeuo pipefail

: "${DEPLOY_RECORD_FILE:?DEPLOY_RECORD_FILE is required}"

state="${1:-}"
detail="${2:-operator_recorded}"
[[ "$state" == "manual_recovery" || "$state" == "rolled_back" ]] || {
  echo "Usage: DEPLOY_RECORD_FILE=/path/to/record $0 <manual_recovery|rolled_back> [detail]" >&2
  exit 2
}

[[ -f "$DEPLOY_RECORD_FILE" && -w "$DEPLOY_RECORD_FILE" ]] || {
  echo "DEPLOY_RECOVERY_RECORD_FAILED record is not writable: $DEPLOY_RECORD_FILE" >&2
  exit 1
}

sanitize_field() {
  local value="$1"
  value="${value//$'\n'/_}"
  value="${value//$'\r'/_}"
  value="${value//$'\t'/_}"
  value="${value// /_}"
  printf '%s' "$value"
}

target_commit="$(sed -n '1s/.* target_commit=\([^ ]*\).*/\1/p' "$DEPLOY_RECORD_FILE")"
[[ -n "$target_commit" ]] || target_commit="${TARGET_COMMIT:-unknown}"

current_commit="unknown"
if [[ -n "${APP_ROOT:-}" ]] && git -C "$APP_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  current_commit="$(git -C "$APP_ROOT" rev-parse HEAD 2>/dev/null || printf 'unknown')"
fi

rollback_ref="${ROLLBACK_REF:-none}"
line="DEPLOY_STATE timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ) state=$(sanitize_field "$state") status=passed target_commit=$(sanitize_field "$target_commit") current_commit=$(sanitize_field "$current_commit") rollback_ref=$(sanitize_field "$rollback_ref") detail=$(sanitize_field "$detail")"
printf '%s\n' "$line" | tee -a "$DEPLOY_RECORD_FILE"
