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

for command in git tar gzip php realpath mktemp sha256sum awk mv rm mkdir chmod dirname; do
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
[[ "$ARTIFACT_PATH_ABS" != "$ARTIFACT_MANIFEST_ABS" ]] || {
  echo "BUILD_ARTIFACT_FAILED artifact_manifest_path_collision" >&2
  exit 2
}

for output_path in "$ARTIFACT_PATH_ABS" "$ARTIFACT_MANIFEST_ABS"; do
  if [[ -d "$output_path" && ! -L "$output_path" ]]; then
    echo "BUILD_ARTIFACT_FAILED output_target_is_directory path=$output_path" >&2
    exit 2
  fi

  case "$output_path" in
    "$APP_ROOT_REAL"/*)
      relative_path="${output_path#"$APP_ROOT_REAL"/}"
      if git ls-files --error-unmatch -- "$relative_path" >/dev/null 2>&1; then
        echo "BUILD_ARTIFACT_FAILED output_target_is_tracked_source path=$relative_path" >&2
        exit 2
      fi
      ;;
  esac
done

QUARANTINE_ROOT="${ARTIFACT_QUARANTINE_ROOT:-$(dirname "$ARTIFACT_PATH_ABS")/.hache-artifact-quarantine}"
QUARANTINE_DIR=""
TMP_ARTIFACT=""
build_success=0

ensure_quarantine_dir() {
  if [[ -n "$QUARANTINE_DIR" ]]; then
    return 0
  fi

  mkdir -p "$QUARANTINE_ROOT"
  QUARANTINE_ROOT="$(realpath -e "$QUARANTINE_ROOT")"
  QUARANTINE_DIR="$(mktemp -d "$QUARANTINE_ROOT/run-XXXXXX")"
  chmod 700 "$QUARANTINE_DIR"
}

quarantine_path() {
  local source_path="$1"
  local label="$2"

  if [[ ! -e "$source_path" && ! -L "$source_path" ]]; then
    return 0
  fi

  ensure_quarantine_dir
  mv -- "$source_path" "$QUARANTINE_DIR/$label"
  echo "BUILD_ARTIFACT_QUARANTINED label=$label path=$QUARANTINE_DIR/$label"
}

cleanup() {
  local exit_code=$?
  set +e

  if [[ -n "$TMP_ARTIFACT" ]]; then
    rm -f -- "$TMP_ARTIFACT"
  fi

  if [[ "$build_success" != "1" ]]; then
    # Never leave an advertised artifact/manifest path populated after a failed
    # invocation. Anything created by build/test/package is preserved off-path.
    quarantine_path "$ARTIFACT_PATH_ABS" "artifact.failed" >/dev/null 2>&1 || true
    quarantine_path "$ARTIFACT_MANIFEST_ABS" "manifest.failed" >/dev/null 2>&1 || true
    if [[ -n "$QUARANTINE_DIR" ]]; then
      echo "BUILD_ARTIFACT_QUARANTINE_PRESERVED path=$QUARANTINE_DIR" >&2
    fi
  elif [[ -n "$QUARANTINE_DIR" ]]; then
    rm -rf -- "$QUARANTINE_DIR"
  fi

  return "$exit_code"
}
trap cleanup EXIT

# A retry can reuse configured paths, but prior bytes are moved away before any
# fallible build/test phase. This prevents later upload/promotion steps from seeing
# a previous successful pair after the current invocation fails.
quarantine_path "$ARTIFACT_PATH_ABS" "artifact.previous"
quarantine_path "$ARTIFACT_MANIFEST_ABS" "manifest.previous"

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

# Build/test commands do not own release output paths. Move accidental writes away
# and fail rather than assigning them the manifest/evidence of this packaging step.
if [[ -e "$ARTIFACT_PATH_ABS" || -L "$ARTIFACT_PATH_ABS" ]]; then
  quarantine_path "$ARTIFACT_PATH_ABS" "artifact.created-by-phase"
  echo "BUILD_ARTIFACT_FAILED artifact_target_created_by_phase" >&2
  exit 2
fi
if [[ -e "$ARTIFACT_MANIFEST_ABS" || -L "$ARTIFACT_MANIFEST_ABS" ]]; then
  quarantine_path "$ARTIFACT_MANIFEST_ABS" "manifest.created-by-phase"
  echo "BUILD_ARTIFACT_FAILED manifest_target_created_by_phase" >&2
  exit 2
fi

ARTIFACT_DIR="$(dirname "$ARTIFACT_PATH_ABS")"
MANIFEST_DIR="$(dirname "$ARTIFACT_MANIFEST_ABS")"
mkdir -p "$ARTIFACT_DIR" "$MANIFEST_DIR"

TMP_ARTIFACT="$(mktemp "$ARTIFACT_DIR/.hache-artifact-XXXXXX.tar.gz")"

# Package only after build and tests have succeeded. The deploy side receives this
# exact byte stream; it does not rebuild or retest in production.
tar -C "$CONTENT_REAL" --exclude='.git' -czf "$TMP_ARTIFACT" .
mv -- "$TMP_ARTIFACT" "$ARTIFACT_PATH_ABS"
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
build_success=1
echo "BUILD_ARTIFACT_OK source_commit=$TARGET_COMMIT sha256=$ARTIFACT_SHA256 artifact=$ARTIFACT_PATH_ABS manifest=$ARTIFACT_MANIFEST_ABS"
