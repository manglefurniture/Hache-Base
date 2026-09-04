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

raw_check() {
  local dir="$1"
  shift
  env SUPPLY_CHAIN_ROOT="$dir" SUPPLY_CHAIN_REPORT_FILE="$dir/report.json" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 "$@" php "$ROOT/security/supply-chain/check.php"
}

workspace_bad="$(new_repo npm-workspaces-truncated)"
mkdir -p "$workspace_bad/packages/a" "$workspace_bad/packages/b"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","workspaces":["packages/*"]}' > "$workspace_bad/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0"}' > "$workspace_bad/packages/a/package.json"
printf '%s\n' '{"name":"b","version":"1.0.0"}' > "$workspace_bad/packages/b/package.json"
cat > "$workspace_bad/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{"name":"a","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$workspace_bad"
set +e
raw_check "$workspace_bad" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_bad/out.txt" 2>&1
workspace_bad_rc=$?
set -e
[[ "$workspace_bad_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$workspace_bad/out.txt"

workspace_good="$(new_repo npm-workspaces-complete)"
mkdir -p "$workspace_good/packages/a" "$workspace_good/packages/b"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","workspaces":["packages/*"]}' > "$workspace_good/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0"}' > "$workspace_good/packages/a/package.json"
printf '%s\n' '{"name":"b","version":"1.0.0"}' > "$workspace_good/packages/b/package.json"
cat > "$workspace_good/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"node_modules/b":{"resolved":"packages/b","link":true},"packages/a":{"name":"a","version":"1.0.0","license":"MIT"},"packages/b":{"name":"b","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$workspace_good"
raw_check "$workspace_good" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_good/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace_good/out.txt"

composer_bad="$(new_repo composer-prod-from-dev)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/a":"^1.0"}}' > "$composer_bad/composer.json"
cat > "$composer_bad/composer.lock" <<'JSON'
{"packages":[{"name":"vendor/a","version":"1.0.0","require":{"vendor/b":"^1.0"}}],"packages-dev":[{"name":"vendor/b","version":"1.0.0"}]}
JSON
commit_all "$composer_bad"
set +e
raw_check "$composer_bad" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_bad/out.txt" 2>&1
composer_bad_rc=$?
set -e
[[ "$composer_bad_rc" -eq 1 ]]
grep -q 'rule=composer_lock_invalid_format' "$composer_bad/out.txt"

composer_good="$(new_repo composer-prod-complete)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/a":"^1.0"}}' > "$composer_good/composer.json"
cat > "$composer_good/composer.lock" <<'JSON'
{"packages":[{"name":"vendor/a","version":"1.0.0","require":{"vendor/b":"^1.0"}},{"name":"vendor/b","version":"1.0.0"}],"packages-dev":[]}
JSON
commit_all "$composer_good"
raw_check "$composer_good" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_good/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$composer_good/out.txt"

peer_bad="$(new_repo npm-required-peer-missing)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"a":"^1.0.0"}}' > "$peer_bad/package.json"
cat > "$peer_bad/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"a":"^1.0.0"}},"node_modules/a":{"name":"a","version":"1.0.0","peerDependencies":{"peer":"1.0.0"}}}}
JSON
commit_all "$peer_bad"
set +e
raw_check "$peer_bad" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$peer_bad/out.txt" 2>&1
peer_bad_rc=$?
set -e
[[ "$peer_bad_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$peer_bad/out.txt"

peer_optional="$(new_repo npm-optional-peer-missing)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"a":"^1.0.0"}}' > "$peer_optional/package.json"
cat > "$peer_optional/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"a":"^1.0.0"}},"node_modules/a":{"name":"a","version":"1.0.0","peerDependencies":{"peer":"1.0.0"},"peerDependenciesMeta":{"peer":{"optional":true}}}}}
JSON
commit_all "$peer_optional"
raw_check "$peer_optional" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$peer_optional/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$peer_optional/out.txt"

stack_typo="$(new_repo explicit-stack-root-typo)"
mkdir -p "$stack_typo/frontend"
printf '%s\n' '{"name":"frontend","private":true,"packageManager":"npm@11.0.0"}' > "$stack_typo/frontend/package.json"
printf '%s\n' '{"name":"frontend","lockfileVersion":3,"packages":{"":{"name":"frontend","version":"1.0.0"}}}' > "$stack_typo/frontend/package-lock.json"
commit_all "$stack_typo"
set +e
raw_check "$stack_typo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_STACK_ROOTS=frontned > "$stack_typo/out.txt" 2>&1
stack_typo_rc=$?
set -e
[[ "$stack_typo_rc" -eq 2 ]]
grep -q 'SUPPLY_CHAIN_CONFIG_ERROR stack_root_without_manifest root=frontned' "$stack_typo/out.txt"

encrypted="$(new_repo encrypted-private-key)"
mkdir -p "$encrypted/secrets"
printf '%s%s\n%s\n%s%s\n' '-----BEGIN ENCRYPTED ' 'PRIVATE KEY-----' 'NOT_REAL_KEY_MATERIAL' '-----END ENCRYPTED ' 'PRIVATE KEY-----' > "$encrypted/secrets/key.pem"
commit_all "$encrypted"
set +e
raw_check "$encrypted" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$encrypted/out.txt" 2>&1
encrypted_rc=$?
set -e
[[ "$encrypted_rc" -eq 1 ]]
grep -q 'category=secret' "$encrypted/out.txt"
grep -q 'rule=private_key' "$encrypted/out.txt"
! grep -q 'NOT_REAL_KEY_MATERIAL' "$encrypted/out.txt"
! grep -q 'NOT_REAL_KEY_MATERIAL' "$encrypted/report.json"


workspace_drift="$(new_repo npm-workspace-manifest-drift)"
mkdir -p "$workspace_drift/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","workspaces":["packages/*"]}' > "$workspace_drift/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0","dependencies":{"b":"^1.0.0"}}' > "$workspace_drift/packages/a/package.json"
cat > "$workspace_drift/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{"name":"a","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$workspace_drift"
set +e
raw_check "$workspace_drift" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_drift/out.txt" 2>&1
workspace_drift_rc=$?
set -e
[[ "$workspace_drift_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$workspace_drift/out.txt"

root_peer_meta="$(new_repo npm-root-peer-meta-drift)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","peerDependencies":{"peer":"1.0.0"}}' > "$root_peer_meta/package.json"
cat > "$root_peer_meta/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","peerDependencies":{"peer":"1.0.0"},"peerDependenciesMeta":{"peer":{"optional":true}}}}}
JSON
commit_all "$root_peer_meta"
set +e
raw_check "$root_peer_meta" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$root_peer_meta/out.txt" 2>&1
root_peer_meta_rc=$?
set -e
[[ "$root_peer_meta_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$root_peer_meta/out.txt"

composer_duplicate="$(new_repo composer-duplicate-package)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/a":"^1.0"}}' > "$composer_duplicate/composer.json"
cat > "$composer_duplicate/composer.lock" <<'JSON'
{"packages":[{"name":"vendor/a","version":"1.0.0"}],"packages-dev":[{"name":"vendor/a","version":"1.1.0"}]}
JSON
commit_all "$composer_duplicate"
set +e
raw_check "$composer_duplicate" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_duplicate/out.txt" 2>&1
composer_duplicate_rc=$?
set -e
[[ "$composer_duplicate_rc" -eq 1 ]]
grep -q 'rule=composer_lock_invalid_format' "$composer_duplicate/out.txt"


workspace_npm11="$(new_repo npm11-workspace-lock-shape)"
mkdir -p "$workspace_npm11/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.4.2","workspaces":["packages/*"]}' > "$workspace_npm11/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0"}' > "$workspace_npm11/packages/a/package.json"
cat > "$workspace_npm11/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{"version":"1.0.0"}}}
JSON
commit_all "$workspace_npm11"
raw_check "$workspace_npm11" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_npm11/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace_npm11/out.txt"

workspace_private="$(new_repo npm11-private-workspace-lock-shape)"
mkdir -p "$workspace_private/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.4.2","workspaces":["packages/*"]}' > "$workspace_private/package.json"
printf '%s\n' '{"name":"a","private":true}' > "$workspace_private/packages/a/package.json"
cat > "$workspace_private/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{}}}
JSON
commit_all "$workspace_private"
raw_check "$workspace_private" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_private/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace_private/out.txt"

composer_root_replace="$(new_repo composer-root-replace-self-version)"
printf '%s\n' '{"name":"fixture/app","version":"1.2.3","replace":{"vendor/virtual":"self.version"},"require":{"vendor/a":"^1.0"}}' > "$composer_root_replace/composer.json"
cat > "$composer_root_replace/composer.lock" <<'JSON'
{"packages":[{"name":"vendor/a","version":"1.0.0","require":{"vendor/virtual":"^1.0"}}],"packages-dev":[]}
JSON
commit_all "$composer_root_replace"
raw_check "$composer_root_replace" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_root_replace/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$composer_root_replace/out.txt"

echo "SUPPLY_CHAIN_REVIEW_ROUND3_REGRESSION_OK"
