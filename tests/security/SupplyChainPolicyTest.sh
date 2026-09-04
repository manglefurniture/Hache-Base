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
  local stack_roots='.'
  local npm_audit=''
  local composer_audit=''
  local arg
  for arg in "$@"; do
    case "$arg" in
      SUPPLY_CHAIN_STACK_ROOTS=*) stack_roots="${arg#*=}" ;;
      SUPPLY_CHAIN_NPM_AUDIT_FILE=*) npm_audit="${arg#*=}" ;;
      SUPPLY_CHAIN_COMPOSER_AUDIT_FILE=*) composer_audit="${arg#*=}" ;;
    esac
  done

  if [[ "$stack_roots" != *,* ]]; then
    local stack_prefix=''
    if [[ -n "$stack_roots" && "$stack_roots" != '.' ]]; then
      stack_prefix="${stack_roots#./}"
      stack_prefix="${stack_prefix%/}/"
    fi
    if [[ -n "$npm_audit" && -f "$npm_audit" ]]; then
      local node_lock=''
      local candidate
      for candidate in package-lock.json npm-shrinkwrap.json; do
        if git -C "$dir" cat-file -e "HEAD:${stack_prefix}${candidate}" 2>/dev/null; then
          node_lock="${stack_prefix}${candidate}"
          break
        fi
      done
      if [[ -n "$node_lock" ]]; then
        local node_hash
        node_hash="$(git -C "$dir" show "HEAD:$node_lock" | sha256sum | awk '{print $1}')"
        php -r '$p=$argv[1];$j=json_decode(file_get_contents($p),true);if(is_array($j)){$j["hache_lock_sha256"]=$argv[2];file_put_contents($p,json_encode($j,JSON_UNESCAPED_SLASHES).PHP_EOL);}' "$npm_audit" "$node_hash"
      fi
    fi
    if [[ -n "$composer_audit" && -f "$composer_audit" ]] && git -C "$dir" cat-file -e "HEAD:${stack_prefix}composer.lock" 2>/dev/null; then
      local composer_hash
      composer_hash="$(git -C "$dir" show "HEAD:${stack_prefix}composer.lock" | sha256sum | awk '{print $1}')"
      php -r '$p=$argv[1];$j=json_decode(file_get_contents($p),true);if(is_array($j)){$j["hache_lock_sha256"]=$argv[2];file_put_contents($p,json_encode($j,JSON_UNESCAPED_SLASHES).PHP_EOL);}' "$composer_audit" "$composer_hash"
    fi
  fi

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

make_node_fixture() {
  local dir="$1"
  local manager="${2:-npm@11.0.0}"
  printf '%s\n' "{\"name\":\"fixture\",\"private\":true,\"packageManager\":\"$manager\"}" > "$dir/package.json"
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

clean="$(new_repo clean)"
run_check "$clean" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$clean/out.txt"
grep -q 'enforced_blockers=0' "$clean/out.txt"

missing_lock="$(new_repo missing-lock)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$missing_lock/package.json"
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

secret_finding_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true); foreach($r["findings"] as $f){if($f["category"]==="secret"){echo $f["id"]; exit;}}' "$secret_repo/report.json")"
cat > "$secret_repo/security/supply-chain/accepted-risk.json" <<JSON
{
  "schema": "hache-supply-chain-accepted-risk-v1",
  "exceptions": [{
    "finding_id": "$secret_finding_id",
    "owner": "fixture-owner",
    "approval_ref": "FIXTURE-SECRET",
    "mitigation": "this must not suppress SEC-013",
    "expires_at": "2099-12-31"
  }]
}
JSON
set +e
run_check "$secret_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_ACCEPTED_RISK_FILE="$secret_repo/security/supply-chain/accepted-risk.json" > "$secret_repo/risk-attempt.txt" 2>&1
secret_risk_rc=$?
set -e
[[ "$secret_risk_rc" -eq 1 ]]
grep -q 'accepted_risks=0' "$secret_repo/risk-attempt.txt"
grep -q 'category=secret' "$secret_repo/risk-attempt.txt"

allow_repo="$(new_repo allow)"
printf '%s\n' 'fixture.txt openai_key' >> "$allow_repo/security/supply-chain/secret-scan.allowlist"
printf '%s\n' "$secret_value" > "$allow_repo/fixture.txt"
commit_all "$allow_repo"
set +e
run_check "$allow_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$allow_repo/invalid-allow.txt" 2>&1
allow_invalid_rc=$?
set -e
[[ "$allow_invalid_rc" -eq 2 ]]
grep -q 'secret_allowlist_path_must_be_exact_fixture' "$allow_repo/invalid-allow.txt"

allow_fixture="$(new_repo allow-fixture)"
mkdir -p "$allow_fixture/tests/fixtures"
printf '%s\n' 'tests/fixtures/fake-secret.txt openai_key' >> "$allow_fixture/security/supply-chain/secret-scan.allowlist"
printf '%s\n' "$secret_value" > "$allow_fixture/tests/fixtures/fake-secret.txt"
commit_all "$allow_fixture"
run_check "$allow_fixture" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$allow_fixture/out.txt"
grep -q 'enforced_blockers=0' "$allow_fixture/out.txt"

broad_allow="$(new_repo broad-allow)"
printf '%s\n' 'src/** openai_key' >> "$broad_allow/security/supply-chain/secret-scan.allowlist"
commit_all "$broad_allow"
set +e
run_check "$broad_allow" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$broad_allow/out.txt" 2>&1
broad_allow_rc=$?
set -e
[[ "$broad_allow_rc" -eq 2 ]]
grep -q 'secret_allowlist_path_must_be_exact_fixture' "$broad_allow/out.txt"

large_repo="$(new_repo large-text)"
python3 - <<PY
from pathlib import Path
p=Path(${large_repo@Q})/'large.txt'
with p.open('w') as f:
    f.write('x' * (2 * 1024 * 1024 + 100) + '\n')
    f.write(${secret_value@Q} + '\n')
PY
commit_all "$large_repo"
set +e
run_check "$large_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$large_repo/out.txt" 2>&1
large_rc=$?
set -e
[[ "$large_rc" -eq 1 ]]
grep -q 'category=secret' "$large_repo/out.txt"

audit_repo="$(new_repo sca)"
make_node_fixture "$audit_repo"
run_check "$audit_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$audit_repo/npm-audit.json" > "$audit_repo/baseline.txt"
grep -q 'potential_blockers=1' "$audit_repo/baseline.txt"
grep -q 'enforced_blockers=0' "$audit_repo/baseline.txt"
set +e
run_check "$audit_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$audit_repo/npm-audit.json" > "$audit_repo/block.txt" 2>&1
sca_block_rc=$?
set -e
[[ "$sca_block_rc" -eq 1 ]]
grep -q 'category=sca severity=high rule=vulnerability' "$audit_repo/block.txt"

finding_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true); foreach($r["findings"] as $f){if($f["category"]==="sca" && $f["rule"]==="vulnerability"){echo $f["id"]; exit;}}' "$audit_repo/report.json")"
cat > "$audit_repo/security/supply-chain/accepted-risk.json" <<JSON
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
run_check "$audit_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$audit_repo/npm-audit.json" SUPPLY_CHAIN_ACCEPTED_RISK_FILE="$audit_repo/security/supply-chain/accepted-risk.json" > "$audit_repo/accepted.txt"
grep -q 'accepted_risks=1' "$audit_repo/accepted.txt"
grep -q 'enforced_blockers=0' "$audit_repo/accepted.txt"

level_a="$(new_repo level-a)"
make_node_fixture "$level_a"
run_check "$level_a" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_NPM_AUDIT_FILE="$level_a/npm-audit.json" > "$level_a/out.txt"
grep -q 'enforced_blockers=0' "$level_a/out.txt"

no_sca="$(new_repo no-sca)"
make_node_fixture "$no_sca"
run_check "$no_sca" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B > "$no_sca/out.txt"
grep -q 'rule=sca_unavailable' "$no_sca/out.txt"
grep -q 'enforced_blockers=0' "$no_sca/out.txt"
grep -q 'not_evaluated=1' "$no_sca/out.txt"
grep -q 'evidence_complete=0' "$no_sca/out.txt"

manager_mismatch="$(new_repo manager-mismatch)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$manager_mismatch/package.json"
printf '%s\n' '# fake yarn lock' > "$manager_mismatch/yarn.lock"
commit_all "$manager_mismatch"
set +e
run_check "$manager_mismatch" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$manager_mismatch/out.txt" 2>&1
manager_rc=$?
set -e
[[ "$manager_rc" -eq 1 ]]
grep -q 'rule=node_lock_manager_mismatch' "$manager_mismatch/out.txt"

ambiguous="$(new_repo ambiguous)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$ambiguous/package.json"
printf '%s\n' '{}' > "$ambiguous/package-lock.json"
printf '%s\n' '# extra lock' > "$ambiguous/yarn.lock"
commit_all "$ambiguous"
set +e
run_check "$ambiguous" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$ambiguous/out.txt" 2>&1
ambiguous_rc=$?
set -e
[[ "$ambiguous_rc" -eq 1 ]]
grep -q 'rule=ambiguous_node_lockfiles' "$ambiguous/out.txt"

yarn_repo="$(new_repo yarn)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"yarn@4.0.0"}' > "$yarn_repo/package.json"
printf '%s\n' '# fake yarn lock' > "$yarn_repo/yarn.lock"
commit_all "$yarn_repo"
run_check "$yarn_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B > "$yarn_repo/out.txt"
grep -q 'rule=license_not_evaluated' "$yarn_repo/out.txt"
grep -q 'rule=sca_unavailable' "$yarn_repo/out.txt"
grep -q 'not_evaluated=2' "$yarn_repo/out.txt"
grep -q '"status": "not_evaluated"' "$yarn_repo/report.json"

license_repo="$(new_repo license)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$license_repo/package.json"
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
grep -q 'category=sca severity=critical rule=vulnerability' "$composer_repo/out.txt"

echo "SUPPLY_CHAIN_POLICY_TEST_OK"
