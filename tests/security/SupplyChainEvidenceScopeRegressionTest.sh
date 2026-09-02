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

write_node_stack() {
  local dir="$1"
  mkdir -p "$dir"
  printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$dir/package.json"
  cat > "$dir/package-lock.json" <<'JSON'
{
  "name":"fixture",
  "lockfileVersion":3,
  "packages":{
    "":{"name":"fixture","version":"1.0.0","license":"MIT"}
  }
}
JSON
}

composer_bad="$(new_repo composer-bad-lock)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$composer_bad/composer.json"
printf '%s\n' '{"packages":[],"packages-dev":[]}' > "$composer_bad/composer.lock"
printf '%s\n' '{"advisories":[]}' > "$composer_bad/composer-audit.json"
commit_all "$composer_bad"
set +e
run_check "$composer_bad" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$composer_bad/composer-audit.json" > "$composer_bad/out.txt" 2>&1
composer_bad_rc=$?
set -e
[[ "$composer_bad_rc" -eq 1 ]]
grep -q 'rule=composer_lock_invalid_format' "$composer_bad/out.txt"
grep -q 'rule=license_not_evaluated' "$composer_bad/out.txt"
grep -q 'rule=sca_unavailable' "$composer_bad/out.txt"
grep -q 'evidence_complete=0' "$composer_bad/out.txt"

multi="$(new_repo multi-node-evidence)"
write_node_stack "$multi"
write_node_stack "$multi/frontend"
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{}}' > "$multi/npm-audit.json"
commit_all "$multi"
run_check "$multi" \
  SUPPLY_CHAIN_MODE=block \
  SUPPLY_CHAIN_LEVEL=B \
  SUPPLY_CHAIN_STACK_ROOTS='.,frontend' \
  SUPPLY_CHAIN_NPM_AUDIT_FILE="$multi/npm-audit.json" > "$multi/out.txt"
[[ "$(grep -c 'rule=sca_unavailable' "$multi/out.txt")" -eq 2 ]]
grep -q 'not_evaluated=2' "$multi/out.txt"
grep -q 'evidence_complete=0' "$multi/out.txt"
[[ "$(php -r '$r=json_decode(file_get_contents($argv[1]),true); $n=0; foreach($r["checks"]["sca"] as $c){if(($c["status"]??"")==="not_evaluated"){$n++;}} echo $n;' "$multi/report.json")" -eq 2 ]]

missing_node="$(new_repo missing-node-lock-report)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$missing_node/package.json"
commit_all "$missing_node"
run_check "$missing_node" SUPPLY_CHAIN_MODE=report SUPPLY_CHAIN_LEVEL=A > "$missing_node/out.txt"
grep -q 'rule=node_lock_missing' "$missing_node/out.txt"
grep -q 'rule=license_not_evaluated' "$missing_node/out.txt"
grep -q 'rule=sca_unavailable' "$missing_node/out.txt"
grep -q 'not_evaluated=2' "$missing_node/out.txt"
grep -q 'evidence_complete=0' "$missing_node/out.txt"

missing_composer="$(new_repo missing-composer-lock-report)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$missing_composer/composer.json"
commit_all "$missing_composer"
run_check "$missing_composer" SUPPLY_CHAIN_MODE=report SUPPLY_CHAIN_LEVEL=A > "$missing_composer/out.txt"
grep -q 'rule=composer_lock_missing' "$missing_composer/out.txt"
grep -q 'rule=license_not_evaluated' "$missing_composer/out.txt"
grep -q 'rule=sca_unavailable' "$missing_composer/out.txt"
grep -q 'not_evaluated=2' "$missing_composer/out.txt"
grep -q 'evidence_complete=0' "$missing_composer/out.txt"

echo "SUPPLY_CHAIN_EVIDENCE_SCOPE_REGRESSION_OK"
