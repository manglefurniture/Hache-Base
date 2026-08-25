#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"
: "${TARGET_COMMIT:?TARGET_COMMIT is required}"

cd "$APP_ROOT"

bash "$APP_ROOT/deployment/preflight.sh"

previous_commit="$(git rev-parse HEAD)"
stamp="$(date -u +%Y%m%d-%H%M%S)"
rollback_branch="rollback/pre-deploy-${stamp}"
git branch "$rollback_branch" "$previous_commit"
echo "ROLLBACK_REF=$rollback_branch"

bash "$APP_ROOT/deployment/backup.sh"

git fetch origin --prune
git rev-parse --verify "${TARGET_COMMIT}^{commit}" >/dev/null
git checkout --detach "$TARGET_COMMIT"

if [[ -n "${MIGRATION_COMMAND:-}" ]]; then
  echo "Running configured migrations"
  bash -lc "$MIGRATION_COMMAND"
else
  echo "No MIGRATION_COMMAND configured; skipping migrations"
fi

TEST_COMMAND="${TEST_COMMAND:-bash tests/run.sh}"
bash -lc "$TEST_COMMAND"

bash "$APP_ROOT/deployment/health-check.sh"

echo "DEPLOY_OK $(git rev-parse HEAD)"
