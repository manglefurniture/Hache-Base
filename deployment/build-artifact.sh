#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_ROOT:?APP_ROOT is required}"
: "${TARGET_COMMIT:?TARGET_COMMIT is required}"
: "${ARTIFACT_CONTENT_DIR:?ARTIFACT_CONTENT_DIR is required}"
: "${ARTIFACT_PATH:?ARTIFACT_PATH is required}"
: "${ARTIFACT_MANIFEST:?ARTIFACT_MANIFEST is required}"
: "${ARTIFACT_TEST_COMMAND:?ARTIFACT_TEST_COMMAND is required}"
: "${CI_RUN_REF:?CI_RUN_REF is required}"
: "${BUILD_EVIDENCE_REF:?BUILD_EVIDENCE_REF is required}"
: "${TEST_EVIDENCE_REF:?TEST_EVIDENCE_REF is required}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARTIFACT_BUILD_COMMAND="${ARTIFACT_BUILD_COMMAND:-:}"

for command in git tar gzip php realpath mktemp; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "BUILD_ARTIFACT_FAILED missing_command=$command" >&2
    exit 2
  }
done

[[ "$TARGET_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "BUILD_ARTIFACT_FAILED invalid_target_commit" >&2
  exit 2
}
TARGET_COMMIT="${TARGET_COMMIT,,}"

APP_ROOT_REAL="$(realpath -e "$APP_ROOT")"
[[ -d "$APP_ROOT_REAL/.git" || "$(git -C "$APP_ROOT_REAL" rev-parse --is-inside-work-tree 2>/dev/null || true)" == "true" ]] || {
  echo "BUILD_ARTIFACT_FAILED app_root_not_git_worktree" >&2
  exit 2
}

cd "$APP_ROOT_REAL"
HEAD_COMMIT="$(git rev-parse HEAD | tr '[:upper:]' '[:lower:]')"
[[ "$HEAD_COMMIT" == "$TARGET_COMMIT" ]] || {
  echo "BUILD_ARTIFACT_FAILED head_commit_mismatch expected=$TARGET_COMMIT actual=$HEAD_COMMIT" >&2
  exit 1
}

if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "BUILD_ARTIFACT_FAILED source_worktree_not_clean" >&2
  exit 1
fi

ARTIFACT_PATH_ABS="$(realpath -m "$ARTIFACT_PATH")"
ARTIFACT_MANIFEST_ABS="$(realpath -m "$ARTIFACT_MANIFEST")"

run_phase() {
  local phase="$1"
  local command_text="$2"

  echo "BUILD_ARTIFACT_PHASE phase=$phase status=started source_commit=$TARGET_COMMIT"
  if bash -lc "$command_text"; then
    echo "BUILD_ARTIFACT_PHASE phase=$phase status=passed source_commit=$TARGET_COMMIT"
  else
    local exit_code=$?
    echo "BUILD_ARTIFACT_PHASE phase=$phase status=failed source_commit=$TARGET_COMMIT exit_code=$exit_code" >&2
    return "$exit_code"
  fi
}

run_phase build "$ARTIFACT_BUILD_COMMAND"

CONTENT_REAL="$(realpath -e "$ARTIFACT_CONTENT_DIR")"
[[ -d "$CONTENT_REAL" ]] || {
  echo "BUILD_ARTIFACT_FAILED content_dir_not_directory" >&2
  exit 2
}
[[ "$CONTENT_REAL" != "/" ]] || {
  echo "BUILD_ARTIFACT_FAILED content_dir_cannot_be_root" >&2
  exit 2
}

is_within_content() {
  local candidate="$1"
  [[ "$candidate" == "$CONTENT_REAL" || "$candidate" == "$CONTENT_REAL"/* ]]
}

if is_within_content "$ARTIFACT_PATH_ABS" || is_within_content "$ARTIFACT_MANIFEST_ABS"; then
  echo "BUILD_ARTIFACT_FAILED output_must_be_outside_content_dir" >&2
  exit 2
fi

run_phase tests "$ARTIFACT_TEST_COMMAND"

ARTIFACT_DIR="$(dirname "$ARTIFACT_PATH_ABS")"
MANIFEST_DIR="$(dirname "$ARTIFACT_MANIFEST_ABS")"
mkdir -p "$ARTIFACT_DIR" "$MANIFEST_DIR"

TMP_ARTIFACT="$(mktemp "$ARTIFACT_DIR/.hache-artifact-XXXXXX.tar.gz")"
cleanup() {
  rm -f "$TMP_ARTIFACT"
}
trap cleanup EXIT

# Package only after build and tests have succeeded. The deploy side receives this
# exact byte stream; it does not rebuild or retest in production.
tar -C "$CONTENT_REAL" --exclude='.git' -czf "$TMP_ARTIFACT" .
mv -f "$TMP_ARTIFACT" "$ARTIFACT_PATH_ABS"
TMP_ARTIFACT=""
chmod 600 "$ARTIFACT_PATH_ABS"

export ARTIFACT_PATH="$ARTIFACT_PATH_ABS"
export ARTIFACT_MANIFEST="$ARTIFACT_MANIFEST_ABS"
export SOURCE_COMMIT="$TARGET_COMMIT"
php "$SCRIPT_DIR/artifact-manifest.php" create

# Re-verify immediately so a malformed/partial manifest can never leave this helper
# with a success status.
export EXPECTED_COMMIT="$TARGET_COMMIT"
php "$SCRIPT_DIR/artifact-manifest.php" verify

ARTIFACT_SHA256="$(sha256sum "$ARTIFACT_PATH_ABS" | awk '{print $1}')"
echo "BUILD_ARTIFACT_OK source_commit=$TARGET_COMMIT sha256=$ARTIFACT_SHA256 artifact=$ARTIFACT_PATH_ABS manifest=$ARTIFACT_MANIFEST_ABS"
