#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

new_repo() {
  local name="$1"
  local dir="$TMP/$name"
  mkdir -p "$dir/security/supply-chain"
  cp "$ROOT/security/supply-chain/policy.json" "$dir/security/supply-chain/policy.json"
  cp "$ROOT/security/supply-chain/license-policy.json" "$dir/security/supply-chain/license-policy.json"
  cp "$ROOT/security/supply-chain/accepted-risk.json" "$dir/security/supply-chain/accepted-risk.json"
  cp "$ROOT/security/supply-chain/secret-scan.allowlist" "$dir/security/supply-chain/secret-scan.allowlist"
  git -C "$dir" init -q
  git -C "$dir" config user.email fixture@example.test
  git -C "$dir" config user.name fixture
  printf '%s\n' fixture > "$dir/README.md"
  git -C "$dir" add .
  git -C "$dir" commit -qm init
  printf '%s\n' "$dir"
}

commit_all() {
  git -C "$1" add .
  git -C "$1" commit -qm fixture
}

write_bound_npm_audit() {
  local dir="$1"
  local out="$2"
  local lock_hash
  lock_hash="$(git -C "$dir" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
  printf '%s\n' "{\"auditReportVersion\":2,\"vulnerabilities\":{},\"hache_lock_sha256\":\"$lock_hash\"}" > "$out"
}

raw_check() {
  local dir="$1"
  shift
  env \
    SUPPLY_CHAIN_ROOT="$dir" \
    SUPPLY_CHAIN_REPORT_FILE="$dir/report.json" \
    SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 \
    "$@" \
    php "$ROOT/security/supply-chain/check.php"
}

mismatch="$(new_repo npm-version-mismatch)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^2.0.0"}}' > "$mismatch/package.json"
cat > "$mismatch/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^2.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$mismatch"
write_bound_npm_audit "$mismatch" "$mismatch/npm-audit.json"
set +e
raw_check "$mismatch" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$mismatch/npm-audit.json" > "$mismatch/out.txt" 2>&1
mismatch_rc=$?
set -e
[[ "$mismatch_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$mismatch/out.txt"
grep -q 'rule=sca_unavailable' "$mismatch/out.txt"
grep -q 'rule=license_not_evaluated' "$mismatch/out.txt"
grep -q 'evidence_complete=0' "$mismatch/out.txt"

matching="$(new_repo npm-version-match)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^2.0.0"}}' > "$matching/package.json"
cat > "$matching/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^2.0.0"}},"node_modules/pkg":{"name":"pkg","version":"2.1.0","license":"MIT"}}}
JSON
commit_all "$matching"
write_bound_npm_audit "$matching" "$matching/npm-audit.json"
raw_check "$matching" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$matching/npm-audit.json" > "$matching/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$matching/out.txt"
grep -q 'evidence_complete=1' "$matching/out.txt"

workspace="$(new_repo npm-workspace-link)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"workspace-pkg":"workspace:*"}}' > "$workspace/package.json"
cat > "$workspace/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"workspace-pkg":"workspace:*"}},"node_modules/workspace-pkg":{"resolved":"packages/workspace-pkg","link":true},"packages/workspace-pkg":{"name":"workspace-pkg","version":"2.3.4","license":"MIT"}}}
JSON
commit_all "$workspace"
write_bound_npm_audit "$workspace" "$workspace/npm-audit.json"
raw_check "$workspace" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$workspace/npm-audit.json" > "$workspace/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace/out.txt"
grep -q 'evidence_complete=1' "$workspace/out.txt"

unsupported="$(new_repo npm-unsupported-constraint)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"file:../pkg"}}' > "$unsupported/package.json"
cat > "$unsupported/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"file:../pkg"}},"node_modules/pkg":{"name":"pkg","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$unsupported"
set +e
raw_check "$unsupported" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$unsupported/out.txt" 2>&1
unsupported_rc=$?
set -e
[[ "$unsupported_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$unsupported/out.txt"
grep -q 'evidence_complete=0' "$unsupported/out.txt"

default_allow="$(new_repo default-allow-head)"
mkdir -p "$default_allow/tests"
secret_value="ghp_$(printf 'A%.0s' $(seq 1 40))"
printf '%s\n' "$secret_value" > "$default_allow/tests/fixture-secret.txt"
commit_all "$default_allow"
printf '%s\n' 'tests/fixture-secret.txt github_token' >> "$default_allow/security/supply-chain/secret-scan.allowlist"
set +e
raw_check "$default_allow" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$default_allow/out.txt" 2>&1
default_allow_rc=$?
set -e
[[ "$default_allow_rc" -eq 1 ]]
grep -q 'category=secret' "$default_allow/out.txt"
grep -q 'evidence_complete=1' "$default_allow/out.txt"
! grep -q "$secret_value" "$default_allow/out.txt"
! grep -q "$secret_value" "$default_allow/report.json"

cp "$default_allow/security/supply-chain/secret-scan.allowlist" "$TMP/explicit-allowlist"
raw_check "$default_allow" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE="$TMP/explicit-allowlist" > "$default_allow/override.txt"
grep -q 'enforced_blockers=0' "$default_allow/override.txt"

echo "SUPPLY_CHAIN_REVIEW_ROUND2_REGRESSION_OK"
