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
commit_all() { git -C "$1" add . && git -C "$1" commit -qm fixture; }
raw_check() {
  local dir="$1"; shift
  env SUPPLY_CHAIN_ROOT="$dir" SUPPLY_CHAIN_REPORT_FILE="$dir/report.json" "$@" php "$ROOT/security/supply-chain/check.php"
}

head_secret="$(new_repo head-secret)"
secret_value='ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
printf '%s\n' "$secret_value" > "$head_secret/tracked.txt"
commit_all "$head_secret"
printf '%s\n' 'working-tree-clean' > "$head_secret/tracked.txt"
set +e
raw_check "$head_secret" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$head_secret/out.txt" 2>&1
head_secret_rc=$?
set -e
[[ "$head_secret_rc" -eq 1 ]]
grep -q 'category=secret' "$head_secret/out.txt"
! grep -q "$secret_value" "$head_secret/out.txt"
! grep -q "$secret_value" "$head_secret/report.json"

bound="$(new_repo bound-audit)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0"}' > "$bound/package.json"
printf '%s\n' '{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","license":"MIT"}}}' > "$bound/package-lock.json"
commit_all "$bound"
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{},"hache_lock_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' > "$bound/npm-audit.json"
raw_check "$bound" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$bound/npm-audit.json" > "$bound/unbound.txt"
grep -q 'rule=sca_unavailable' "$bound/unbound.txt"
grep -q 'evidence_complete=0' "$bound/unbound.txt"
lock_hash="$(git -C "$bound" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
printf '%s\n' "{\"auditReportVersion\":2,\"vulnerabilities\":{},\"hache_lock_sha256\":\"$lock_hash\"}" > "$bound/npm-audit.json"
raw_check "$bound" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$bound/npm-audit.json" > "$bound/bound.txt"
! grep -q 'rule=sca_unavailable' "$bound/bound.txt"
grep -q 'evidence_complete=1' "$bound/bound.txt"

npm_head="$(new_repo npm-head-audit)"
printf '%s\n' '{"name":"head-version","private":true,"packageManager":"npm@11.0.0"}' > "$npm_head/package.json"
printf '%s\n' '{"name":"head-version","lockfileVersion":3,"packages":{"":{"name":"head-version","version":"1.0.0","license":"MIT"}}}' > "$npm_head/package-lock.json"
commit_all "$npm_head"
printf '%s\n' '{"name":"dirty-version","private":true,"packageManager":"npm@11.0.0"}' > "$npm_head/package.json"
printf '%s\n' '{"name":"dirty-version","lockfileVersion":3,"packages":{"":{"name":"dirty-version","version":"1.0.0","license":"MIT"}}}' > "$npm_head/package-lock.json"
mkdir -p "$npm_head/bin"
cat > "$npm_head/bin/npm" <<'SH'
#!/usr/bin/env bash
set -e
grep -q 'head-version' package-lock.json
! grep -q 'dirty-version' package-lock.json
printf '%s\n' '{"auditReportVersion":2,"vulnerabilities":{}}'
SH
chmod +x "$npm_head/bin/npm"
PATH="$npm_head/bin:$PATH" raw_check "$npm_head" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=0 SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C > "$npm_head/out.txt"
! grep -q 'rule=sca_unavailable' "$npm_head/out.txt"
grep -q 'evidence_complete=1' "$npm_head/out.txt"

composer_head="$(new_repo composer-head-audit)"
printf '%s\n' '{"name":"fixture/app","require":{}}' > "$composer_head/composer.json"
printf '%s\n' '{"marker":"head-version","packages":[],"packages-dev":[]}' > "$composer_head/composer.lock"
commit_all "$composer_head"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/dirty":"1.0.0"}}' > "$composer_head/composer.json"
printf '%s\n' '{"marker":"dirty-version","packages":[],"packages-dev":[]}' > "$composer_head/composer.lock"
mkdir -p "$composer_head/bin"
cat > "$composer_head/bin/composer" <<'SH'
#!/usr/bin/env bash
set -e
grep -q 'head-version' composer.lock
! grep -q 'dirty-version' composer.lock
printf '%s\n' '{"advisories":[]}'
SH
chmod +x "$composer_head/bin/composer"
PATH="$composer_head/bin:$PATH" raw_check "$composer_head" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=0 SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C > "$composer_head/out.txt"
! grep -q 'rule=sca_unavailable' "$composer_head/out.txt"
grep -q 'evidence_complete=1' "$composer_head/out.txt"

virtual_repo="$(new_repo composer-virtual)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/b":"1.0.0"}}' > "$virtual_repo/composer.json"
cat > "$virtual_repo/composer.lock" <<'JSON'
{"packages":[{"name":"vendor/a","version":"1.0.0","license":["MIT"],"provide":{"virtual/foo":"1.0.0"},"replace":{"vendor/old":"self.version"}},{"name":"vendor/b","version":"1.0.0","license":["MIT"],"require":{"virtual/foo":"^1.0","vendor/old":"^1.0"}}],"packages-dev":[]}
JSON
commit_all "$virtual_repo"
raw_check "$virtual_repo" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$virtual_repo/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$virtual_repo/out.txt"

hyphen_repo="$(new_repo composer-hyphen)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/pkg":"1.0 - 2.0"}}' > "$hyphen_repo/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/pkg","version":"2.0.5","license":["MIT"]}],"packages-dev":[]}' > "$hyphen_repo/composer.lock"
commit_all "$hyphen_repo"
raw_check "$hyphen_repo" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$hyphen_repo/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$hyphen_repo/out.txt"

echo "SUPPLY_CHAIN_HEAD_EVIDENCE_REGRESSION_OK"
