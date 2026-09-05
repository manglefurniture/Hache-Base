#!/usr/bin/env bash
set -Eeuo pipefail

: "${ARTIFACT_PATH:?ARTIFACT_PATH is required}"
: "${ARTIFACT_MANIFEST:?ARTIFACT_MANIFEST is required}"
: "${EXPECTED_COMMIT:?EXPECTED_COMMIT is required}"
: "${PROMOTE_COMMAND:?PROMOTE_COMMAND is required}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMOTION_WORK_ROOT="${PROMOTION_WORK_ROOT:-${TMPDIR:-/tmp}}"

for command in php realpath mktemp cp chmod mkdir rm basename; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "ARTIFACT_PROMOTION_FAILED missing_command=$command" >&2
    exit 2
  }
done

[[ "$EXPECTED_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "ARTIFACT_PROMOTION_FAILED invalid_expected_commit" >&2
  exit 2
}
EXPECTED_COMMIT="${EXPECTED_COMMIT,,}"

SOURCE_ARTIFACT="$(realpath -e "$ARTIFACT_PATH")"
SOURCE_MANIFEST="$(realpath -e "$ARTIFACT_MANIFEST")"
[[ -f "$SOURCE_ARTIFACT" && -f "$SOURCE_MANIFEST" ]] || {
  echo "ARTIFACT_PROMOTION_FAILED artifact_or_manifest_not_file" >&2
  exit 2
}

mkdir -p "$PROMOTION_WORK_ROOT"
PROMOTION_WORK_ROOT="$(realpath -e "$PROMOTION_WORK_ROOT")"
SNAPSHOT_DIR="$(mktemp -d "$PROMOTION_WORK_ROOT/hache-artifact-promotion-XXXXXX")"
chmod 700 "$SNAPSHOT_DIR"

cleanup() {
  rm -rf -- "$SNAPSHOT_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

SNAPSHOT_ARTIFACT="$SNAPSHOT_DIR/$(basename "$SOURCE_ARTIFACT")"
SNAPSHOT_MANIFEST="$SNAPSHOT_DIR/$(basename "$SOURCE_MANIFEST")"
cp -- "$SOURCE_ARTIFACT" "$SNAPSHOT_ARTIFACT"
cp -- "$SOURCE_MANIFEST" "$SNAPSHOT_MANIFEST"
chmod 400 "$SNAPSHOT_ARTIFACT" "$SNAPSHOT_MANIFEST"

export ARTIFACT_PATH="$SNAPSHOT_ARTIFACT"
export ARTIFACT_MANIFEST="$SNAPSHOT_MANIFEST"
export EXPECTED_COMMIT
VERIFY_OUTPUT="$(php "$SCRIPT_DIR/artifact-manifest.php" verify)"
printf '%s\n' "$VERIFY_OUTPUT"

if [[ ! "$VERIFY_OUTPUT" =~ ^ARTIFACT_VERIFY_OK\ source_commit=([0-9a-f]{40})\ sha256=([0-9a-f]{64})\ size=([0-9]+)$ ]]; then
  echo "ARTIFACT_PROMOTION_FAILED verifier_output_contract" >&2
  exit 2
fi

VERIFIED_SOURCE_COMMIT="${BASH_REMATCH[1]}"
VERIFIED_ARTIFACT_SHA256="${BASH_REMATCH[2]}"
VERIFIED_ARTIFACT_SIZE="${BASH_REMATCH[3]}"
export VERIFIED_ARTIFACT_PATH="$SNAPSHOT_ARTIFACT"
export VERIFIED_ARTIFACT_MANIFEST="$SNAPSHOT_MANIFEST"
export VERIFIED_SOURCE_COMMIT VERIFIED_ARTIFACT_SHA256 VERIFIED_ARTIFACT_SIZE

# PROMOTE_COMMAND is project-owned and must synchronously consume/copy the verified
# snapshot before returning. This boundary deliberately does not build or run the
# pre-release test suite again in production.
echo "ARTIFACT_PROMOTION_GATE status=verified source_commit=$VERIFIED_SOURCE_COMMIT sha256=$VERIFIED_ARTIFACT_SHA256"
if bash -lc "$PROMOTE_COMMAND"; then
  :
else
  exit_code=$?
  echo "ARTIFACT_PROMOTION_FAILED promote_command exit_code=$exit_code source_commit=$VERIFIED_SOURCE_COMMIT" >&2
  exit "$exit_code"
fi

echo "ARTIFACT_PROMOTION_OK source_commit=$VERIFIED_SOURCE_COMMIT sha256=$VERIFIED_ARTIFACT_SHA256 size=$VERIFIED_ARTIFACT_SIZE"
