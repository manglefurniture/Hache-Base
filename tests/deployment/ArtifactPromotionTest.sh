#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE="$ROOT/templates/ARTIFACT-PROMOTION.md"

for fragment in \
  'build una sola vez' \
  'digest + commit' \
  'no auto-PASS' \
  'No construir cambios no revisados directamente en producción' \
  'P2-06'; do
  grep -Fq "$fragment" "$TEMPLATE" || {
    echo "ERROR: missing artifact promotion template fragment: $fragment" >&2
    exit 1
  }
done

TMP="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP"
}
trap cleanup EXIT

SOURCE="$TMP/source"
STAGE="$TMP/stage"
OUT="$TMP/out"
DEPLOYED="$TMP/deployed.tar.gz"
mkdir -p "$SOURCE/deployment" "$OUT"
cp "$ROOT/deployment/artifact-manifest.php" "$SOURCE/deployment/artifact-manifest.php"
cp "$ROOT/deployment/build-artifact.sh" "$SOURCE/deployment/build-artifact.sh"

cd "$SOURCE"
git init -q
git config user.name 'Hache Test'
git config user.email 'test@example.invalid'
printf 'hello artifact\n' > app.txt
git add app.txt deployment
git commit -qm 'fixture source'
TARGET="$(git rev-parse HEAD)"

export FIXTURE_STAGE="$STAGE"
export APP_ROOT="$SOURCE"
export TARGET_COMMIT="$TARGET"
export ARTIFACT_CONTENT_DIR="$STAGE"
export ARTIFACT_PATH="$OUT/release.tar.gz"
export ARTIFACT_MANIFEST="$OUT/release.manifest.json"
export ARTIFACT_BUILD_COMMAND='mkdir -p "$FIXTURE_STAGE"; cp app.txt "$FIXTURE_STAGE/app.txt"'
export ARTIFACT_TEST_COMMAND='test -f "$FIXTURE_STAGE/app.txt"; grep -q "hello artifact" "$FIXTURE_STAGE/app.txt"'
export CI_RUN_REF='fixture://ci/run-1'
export BUILD_EVIDENCE_REF='fixture://ci/run-1/build'
export TEST_EVIDENCE_REF='fixture://ci/run-1/tests'

bash "$ROOT/deployment/build-artifact.sh" > "$TMP/build.log"
grep -q '^BUILD_ARTIFACT_OK ' "$TMP/build.log"
test -s "$ARTIFACT_PATH"
test -s "$ARTIFACT_MANIFEST"

grep -q '"schema": "hache-artifact-manifest/v1"' "$ARTIFACT_MANIFEST"
grep -q "\"source_commit\": \"$TARGET\"" "$ARTIFACT_MANIFEST"
grep -q '"decision": "ARTIFACT_IDENTITY_ONLY_NOT_PRODUCTION_READY_DECLARATION"' "$ARTIFACT_MANIFEST"
! grep -q 'cp app.txt' "$ARTIFACT_MANIFEST"
! grep -q 'grep -q' "$ARTIFACT_MANIFEST"

export EXPECTED_COMMIT="$TARGET"
php "$ROOT/deployment/artifact-manifest.php" verify > "$TMP/verify.log"
grep -q '^ARTIFACT_VERIFY_OK ' "$TMP/verify.log"

# A manifest must never overwrite the artifact it describes.
ARTIFACT_SHA_BEFORE_COLLISION="$(sha256sum "$ARTIFACT_PATH" | awk '{print $1}')"
if ARTIFACT_MANIFEST="$ARTIFACT_PATH" \
   SOURCE_COMMIT="$TARGET" \
   php "$ROOT/deployment/artifact-manifest.php" create >"$TMP/collision.out" 2>"$TMP/collision.err"; then
  echo 'ERROR: manifest helper accepted artifact/manifest path collision' >&2
  exit 1
fi
grep -q 'artifact_manifest_path_collision' "$TMP/collision.err"
test "$ARTIFACT_SHA_BEFORE_COLLISION" = "$(sha256sum "$ARTIFACT_PATH" | awk '{print $1}')"

# Manifests are create-once; a second create cannot replace release evidence.
if SOURCE_COMMIT="$TARGET" php "$ROOT/deployment/artifact-manifest.php" create >"$TMP/recreate.out" 2>"$TMP/recreate.err"; then
  echo 'ERROR: manifest helper overwrote an existing manifest' >&2
  exit 1
fi
grep -q 'manifest_target_exists' "$TMP/recreate.err"

# Build outputs are also create-once. A stale target must stop before build/test run.
export FIXTURE_SENTINEL="$TMP/stale-build-ran"
if ARTIFACT_BUILD_COMMAND='touch "$FIXTURE_SENTINEL"' \
   bash "$ROOT/deployment/build-artifact.sh" >"$TMP/stale.out" 2>"$TMP/stale.err"; then
  echo 'ERROR: build helper reused stale release paths' >&2
  exit 1
fi
grep -q 'artifact_target_exists' "$TMP/stale.err"
test ! -e "$FIXTURE_SENTINEL"

# A different release commit must not be accepted even when the bytes are intact.
BAD_COMMIT="0000000000000000000000000000000000000000"
if EXPECTED_COMMIT="$BAD_COMMIT" php "$ROOT/deployment/artifact-manifest.php" verify >"$TMP/bad-commit.out" 2>"$TMP/bad-commit.err"; then
  echo 'ERROR: verifier accepted mismatched source commit' >&2
  exit 1
fi
grep -q 'source_commit_mismatch' "$TMP/bad-commit.err"

# Byte tampering after manifest creation must be detected.
cp "$ARTIFACT_PATH" "$TMP/pristine.tar.gz"
printf 'tamper' >> "$ARTIFACT_PATH"
if EXPECTED_COMMIT="$TARGET" php "$ROOT/deployment/artifact-manifest.php" verify >"$TMP/tamper.out" 2>"$TMP/tamper.err"; then
  echo 'ERROR: verifier accepted tampered artifact' >&2
  exit 1
fi
grep -Eq 'artifact_(size|sha256)_mismatch' "$TMP/tamper.err"
cp "$TMP/pristine.tar.gz" "$ARTIFACT_PATH"

# A failed test phase must not create a releasable artifact or manifest.
rm -rf "$STAGE"
FAIL_ARTIFACT="$OUT/failed.tar.gz"
FAIL_MANIFEST="$OUT/failed.manifest.json"
if ARTIFACT_PATH="$FAIL_ARTIFACT" \
   ARTIFACT_MANIFEST="$FAIL_MANIFEST" \
   ARTIFACT_TEST_COMMAND='exit 7' \
   bash "$ROOT/deployment/build-artifact.sh" >"$TMP/fail-build.out" 2>"$TMP/fail-build.err"; then
  echo 'ERROR: build helper succeeded after failing tests' >&2
  exit 1
fi
test ! -e "$FAIL_ARTIFACT"
test ! -e "$FAIL_MANIFEST"

# Promotion gets a private verified snapshot and must consume it synchronously.
rm -rf "$STAGE"
ARTIFACT_PATH="$OUT/release.tar.gz"
ARTIFACT_MANIFEST="$OUT/release.manifest.json"
export ARTIFACT_PATH ARTIFACT_MANIFEST
export EXPECTED_COMMIT="$TARGET"
export FIXTURE_DEPLOYED="$DEPLOYED"
export PROMOTE_COMMAND='test "$VERIFIED_SOURCE_COMMIT" = "$EXPECTED_COMMIT"; cp "$VERIFIED_ARTIFACT_PATH" "$FIXTURE_DEPLOYED"'
bash "$ROOT/deployment/promote-artifact.sh" > "$TMP/promote.log"
grep -q '^ARTIFACT_PROMOTION_OK ' "$TMP/promote.log"
test -s "$DEPLOYED"
test "$(sha256sum "$DEPLOYED" | awk '{print $1}')" = "$(sha256sum "$ARTIFACT_PATH" | awk '{print $1}')"

# Promotion must fail before the installer runs when bytes no longer match the manifest.
printf 'tamper-again' >> "$ARTIFACT_PATH"
rm -f "$DEPLOYED"
if PROMOTE_COMMAND='touch "$FIXTURE_DEPLOYED"' bash "$ROOT/deployment/promote-artifact.sh" >"$TMP/promote-tamper.out" 2>"$TMP/promote-tamper.err"; then
  echo 'ERROR: promotion accepted tampered bytes' >&2
  exit 1
fi
test ! -e "$DEPLOYED"
cp "$TMP/pristine.tar.gz" "$ARTIFACT_PATH"

# Installer failures propagate and never emit a success marker.
if PROMOTE_COMMAND='exit 9' bash "$ROOT/deployment/promote-artifact.sh" >"$TMP/promote-fail.out" 2>"$TMP/promote-fail.err"; then
  echo 'ERROR: promotion swallowed installer failure' >&2
  exit 1
fi
grep -q 'exit_code=9' "$TMP/promote-fail.err"
! grep -q '^ARTIFACT_PROMOTION_OK ' "$TMP/promote-fail.out"

echo 'ARTIFACT_PROMOTION_TEST_OK'
