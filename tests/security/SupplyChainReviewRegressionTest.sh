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

make_node_lock() {
  local dir="$1"
  printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$dir/package.json"
  cat > "$dir/package-lock.json" <<'JSON'
{
  "name":"fixture",
  "lockfileVersion":3,
  "packages":{
    "":{"name":"fixture","version":"1.0.0","license":"MIT"},
    "node_modules/vuln-pkg":{"name":"vuln-pkg","version":"1.0.0","license":"MIT"}
  }
}
JSON
}

invalid_npm="$(new_repo invalid-npm)"
make_node_lock "$invalid_npm"
printf '%s\n' '{}' > "$invalid_npm/npm-audit.json"
commit_all "$invalid_npm"
run_check "$invalid_npm" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$invalid_npm/npm-audit.json" > "$invalid_npm/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_npm/out.txt"
grep -q 'not_evaluated=1' "$invalid_npm/out.txt"
grep -q 'evidence_complete=0' "$invalid_npm/out.txt"

invalid_npm_inner="$(new_repo invalid-npm-inner)"
make_node_lock "$invalid_npm_inner"
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{"vuln-pkg":"invalid"}}' > "$invalid_npm_inner/npm-audit.json"
commit_all "$invalid_npm_inner"
run_check "$invalid_npm_inner" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$invalid_npm_inner/npm-audit.json" > "$invalid_npm_inner/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_npm_inner/out.txt"
grep -q 'not_evaluated=1' "$invalid_npm_inner/out.txt"
grep -q 'evidence_complete=0' "$invalid_npm_inner/out.txt"

invalid_npm_advisory="$(new_repo invalid-npm-advisory)"
make_node_lock "$invalid_npm_advisory"
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{"vuln-pkg":{"severity":"high","via":[{}]}}}' > "$invalid_npm_advisory/npm-audit.json"
commit_all "$invalid_npm_advisory"
run_check "$invalid_npm_advisory" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$invalid_npm_advisory/npm-audit.json" > "$invalid_npm_advisory/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_npm_advisory/out.txt"
grep -q 'not_evaluated=1' "$invalid_npm_advisory/out.txt"
grep -q 'evidence_complete=0' "$invalid_npm_advisory/out.txt"

invalid_lock="$(new_repo invalid-node-lock)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$invalid_lock/package.json"
printf '%s\n' '{}' > "$invalid_lock/package-lock.json"
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{}}' > "$invalid_lock/npm-audit.json"
commit_all "$invalid_lock"
set +e
run_check "$invalid_lock" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_NPM_AUDIT_FILE="$invalid_lock/npm-audit.json" > "$invalid_lock/out.txt" 2>&1
invalid_lock_rc=$?
set -e
[[ "$invalid_lock_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$invalid_lock/out.txt"
grep -q 'rule=license_not_evaluated' "$invalid_lock/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_lock/out.txt"
grep -q 'evidence_complete=0' "$invalid_lock/out.txt"

mismatched_lock="$(new_repo mismatched-node-lock)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"left-pad":"1.3.0"}}' > "$mismatched_lock/package.json"
cat > "$mismatched_lock/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"}}}
JSON
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{}}' > "$mismatched_lock/npm-audit.json"
commit_all "$mismatched_lock"
set +e
run_check "$mismatched_lock" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_NPM_AUDIT_FILE="$mismatched_lock/npm-audit.json" > "$mismatched_lock/out.txt" 2>&1
mismatched_lock_rc=$?
set -e
[[ "$mismatched_lock_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$mismatched_lock/out.txt"
grep -q 'rule=license_not_evaluated' "$mismatched_lock/out.txt"
grep -q 'rule=sca_unavailable' "$mismatched_lock/out.txt"
grep -q 'evidence_complete=0' "$mismatched_lock/out.txt"

invalid_composer="$(new_repo invalid-composer)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$invalid_composer/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"1.0.0","license":["MIT"]}],"packages-dev":[]}' > "$invalid_composer/composer.lock"
printf '%s\n' '{}' > "$invalid_composer/composer-audit.json"
commit_all "$invalid_composer"
run_check "$invalid_composer" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$invalid_composer/composer-audit.json" > "$invalid_composer/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_composer/out.txt"
grep -q 'not_evaluated=1' "$invalid_composer/out.txt"
grep -q 'evidence_complete=0' "$invalid_composer/out.txt"

invalid_composer_inner="$(new_repo invalid-composer-inner)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$invalid_composer_inner/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"1.0.0","license":["MIT"]}],"packages-dev":[]}' > "$invalid_composer_inner/composer.lock"
printf '%s\n' '{"advisories":{"vendor/pkg":["invalid"]}}' > "$invalid_composer_inner/composer-audit.json"
commit_all "$invalid_composer_inner"
run_check "$invalid_composer_inner" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$invalid_composer_inner/composer-audit.json" > "$invalid_composer_inner/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_composer_inner/out.txt"
grep -q 'not_evaluated=1' "$invalid_composer_inner/out.txt"
grep -q 'evidence_complete=0' "$invalid_composer_inner/out.txt"

invalid_composer_advisory="$(new_repo invalid-composer-advisory)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$invalid_composer_advisory/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"1.0.0","license":["MIT"]}],"packages-dev":[]}' > "$invalid_composer_advisory/composer.lock"
printf '%s\n' '{"advisories":{"vendor/pkg":[{}]}}' > "$invalid_composer_advisory/composer-audit.json"
commit_all "$invalid_composer_advisory"
run_check "$invalid_composer_advisory" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$invalid_composer_advisory/composer-audit.json" > "$invalid_composer_advisory/out.txt"
grep -q 'rule=sca_unavailable' "$invalid_composer_advisory/out.txt"
grep -q 'not_evaluated=1' "$invalid_composer_advisory/out.txt"
grep -q 'evidence_complete=0' "$invalid_composer_advisory/out.txt"

composer_identity="$(new_repo composer-identity)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0.0"}}' > "$composer_identity/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"1.0.0","license":["MIT"]}],"packages-dev":[]}' > "$composer_identity/composer.lock"
cat > "$composer_identity/composer-audit.json" <<'JSON'
{
  "advisories": {
    "vendor/pkg": [
      {"advisoryId":"","cve":"CVE-2099-0001","packageName":"vendor/pkg","title":"first CVE","severity":"high"},
      {"advisoryId":"","cve":"CVE-2099-0002","packageName":"vendor/pkg","title":"second CVE","severity":"critical"}
    ]
  }
}
JSON
commit_all "$composer_identity"
set +e
run_check "$composer_identity" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$composer_identity/composer-audit.json" > "$composer_identity/out.txt" 2>&1
composer_identity_rc=$?
set -e
[[ "$composer_identity_rc" -eq 1 ]]
[[ "$(grep -c 'category=sca .*rule=vulnerability' "$composer_identity/out.txt")" -eq 2 ]]
[[ "$(php -r '$r=json_decode(file_get_contents($argv[1]),true); $ids=[]; foreach($r["findings"] as $f){if($f["rule"]==="vulnerability"){$ids[$f["id"]]=1;}} echo count($ids);' "$composer_identity/report.json")" -eq 2 ]]
composer_first_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true); foreach($r["findings"] as $f){if($f["rule"]==="vulnerability" && str_contains($f["subject"],"CVE-2099-0001")){echo $f["id"]; exit;}}' "$composer_identity/report.json")"
[[ -n "$composer_first_id" ]]
cat > "$composer_identity/security/supply-chain/accepted-risk.json" <<JSON
{
  "schema":"hache-supply-chain-accepted-risk-v1",
  "exceptions":[{
    "finding_id":"$composer_first_id",
    "owner":"fixture-owner",
    "approval_ref":"FIXTURE-CVE-1",
    "mitigation":"accept first CVE only",
    "expires_at":"2099-12-31"
  }]
}
JSON
set +e
run_check "$composer_identity" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$composer_identity/composer-audit.json" > "$composer_identity/accepted.txt" 2>&1
composer_accepted_rc=$?
set -e
[[ "$composer_accepted_rc" -eq 1 ]]
grep -q 'accepted_risks=1' "$composer_identity/accepted.txt"
grep -q 'enforced_blockers=1' "$composer_identity/accepted.txt"

multi="$(new_repo multi-advisory)"
make_node_lock "$multi"
cat > "$multi/npm-audit.json" <<'JSON'
{
  "auditReportVersion":2,
  "vulnerabilities":{
    "vuln-pkg":{
      "name":"vuln-pkg",
      "severity":"critical",
      "isDirect":true,
      "via":[
        {"source":111,"title":"first advisory","url":"https://example.test/111","severity":"high"},
        {"source":222,"title":"second advisory","url":"https://example.test/222","severity":"critical"}
      ]
    }
  }
}
JSON
commit_all "$multi"
set +e
run_check "$multi" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$multi/npm-audit.json" > "$multi/out.txt" 2>&1
multi_rc=$?
set -e
[[ "$multi_rc" -eq 1 ]]
[[ "$(grep -c 'category=sca .*rule=vulnerability' "$multi/out.txt")" -eq 2 ]]
[[ "$(php -r '$r=json_decode(file_get_contents($argv[1]),true); $ids=[]; foreach($r["findings"] as $f){if($f["rule"]==="vulnerability"){$ids[$f["id"]]=1;}} echo count($ids);' "$multi/report.json")" -eq 2 ]]

first_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true); foreach($r["findings"] as $f){if($f["rule"]==="vulnerability" && str_contains($f["subject"],"npm:111")){echo $f["id"]; exit;}}' "$multi/report.json")"
[[ -n "$first_id" ]]
cat > "$multi/security/supply-chain/accepted-risk.json" <<JSON
{
  "schema":"hache-supply-chain-accepted-risk-v1",
  "exceptions":[{
    "finding_id":"$first_id",
    "owner":"fixture-owner",
    "approval_ref":"FIXTURE-111",
    "mitigation":"first advisory isolated",
    "expires_at":"2099-12-31"
  }]
}
JSON
set +e
run_check "$multi" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$multi/npm-audit.json" > "$multi/accepted.txt" 2>&1
accepted_rc=$?
set -e
[[ "$accepted_rc" -eq 1 ]]
grep -q 'accepted_risks=1' "$multi/accepted.txt"
grep -q 'enforced_blockers=1' "$multi/accepted.txt"

bad_date="$(new_repo bad-date)"
make_node_lock "$bad_date"
cat > "$bad_date/npm-audit.json" <<'JSON'
{"auditReportVersion":2,"vulnerabilities":{"vuln-pkg":{"name":"vuln-pkg","severity":"high","via":[{"source":333,"title":"date advisory","severity":"high"}]}}}
JSON
commit_all "$bad_date"
set +e
run_check "$bad_date" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$bad_date/npm-audit.json" > "$bad_date/initial.txt" 2>&1
initial_rc=$?
set -e
[[ "$initial_rc" -eq 1 ]]
date_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true); foreach($r["findings"] as $f){if($f["rule"]==="vulnerability"){echo $f["id"]; exit;}}' "$bad_date/report.json")"

for invalid_date in 'next year' '2099-02-31'; do
  cat > "$bad_date/security/supply-chain/accepted-risk.json" <<JSON
{
  "schema":"hache-supply-chain-accepted-risk-v1",
  "exceptions":[{
    "finding_id":"$date_id",
    "owner":"fixture-owner",
    "approval_ref":"FIXTURE-DATE",
    "mitigation":"must not become evergreen",
    "expires_at":"$invalid_date"
  }]
}
JSON
  set +e
  run_check "$bad_date" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$bad_date/npm-audit.json" > "$bad_date/date.txt" 2>&1
  date_rc=$?
  set -e
  [[ "$date_rc" -eq 1 ]]
  grep -q 'accepted_risks=0' "$bad_date/date.txt"
done

cat > "$bad_date/security/supply-chain/accepted-risk.json" <<JSON
{
  "schema":"hache-supply-chain-accepted-risk-v1",
  "exceptions":[{
    "finding_id":"$date_id",
    "owner":["not-a-string"],
    "approval_ref":"FIXTURE-TYPE",
    "mitigation":"must not accept non-scalar owner",
    "expires_at":"2099-12-31"
  }]
}
JSON
set +e
run_check "$bad_date" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$bad_date/npm-audit.json" > "$bad_date/type.txt" 2>&1
type_rc=$?
set -e
[[ "$type_rc" -eq 1 ]]
grep -q 'accepted_risks=0' "$bad_date/type.txt"

incomplete_secret="$(new_repo incomplete-secret)"
printf '%s\n' 'cannot-read-this-file' > "$incomplete_secret/a-unreadable.txt"
printf '%s\n' 'sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890' > "$incomplete_secret/z-secret.txt"
commit_all "$incomplete_secret"
chmod 000 "$incomplete_secret/a-unreadable.txt"
set +e
run_check "$incomplete_secret" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$incomplete_secret/out.txt" 2>&1
incomplete_rc=$?
set -e
chmod 600 "$incomplete_secret/a-unreadable.txt"
[[ "$incomplete_rc" -eq 1 ]]
grep -q 'category=secret' "$incomplete_secret/out.txt"
grep -q 'not_evaluated=0' "$incomplete_secret/out.txt"
grep -q 'evidence_complete=1' "$incomplete_secret/out.txt"
grep -q '"incomplete": false' "$incomplete_secret/report.json"

echo "SUPPLY_CHAIN_REVIEW_REGRESSION_OK"