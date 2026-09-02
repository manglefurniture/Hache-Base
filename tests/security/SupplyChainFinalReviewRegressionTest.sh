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

run_check() {
  local dir="$1"
  shift
  env \
    SUPPLY_CHAIN_ROOT="$dir" \
    SUPPLY_CHAIN_REPORT_FILE="$dir/report.json" \
    SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 \
    "$@" \
    php "$ROOT/security/supply-chain/check.php"
}

composer_mismatch="$(new_repo composer-version-mismatch)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"^2.0"}}' > "$composer_mismatch/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"1.0.0","license":["MIT"]}],"packages-dev":[]}' > "$composer_mismatch/composer.lock"
commit_all "$composer_mismatch"
set +e
run_check "$composer_mismatch" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_mismatch/out.txt" 2>&1
composer_mismatch_rc=$?
set -e
[[ "$composer_mismatch_rc" -eq 1 ]]
grep -q 'rule=composer_lock_invalid_format' "$composer_mismatch/out.txt"
grep -q 'rule=license_not_evaluated' "$composer_mismatch/out.txt"
grep -q 'rule=sca_unavailable' "$composer_mismatch/out.txt"

composer_valid="$(new_repo composer-version-valid)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"^1.0"}}' > "$composer_valid/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"1.2.3","license":["MIT"]}],"packages-dev":[]}' > "$composer_valid/composer.lock"
commit_all "$composer_valid"
run_check "$composer_valid" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_valid/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$composer_valid/out.txt"

audit_truncated="$(new_repo npm-truncated-direct)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"left-pad":"^1.3.0"}}' > "$audit_truncated/package.json"
cat > "$audit_truncated/package-lock.json" <<'JSON'
{
  "name":"fixture",
  "lockfileVersion":3,
  "packages":{
    "":{"name":"fixture","version":"1.0.0","dependencies":{"left-pad":"^1.3.0"}}
  }
}
JSON
commit_all "$audit_truncated"
set +e
run_check "$audit_truncated" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$audit_truncated/out.txt" 2>&1
truncated_rc=$?
set -e
[[ "$truncated_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$audit_truncated/out.txt"

audit_transitive="$(new_repo npm-truncated-transitive)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg-a":"1.0.0"}}' > "$audit_transitive/package.json"
cat > "$audit_transitive/package-lock.json" <<'JSON'
{
  "name":"fixture",
  "lockfileVersion":3,
  "packages":{
    "":{"name":"fixture","version":"1.0.0","dependencies":{"pkg-a":"1.0.0"}},
    "node_modules/pkg-a":{"name":"pkg-a","version":"1.0.0","dependencies":{"pkg-b":"1.0.0"}}
  }
}
JSON
commit_all "$audit_transitive"
set +e
run_check "$audit_transitive" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$audit_transitive/out.txt" 2>&1
transitive_rc=$?
set -e
[[ "$transitive_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$audit_transitive/out.txt"

fine_pat="$(new_repo fine-grained-github-pat)"
fine_pat_value='github_pat_11AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
printf '%s\n' "$fine_pat_value" > "$fine_pat/fixture.txt"
commit_all "$fine_pat"
set +e
run_check "$fine_pat" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$fine_pat/out.txt" 2>&1
fine_pat_rc=$?
set -e
[[ "$fine_pat_rc" -eq 1 ]]
grep -q 'rule=github_token' "$fine_pat/out.txt"
! grep -q "$fine_pat_value" "$fine_pat/out.txt"
! grep -q "$fine_pat_value" "$fine_pat/report.json"

untracked_node="$(new_repo untracked-node-lock)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$untracked_node/package.json"
git -C "$untracked_node" add package.json
git -C "$untracked_node" commit -qm manifest
printf '%s\n' '{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"}}}' > "$untracked_node/package-lock.json"
set +e
run_check "$untracked_node" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$untracked_node/out.txt" 2>&1
untracked_node_rc=$?
set -e
[[ "$untracked_node_rc" -eq 1 ]]
grep -q 'rule=node_lock_untracked' "$untracked_node/out.txt"
grep -q 'rule=license_not_evaluated' "$untracked_node/out.txt"
grep -q 'rule=sca_unavailable' "$untracked_node/out.txt"

untracked_composer="$(new_repo untracked-composer-lock)"
printf '%s\n' '{"name":"fixture/app","require":{}}' > "$untracked_composer/composer.json"
git -C "$untracked_composer" add composer.json
git -C "$untracked_composer" commit -qm manifest
printf '%s\n' '{"packages":[],"packages-dev":[]}' > "$untracked_composer/composer.lock"
set +e
run_check "$untracked_composer" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$untracked_composer/out.txt" 2>&1
untracked_composer_rc=$?
set -e
[[ "$untracked_composer_rc" -eq 1 ]]
grep -q 'rule=composer_lock_untracked' "$untracked_composer/out.txt"
grep -q 'rule=license_not_evaluated' "$untracked_composer/out.txt"
grep -q 'rule=sca_unavailable' "$untracked_composer/out.txt"

echo "SUPPLY_CHAIN_FINAL_REVIEW_REGRESSION_OK"
