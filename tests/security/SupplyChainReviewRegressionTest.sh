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
if [[ "$(id -u)" -eq 0 ]]; then
  command -v runuser >/dev/null 2>&1 || { echo 'runuser required for root unreadable regression' >&2; exit 1; }
  getent passwd nobody >/dev/null 2>&1 || { echo 'nobody user required for root unreadable regression' >&2; exit 1; }
  cp "$ROOT/security/supply-chain/check.php" "$incomplete_secret/check-runner.php"
  chmod -R a+rX "$incomplete_secret"
  chmod 777 "$incomplete_secret"
  chmod 000 "$incomplete_secret/a-unreadable.txt"
  runuser -u nobody -- env \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=safe.directory \
    GIT_CONFIG_VALUE_0='*' \
    SUPPLY_CHAIN_ROOT="$incomplete_secret" \
    SUPPLY_CHAIN_REPORT_FILE="$incomplete_secret/report.json" \
    SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 \
    SUPPLY_CHAIN_MODE=baseline \
    SUPPLY_CHAIN_LEVEL=A \
    php "$incomplete_secret/check-runner.php" > "$incomplete_secret/out.txt" 2>&1
  incomplete_rc=$?
else
  run_check "$incomplete_secret" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$incomplete_secret/out.txt" 2>&1
  incomplete_rc=$?
fi
set -e
chmod 600 "$incomplete_secret/a-unreadable.txt"
[[ "$incomplete_rc" -eq 1 ]]
grep -q 'category=secret' "$incomplete_secret/out.txt"
grep -q 'not_evaluated=1' "$incomplete_secret/out.txt"
grep -q 'evidence_complete=0' "$incomplete_secret/out.txt"
grep -q '"incomplete": true' "$incomplete_secret/report.json"

echo "SUPPLY_CHAIN_REVIEW_REGRESSION_OK"