#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"
: "${TARGET_COMMIT:?TARGET_COMMIT is required}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required}"

cd "$APP_ROOT"

DEPLOY_RECORD_ROOT="${DEPLOY_RECORD_ROOT:-$BACKUP_ROOT/deploy-records}"
OBSERVATION_SECONDS="${OBSERVATION_SECONDS:-0}"
REQUIRE_SMOKE="${REQUIRE_SMOKE:-0}"
REQUIRE_OBSERVATION="${REQUIRE_OBSERVATION:-0}"

current_phase="started"
previous_commit=""
rollback_branch=""
deploy_record=""

sanitize_field() {
  local value="$1"
  value="${value//$'\n'/_}"
  value="${value//$'\r'/_}"
  value="${value//$'\t'/_}"
  value="${value// /_}"
  printf '%s' "$value"
}

current_commit() {
  git rev-parse HEAD 2>/dev/null || printf 'unknown'
}

format_state() {
  local state="$1"
  local status="$2"
  local detail="${3:-none}"

  printf 'DEPLOY_STATE timestamp=%s state=%s status=%s target_commit=%s current_commit=%s rollback_ref=%s detail=%s' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$(sanitize_field "$state")" \
    "$(sanitize_field "$status")" \
    "$(sanitize_field "$TARGET_COMMIT")" \
    "$(sanitize_field "$(current_commit)")" \
    "$(sanitize_field "${rollback_branch:-none}")" \
    "$(sanitize_field "$detail")"
}

emit_state() {
  local line
  line="$(format_state "$@")"
  printf '%s\n' "$line"
  if [[ -n "$deploy_record" ]]; then
    printf '%s\n' "$line" >> "$deploy_record"
  fi
}

on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  emit_state "failed" "failed" "failed_phase=${current_phase};exit_code=${exit_code}" || true
  printf 'DEPLOY_RECOVERY_REQUIRED failed_phase=%s exit_code=%s runbook=%s record=%s rollback_ref=%s\n' \
    "$(sanitize_field "$current_phase")" \
    "$exit_code" \
    "$APP_ROOT/deployment/DEPLOY-FAILURE-RUNBOOK.md" \
    "${deploy_record:-unavailable}" \
    "${rollback_branch:-unavailable}" >&2
  exit "$exit_code"
}
trap on_error ERR

for flag_name in REQUIRE_SMOKE REQUIRE_OBSERVATION; do
  flag_value="${!flag_name}"
  [[ "$flag_value" == "0" || "$flag_value" == "1" ]] || {
    echo "DEPLOY_CONFIG_FAILED $flag_name must be 0 or 1" >&2
    false
  }
done

[[ "$OBSERVATION_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
  echo "DEPLOY_CONFIG_FAILED OBSERVATION_SECONDS must be a non-negative number" >&2
  false
}

if [[ "$REQUIRE_SMOKE" == "1" && -z "${SMOKE_COMMAND:-}" && -z "${SMOKE_BASE_URL:-}" ]]; then
  echo "DEPLOY_CONFIG_FAILED smoke is required but SMOKE_COMMAND/SMOKE_BASE_URL is not configured" >&2
  false
fi

if [[ "$REQUIRE_OBSERVATION" == "1" && "$OBSERVATION_SECONDS" =~ ^0+([.]0+)?$ ]]; then
  echo "DEPLOY_CONFIG_FAILED observation is required but OBSERVATION_SECONDS is zero" >&2
  false
fi

started_line="$(format_state "started" "running" "runner_started")"
printf '%s\n' "$started_line"

bash "$APP_ROOT/deployment/preflight.sh"

install -d -m 700 "$DEPLOY_RECORD_ROOT"
stamp="$(date -u +%Y%m%d-%H%M%S)"
deploy_record="$DEPLOY_RECORD_ROOT/deploy-${stamp}-$$.log"
: > "$deploy_record"
chmod 600 "$deploy_record"
printf '%s\n' "$started_line" > "$deploy_record"
printf 'DEPLOY_RECORD_FILE=%s\n' "$deploy_record"

previous_commit="$(git rev-parse HEAD)"
rollback_branch="rollback/pre-deploy-${stamp}-$$"
git branch "$rollback_branch" "$previous_commit"
printf 'ROLLBACK_REF=%s\n' "$rollback_branch"

bash "$APP_ROOT/deployment/backup.sh"

git fetch origin --prune
git rev-parse --verify "${TARGET_COMMIT}^{commit}" >/dev/null
git checkout --detach "$TARGET_COMMIT"
emit_state "code_changed" "passed" "previous_commit=${previous_commit}"

current_phase="migrations"
if [[ -n "${MIGRATION_COMMAND:-}" ]]; then
  echo "Running configured migrations"
  bash -lc "$MIGRATION_COMMAND"
  emit_state "migrations_applied" "passed" "migration_command_configured"
else
  echo "No MIGRATION_COMMAND configured; migrations are not applicable in this runner execution"
  emit_state "migrations_applied" "not_applicable" "no_migration_command"
fi

current_phase="tests"
TEST_COMMAND="${TEST_COMMAND:-bash tests/run.sh}"
bash -lc "$TEST_COMMAND"
emit_state "tests_passed" "passed" "test_command_completed"

run_smoke() {
  current_phase="smoke"
  if [[ -n "${SMOKE_COMMAND:-}" ]]; then
    bash -lc "$SMOKE_COMMAND"
    echo "DEPLOY_SMOKE status=passed source=SMOKE_COMMAND"
    return 0
  fi

  if [[ -n "${SMOKE_BASE_URL:-}" ]]; then
    bash "$APP_ROOT/tests/smoke/http-smoke.sh" "$SMOKE_BASE_URL"
    echo "DEPLOY_SMOKE status=passed source=SMOKE_BASE_URL"
    return 0
  fi

  if [[ "$REQUIRE_SMOKE" == "1" ]]; then
    echo "DEPLOY_SMOKE status=failed reason=not_configured" >&2
    return 1
  fi

  echo "DEPLOY_SMOKE status=not_configured evidence=NOT_EVALUATED"
}

run_release_gates() {
  current_phase="readiness"
  bash "$APP_ROOT/deployment/health-check.sh"
  echo "DEPLOY_READINESS status=passed"
  run_smoke
}

run_release_gates

if [[ ! "$OBSERVATION_SECONDS" =~ ^0+([.]0+)?$ ]]; then
  current_phase="observation"
  printf 'DEPLOY_OBSERVATION status=started seconds=%s\n' "$OBSERVATION_SECONDS"
  sleep "$OBSERVATION_SECONDS"
  run_release_gates
  printf 'DEPLOY_OBSERVATION status=passed seconds=%s\n' "$OBSERVATION_SECONDS"
else
  echo "DEPLOY_OBSERVATION status=not_configured evidence=NOT_EVALUATED"
fi

current_phase="healthy"
emit_state "healthy" "passed" "release_gates_completed"
trap - ERR

echo "DEPLOY_OK $(git rev-parse HEAD) record=$deploy_record rollback_ref=$rollback_branch"
