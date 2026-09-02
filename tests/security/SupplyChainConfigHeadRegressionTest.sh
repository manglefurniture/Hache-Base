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
  printf '%s\n' "$dir"
}

commit_all() {
  git -C "$1" add .
  git -C "$1" commit -qm fixture
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

# Default policy must come from HEAD, not a dirty working tree.
policy_repo="$(new_repo policy-head)"
mkdir -p "$policy_repo/runtime"
secret_value='sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
printf '%s\n' "$secret_value" > "$policy_repo/runtime/secret.txt"
commit_all "$policy_repo"
php -r '$p=$argv[1];$j=json_decode(file_get_contents($p),true);$j["baseline_blocks"]=[];file_put_contents($p,json_encode($j,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES).PHP_EOL);' "$policy_repo/security/supply-chain/policy.json"
set +e
raw_check "$policy_repo" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$policy_repo/out.txt" 2>&1
policy_rc=$?
set -e
[[ "$policy_rc" -eq 1 ]]
grep -q 'category=secret' "$policy_repo/out.txt"
! grep -q "$secret_value" "$policy_repo/out.txt"

# Default license policy must come from HEAD.
license_repo="$(new_repo license-head)"
php -r '$p=$argv[1];$j=json_decode(file_get_contents($p),true);$j["denied"]=["MIT"];$j["block_denied"]=true;file_put_contents($p,json_encode($j,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES).PHP_EOL);' "$license_repo/security/supply-chain/license-policy.json"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^1.0.0"}}' > "$license_repo/package.json"
cat > "$license_repo/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^1.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.2.0","license":"MIT"}}}
JSON
commit_all "$license_repo"
php -r '$p=$argv[1];$j=json_decode(file_get_contents($p),true);$j["denied"]=[];file_put_contents($p,json_encode($j,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES).PHP_EOL);' "$license_repo/security/supply-chain/license-policy.json"
set +e
raw_check "$license_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=A > "$license_repo/out.txt" 2>&1
license_rc=$?
set -e
[[ "$license_rc" -eq 1 ]]
grep -q 'category=license severity=high rule=license_denied' "$license_repo/out.txt"

# Default accepted-risk must come from HEAD; explicit override remains supported.
risk_repo="$(new_repo risk-head)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^1.0.0"}}' > "$risk_repo/package.json"
cat > "$risk_repo/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^1.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.2.0","license":"MIT"}}}
JSON
commit_all "$risk_repo"
lock_hash="$(git -C "$risk_repo" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
cat > "$TMP/npm-audit.json" <<JSON
{"auditReportVersion":2,"vulnerabilities":{"pkg":{"name":"pkg","severity":"high","isDirect":true,"via":[{"source":12345,"title":"fixture advisory","url":"https://example.test/advisory","severity":"high"}]}},"hache_lock_sha256":"$lock_hash"}
JSON
set +e
raw_check "$risk_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$TMP/npm-audit.json" > "$risk_repo/first.txt" 2>&1
first_rc=$?
set -e
[[ "$first_rc" -eq 1 ]]
finding_id="$(php -r '$r=json_decode(file_get_contents($argv[1]),true);foreach($r["findings"] as $f){if(($f["category"]??"")==="sca"&&($f["rule"]??"")==="vulnerability"){echo $f["id"];exit;}}' "$risk_repo/report.json")"
[[ -n "$finding_id" ]]
cat > "$risk_repo/security/supply-chain/accepted-risk.json" <<JSON
{"schema":"hache-supply-chain-accepted-risk-v1","exceptions":[{"finding_id":"$finding_id","owner":"fixture-owner","approval_ref":"FIXTURE-1","mitigation":"fixture mitigation","expires_at":"2099-12-31"}]}
JSON
set +e
raw_check "$risk_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$TMP/npm-audit.json" > "$risk_repo/default.txt" 2>&1
default_rc=$?
set -e
[[ "$default_rc" -eq 1 ]]
grep -q 'accepted_risks=0' "$risk_repo/default.txt"
raw_check "$risk_repo" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=B SUPPLY_CHAIN_NPM_AUDIT_FILE="$TMP/npm-audit.json" SUPPLY_CHAIN_ACCEPTED_RISK_FILE="$risk_repo/security/supply-chain/accepted-risk.json" > "$risk_repo/override.txt"
grep -q 'accepted_risks=1' "$risk_repo/override.txt"
grep -q 'enforced_blockers=0' "$risk_repo/override.txt"

echo "SUPPLY_CHAIN_CONFIG_HEAD_REGRESSION_OK"
