#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"
ROLLBACK_REF="${1:-${ROLLBACK_REF:-}}"
[[ -n "$ROLLBACK_REF" ]] || { echo "Provide a rollback commit/ref" >&2; exit 2; }

cd "$APP_ROOT"

git diff --quiet && git diff --cached --quiet || {
  echo "Refusing rollback: working tree has uncommitted changes" >&2
  exit 1
}

git fetch origin --prune
git rev-parse --verify "${ROLLBACK_REF}^{commit}" >/dev/null

git checkout --detach "$ROLLBACK_REF"

current_commit="$(git rev-parse HEAD)"
echo "CODE_ROLLBACK_OK $current_commit"
echo "Database restoration is intentionally separate; restore only from a verified backup when required by the migration history."

sanitize_field() {
  local value="$1"
  value="${value//$'\n'/_}"
  value="${value//$'\r'/_}"
  value="${value//$'\t'/_}"
  value="${value// /_}"
  printf '%s' "$value"
}

target_commit="${TARGET_COMMIT:-unknown}"
if [[ -n "${DEPLOY_RECORD_FILE:-}" && -f "$DEPLOY_RECORD_FILE" ]]; then
  recorded_target="$(sed -n '1s/.* target_commit=\([^ ]*\).*/\1/p' "$DEPLOY_RECORD_FILE")"
  if [[ -n "$recorded_target" ]]; then
    target_commit="$recorded_target"
  fi
fi

recovery_line="DEPLOY_STATE timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ) state=rolled_back status=passed target_commit=$(sanitize_field "$target_commit") current_commit=$(sanitize_field "$current_commit") rollback_ref=$(sanitize_field "$ROLLBACK_REF") detail=code_rollback_completed"
printf '%s\n' "$recovery_line"

if [[ -n "${DEPLOY_RECORD_FILE:-}" ]]; then
  if [[ -f "$DEPLOY_RECORD_FILE" && -w "$DEPLOY_RECORD_FILE" ]]; then
    if ! printf '%s\n' "$recovery_line" >> "$DEPLOY_RECORD_FILE"; then
      echo "ROLLBACK_RECORD_WARNING unable to append deploy record: $DEPLOY_RECORD_FILE" >&2
    fi
  else
    echo "ROLLBACK_RECORD_WARNING deploy record is not writable: $DEPLOY_RECORD_FILE" >&2
  fi
fi
