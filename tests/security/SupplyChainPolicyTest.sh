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

commit_all() {
  local dir="$1"
  git -C "$dir" add .
  git -C "$dir" commit -qm fixture
}

clean="$(new_repo clean)"
run_check "$clean" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$clean/out.txt"
grep -q 'enforced_blockers=0' "$clean/out.txt"

missing_lock="$(new_repo missing-lock)"
printf '%s\n' '{"name":"fixture","private":true}' > "$missing_lock/package.json"
commit_all "$missing_lock"
set +e
run_check "$missing_lock" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$missing_lock/out.txt" 2>&1
missing_lock_rc=$?
set -e
[[ "$missing_lock_rc" -eq 1 ]]
grep -q 'rule=node_lock_missing' "$missing_lock/out.txt"

secret_repo="$(new_repo secret)"
secret_value='sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
printf '%s\n' "$secret_value" > "$secret_repo/fixture.txt"
commit_all "$secret_repo"
set +e
run_check "$secret_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$secret_repo/out.txt" 2>&1
secret_rc=$?
set -e
[[ "$secret_rc" -eq 1 ]]
grep -q 'rule=openai_key' "$secret_repo/out.txt"
! grep -q "$secret_value" "$secret_repo/out.txt"
! grep -q "$secret_value" "$secret_repo/report.json"

allow_repo="$(new_repo allow)"
printf '%s\n' 'fixture.txt openai_key' >> "$allow_repo/security/supply-chain/secret-scan.allowlist"
printf '%s\n' "$secret_value" > "$allow_repo/fixture.txt"
commit_all "$allow_repo"
run_check "$allow_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$allow_repo/out.txt"
grep -q 'enforced_blockers=0' "$allow_repo/out.txt"

make_node_fixture() {
  local dir="$1"
  printf '%s\n' '{"name":"fixture","private":true}' > "$dir/package.json"
  cat > "$dir/package-lock.json" <<'JSON'
{
  "name": "fixture",
  "lockfileVersion": 3,
  "packages": {
    "": {"name":"fixture","version":"1.0.0","license":"MIT"},
    "node_modules/vuln-pkg": {"name":"vuln-pkg","version":"1.0.0","license":"MIT"}
  }
}
JSON
  cat > "$dir/npm-audit.json" <<'JSON'
{
  "auditReportVersion": 2,
  "vulnerabilities": {
    "vuln-pkg": {
      "name": "vuln-pkg",
      "severity": "high",
      "isDirect": true,
      "via": [{"source":12345,"title":"fixture advisory","url":"https://example.test/advisory","severity":"high"}]
    }
  }
}
JSON
  commit_all "$dir"
}

sca_repo="$(new_repo sca)"
make_node_fixture "$sca_repo"
run_check "$sca_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$sca_repo/npm-audit.json" > "$sca_repo/baseline.txt"
grep -q 'potential_blockers=1' "$sca_repo/baseline.txt"
grep -q 'enforced_blockers=0' "$sca_repo/baseline.txt"
set +e
run_check "$sca_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$sca_repo/npm-audit.json" > "$sca_repo/block.txt" 2>&1
sca_block_rc=$?
set -e
[[ "$sca_block_rc" -eq 1 ]]
grep -q 'category=sca severity=high' "$sca_repo/block.txt"

finding_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true); foreach($r["findings"] as $f){if($f["category"]==="sca" && $f["rule"]==="vulnerability"){echo $f["id"]; exit;}}' "$sca_repo/report.json")"
[[ -n "$finding_id" ]]
cat > "$sca_repo/security/supply-chain/accepted-risk.json" <<JSON
{
  "schema": "hache-supply-chain-accepted-risk-v1",
  "exceptions": [{
    "finding_id": "$finding_id",
    "owner": "fixture-owner",
    "approval_ref": "FIXTURE-123",
    "mitigation": "fixture dependency is isolated from production paths",
    "expires_at": "2099-12-31"
  }]
}
JSON
run_check "$sca_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$sca_repo/npm-audit.json" > "$sca_repo/accepted.txt"
grep -q 'accepted_risks=1' "$sca_repo/accepted.txt"
grep -q 'enforced_blockers=0' "$sca_repo/accepted.txt"

level_a="$(new_repo level-a)"
make_node_fixture "$level_a"
run_check "$level_a" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_NPM_AUDIT_FILE="$level_a/npm-audit.json" > "$level_a/out.txt"
grep -q 'enforced_blockers=0' "$level_a/out.txt"

no_sca="$(new_repo no-sca)"
make_node_fixture "$no_sca"
set +e
run_check "$no_sca" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B > "$no_sca/out.txt" 2>&1
no_sca_rc=$?
set -e
[[ "$no_sca_rc" -eq 1 ]]
grep -q 'rule=sca_unavailable' "$no_sca/out.txt"

license_repo="$(new_repo license)"
printf '%s\n' '{"name":"fixture","private":true}' > "$license_repo/package.json"
cat > "$license_repo/package-lock.json" <<'JSON'
{
  "name": "fixture",
  "lockfileVersion": 3,
  "packages": {
    "": {"name":"fixture","version":"1.0.0","license":"MIT"},
    "node_modules/license-pkg": {"name":"license-pkg","version":"1.0.0","license":"GPL-3.0-only"}
  }
}
JSON
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{}}' > "$license_repo/npm-audit.json"
cat > "$license_repo/security/supply-chain/license-policy.json" <<'JSON'
{
  "schema":"hache-license-policy-v1",
  "denied":["GPL-3.0-only"],
  "block_denied":true,
  "report_missing":true,
  "block_missing":false
}
JSON
commit_all "$license_repo"
set +e
run_check "$license_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$license_repo/npm-audit.json" > "$license_repo/out.txt" 2>&1
license_rc=$?
set -e
[[ "$license_rc" -eq 1 ]]
grep -q 'rule=license_denied' "$license_repo/out.txt"

composer_repo="$(new_repo composer)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$composer_repo/composer.json"
cat > "$composer_repo/composer.lock" <<'JSON'
{
  "packages": [{"name":"vendor/pkg","version":"1.0.0","license":["MIT"]}],
  "packages-dev": []
}
JSON
cat > "$composer_repo/composer-audit.json" <<'JSON'
{
  "advisories": {
    "vendor/pkg": [{
      "advisoryId":"PKSA-fixture",
      "packageName":"vendor/pkg",
      "title":"fixture composer advisory",
      "severity":"critical",
      "link":"https://example.test/composer-advisory"
    }]
  }
}
JSON
commit_all "$composer_repo"
set +e
run_check "$composer_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$composer_repo/composer-audit.json" > "$composer_repo/out.txt" 2>&1
composer_rc=$?
set -e
[[ "$composer_rc" -eq 1 ]]
grep -q 'category=sca severity=critical' "$composer_repo/out.txt"

echo "SUPPLY_CHAIN_POLICY_TEST_OK"
