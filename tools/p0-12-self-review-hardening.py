from pathlib import Path

check = Path('security/supply-chain/check.php')
test = Path('tests/security/SupplyChainReviewRound2RegressionTest.sh')
policy_json = Path('security/supply-chain/policy.json')
policy_md = Path('security/supply-chain/POLICY.md')

src = check.read_text()
old = '''    if (!isset($audit['auditReportVersion'])
        || !is_int($audit['auditReportVersion'])
        || !array_key_exists('vulnerabilities', $audit)
'''
new = '''    if (!isset($audit['auditReportVersion'])
        || !is_int($audit['auditReportVersion'])
        || $audit['auditReportVersion'] !== 2
        || !array_key_exists('vulnerabilities', $audit)
'''
assert src.count(old) == 1, 'npm audit version guard mismatch'
src = src.replace(old, new)

old = '''function validComposerAudit(array $audit): bool
{
    if (!array_key_exists('advisories', $audit) || !is_array($audit['advisories'])) {
        return false;
    }
'''
new = '''function validComposerAudit(array $audit): bool
{
    if (isset($audit['error']) || !array_key_exists('advisories', $audit) || !is_array($audit['advisories'])) {
        return false;
    }
'''
assert src.count(old) == 1, 'composer audit error guard mismatch'
src = src.replace(old, new)
check.write_text(src)

txt = test.read_text()
needle = '\necho "SUPPLY_CHAIN_REVIEW_ROUND2_REGRESSION_OK"\n'
assert txt.count(needle) == 1
append = r'''

npm_unknown_schema="$(new_repo npm-audit-unknown-schema)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^1.0.0"}}' > "$npm_unknown_schema/package.json"
cat > "$npm_unknown_schema/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^1.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.5.0","license":"MIT"}}}
JSON
commit_all "$npm_unknown_schema"
npm_unknown_hash="$(git -C "$npm_unknown_schema" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
cat > "$npm_unknown_schema/npm-audit.json" <<JSON
{"auditReportVersion":3,"vulnerabilities":{"pkg":{"severity":"critical","via":[{"source":3301,"severity":"critical","title":"unknown schema critical","url":"https://example.test/3301"}]}},"hache_lock_sha256":"$npm_unknown_hash"}
JSON
raw_check "$npm_unknown_schema" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$npm_unknown_schema/npm-audit.json" > "$npm_unknown_schema/out.txt"
grep -q 'rule=sca_unavailable' "$npm_unknown_schema/out.txt"
grep -q 'evidence_complete=0' "$npm_unknown_schema/out.txt"
! grep -q 'severity=critical rule=vulnerability' "$npm_unknown_schema/out.txt"

composer_error="$(new_repo composer-audit-error)"
printf '%s\n' '{"name":"fixture/app"}' > "$composer_error/composer.json"
printf '%s\n' '{"packages":[],"packages-dev":[]}' > "$composer_error/composer.lock"
commit_all "$composer_error"
composer_error_hash="$(git -C "$composer_error" show HEAD:composer.lock | sha256sum | awk '{print $1}')"
printf '%s\n' "{\"advisories\":{},\"error\":\"audit failed\",\"hache_lock_sha256\":\"$composer_error_hash\"}" > "$composer_error/composer-audit.json"
raw_check "$composer_error" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_COMPOSER_AUDIT_FILE="$composer_error/composer-audit.json" > "$composer_error/out.txt"
grep -q 'rule=sca_unavailable' "$composer_error/out.txt"
grep -q 'evidence_complete=0' "$composer_error/out.txt"
'''
txt = txt.replace(needle, append + needle)
test.write_text(txt)

p = policy_json.read_text()
assert '"secret_scan_scope": "tracked_current_tree"' in p
policy_json.write_text(p.replace('"secret_scan_scope": "tracked_current_tree"', '"secret_scan_scope": "tracked_head_text_tree"'))

m = policy_md.read_text()
m = m.replace('secret scan de firmas de alta confianza sobre archivos de texto actualmente trackeados;', 'secret scan de firmas de alta confianza sobre blobs de texto trackeados del árbol de `HEAD`;')
m = m.replace('el alcance declarado es `tracked_text_tree`;', 'el alcance declarado es `tracked_head_text_tree`;')
policy_md.write_text(m)
