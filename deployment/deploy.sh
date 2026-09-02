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

current_phase="configuration"
previous_commit=""
rollback_branch=""
rollback_branch_candidate=""
deploy_record=""
deploy_id=""

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

emit_gate() {
  local gate="$1"
  local status="$2"
  local detail="${3:-none}"
  local line
  line="DEPLOY_GATE timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ) gate=$(sanitize_field "$gate") status=$(sanitize_field "$status") target_commit=$(sanitize_field "$TARGET_COMMIT") current_commit=$(sanitize_field "$(current_commit)") detail=$(sanitize_field "$detail")"
  printf '%s\n' "$line"
  if [[ -n "$deploy_record" ]]; then
    printf '%s\n' "$line" >> "$deploy_record"
  fi
}

validate_record_root_outside_worktree() {
  # Missing tools are reported by preflight. Avoid masking that error here.
  command -v git >/dev/null 2>&1 || return 0
  command -v realpath >/dev/null 2>&1 || return 0

  local git_root git_root_real record_root_real
  git_root="$(git -C "$APP_ROOT" rev-parse --show-toplevel 2>/dev/null)" || {
    echo "DEPLOY_CONFIG_FAILED APP_ROOT must be inside a Git working tree" >&2
    return 1
  }
  git_root_real="$(realpath -e "$git_root")"
  record_root_real="$(realpath -m "$DEPLOY_RECORD_ROOT")"

  case "$record_root_real" in
    "$git_root_real"|"$git_root_real"/*)
      echo "DEPLOY_CONFIG_FAILED DEPLOY_RECORD_ROOT must be outside the Git working tree" >&2
      return 1
      ;;
  esac

  DEPLOY_RECORD_ROOT="$record_root_real"
}

on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  emit_state "failed" "failed" "failed_phase=${current_phase};exit_code=${exit_code}" || true
  printf 'DEPLOY_RECOVERY_REQUIRED failed_phase=%s exit_code=%s runbook=%s record=%s rollback_ref=%s\n' \
    "$(sanitize_field "$current_phase")" \
    "$exit_code" \
    "$(sanitize_field "$APP_ROOT/deployment/DEPLOY-FAILURE-RUNBOOK.md")" \
    "$(sanitize_field "${deploy_record:-unavailable}")" \
    "$(sanitize_field "${rollback_branch:-unavailable}")" >&2
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

# Validate before preflight can create BACKUP_ROOT when the record root inherits it.
validate_record_root_outside_worktree

current_phase="started"
started_line="$(format_state "started" "running" "runner_started")"
printf '%s\n' "$started_line"

current_phase="preflight"
bash "$APP_ROOT/deployment/preflight.sh"

current_phase="deploy_record"
# Re-resolve after preflight so existing/symlinked path components are checked physically.
validate_record_root_outside_worktree
stamp="$(date -u +%Y%m%d-%H%M%S)"
deploy_record="$(
  umask 077
  install -d -m 700 "$DEPLOY_RECORD_ROOT"
  mktemp "$DEPLOY_RECORD_ROOT/deploy-${stamp}-XXXXXX.log"
)"
chmod 600 "$deploy_record"
printf '%s\n' "$started_line" > "$deploy_record"
deploy_file="${deploy_record##*/}"
deploy_id="${deploy_file%.log}"
printf 'DEPLOY_RECORD_FILE=%s\n' "$deploy_record"

current_phase="rollback_ref"
previous_commit="$(git rev-parse HEAD)"
rollback_branch_candidate="rollback/pre-${deploy_id}"
git branch "$rollback_branch_candidate" "$previous_commit"
rollback_branch="$rollback_branch_candidate"
printf 'ROLLBACK_REF=%s\n' "$rollback_branch"

current_phase="backup"
bash "$APP_ROOT/deployment/backup.sh"

current_phase="code_change"
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
  local exit_code
  current_phase="smoke"

  if [[ -n "${SMOKE_COMMAND:-}" ]]; then
    if bash -lc "$SMOKE_COMMAND"; then
      emit_gate "smoke" "passed" "source=SMOKE_COMMAND"
      return 0
    else
      exit_code=$?
      emit_gate "smoke" "failed" "source=SMOKE_COMMAND;exit_code=${exit_code}"
      return "$exit_code"
    fi
  fi

  if [[ -n "${SMOKE_BASE_URL:-}" ]]; then
    if bash "$APP_ROOT/tests/smoke/http-smoke.sh" "$SMOKE_BASE_URL"; then
      emit_gate "smoke" "passed" "source=SMOKE_BASE_URL"
      return 0
    else
      exit_code=$?
      emit_gate "smoke" "failed" "source=SMOKE_BASE_URL;exit_code=${exit_code}"
      return "$exit_code"
    fi
  fi

  if [[ "$REQUIRE_SMOKE" == "1" ]]; then
    emit_gate "smoke" "failed" "reason=not_configured"
    return 1
  fi

  emit_gate "smoke" "not_evaluated" "evidence=NOT_EVALUATED;reason=not_configured"
}

run_release_gates() {
  local exit_code
  current_phase="readiness"
  if bash "$APP_ROOT/deployment/health-check.sh"; then
    emit_gate "readiness" "passed" "health_check_completed"
  else
    exit_code=$?
    emit_gate "readiness" "failed" "exit_code=${exit_code}"
    return "$exit_code"
  fi

  run_smoke
}

run_release_gates

if [[ ! "$OBSERVATION_SECONDS" =~ ^0+([.]0+)?$ ]]; then
  current_phase="observation"
  emit_gate "observation" "running" "seconds=${OBSERVATION_SECONDS}"
  sleep "$OBSERVATION_SECONDS"
  run_release_gates
  current_phase="observation"
  emit_gate "observation" "passed" "seconds=${OBSERVATION_SECONDS}"
else
  emit_gate "observation" "not_evaluated" "evidence=NOT_EVALUATED;reason=not_configured"
fi

current_phase="healthy"
emit_state "healthy" "passed" "release_gates_completed"
trap - ERR

echo "DEPLOY_OK $(git rev-parse HEAD) record=$deploy_record rollback_ref=$rollback_branch"
