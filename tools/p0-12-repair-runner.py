from pathlib import Path
import re

CHECK = Path('security/supply-chain/check.php')
s = CHECK.read_text()


def sub_once(pattern: str, replacement: str, label: str) -> None:
    global s
    updated, count = re.subn(pattern, lambda _: replacement, s, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, got {count}')
    s = updated


def replace_once(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, got {count}')
    s = s.replace(old, new, 1)


# 1) Helpers that make all reviewed evidence attributable to HEAD.
helper_anchor = """function headFileContent(string $root, string $relativePath): ?string
{
    [$code, $out] = runCommand(['git', '-C', $root, 'show', 'HEAD:' . $relativePath], $root);
    return $code === 0 ? $out : null;
}
"""
helper_insert = helper_anchor + r'''

function headFileMode(string $root, string $relativePath): ?string
{
    [$code, $out] = runCommand(['git', '-C', $root, 'ls-tree', '-z', 'HEAD', '--', $relativePath], $root);
    if ($code !== 0 || $out === '') {
        return null;
    }
    if (preg_match('/^([0-9]{6})\s+[^\s]+\s+[0-9a-f]+\t/s', $out, $matches) !== 1) {
        return null;
    }
    return $matches[1];
}

function auditBoundToLock(array $audit, string $lockContent): bool
{
    $declared = $audit['hache_lock_sha256'] ?? null;
    if (!is_string($declared) || preg_match('/^[0-9a-fA-F]{64}$/', $declared) !== 1) {
        return false;
    }
    return hash_equals(hash('sha256', $lockContent), strtolower($declared));
}

function removeSupplyChainTempTree(string $path): void
{
    if (!file_exists($path) && !is_link($path)) {
        return;
    }
    if (is_dir($path) && !is_link($path)) {
        $entries = scandir($path);
        if (is_array($entries)) {
            foreach ($entries as $entry) {
                if ($entry === '.' || $entry === '..') {
                    continue;
                }
                removeSupplyChainTempTree($path . DIRECTORY_SEPARATOR . $entry);
            }
        }
        @rmdir($path);
        return;
    }
    @unlink($path);
}

/** @return array{0:int,1:string,2:string} */
function runHeadAudit(string $root, string $stackRelative, array $files, array $command): array
{
    try {
        $suffix = bin2hex(random_bytes(8));
    } catch (Throwable) {
        return [127, '', 'unable to allocate temporary audit directory'];
    }
    $tmp = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'hache-sca-' . $suffix;
    if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) {
        return [127, '', 'unable to create temporary audit directory'];
    }
    try {
        foreach ($files as $file) {
            if (!is_string($file) || $file === '' || str_contains($file, '/')) {
                return [127, '', 'invalid materialized audit filename'];
            }
            $relative = stackFileRelative($stackRelative, $file);
            $content = headFileContent($root, $relative);
            if ($content === null || file_put_contents($tmp . DIRECTORY_SEPARATOR . $file, $content) === false) {
                return [127, '', 'unable to materialize reviewed HEAD evidence'];
            }
        }
        return runCommand($command, $tmp);
    } finally {
        removeSupplyChainTempTree($tmp);
    }
}
'''
replace_once(helper_anchor, helper_insert, 'HEAD evidence helpers')

# 2) Composer abbreviated hyphen ranges: 1.0 - 2.0 means >=1.0.0 <2.1.0.
hyphen_start_marker = "if (preg_match('/^v?(\\d+(?:\\.\\d+){0,2})\\s+-\\s+v?(\\d+(?:\\.\\d+){0,2})$/', $branch, $range) === 1) {"
hyphen_start = s.find(hyphen_start_marker)
hyphen_next = s.find('$tokens = preg_split', hyphen_start)
if hyphen_start < 0 or hyphen_next < 0:
    raise SystemExit('Composer hyphen-range markers not found')
hyphen_line_start = s.rfind('\n', 0, hyphen_start) + 1
hyphen_next_line_start = s.rfind('\n', 0, hyphen_next) + 1
hyphen_replacement = r'''        if (preg_match('/^v?(\d+(?:\.\d+){0,2})\s+-\s+v?(\d+(?:\.\d+){0,2})$/', $branch, $range) === 1) {
            $lower = composerNumericVersion($range[1]);
            $upper = composerNumericVersion($range[2]);
            if ($lower !== null && $upper !== null) {
                $lockedString = composerVersionString($locked);
                $lowerOk = version_compare($lockedString, composerVersionString($lower), '>=');
                $upperParts = count(explode('.', $range[2]));
                if ($upperParts >= 3) {
                    $upperOk = version_compare($lockedString, composerVersionString($upper), '<=');
                } elseif ($upperParts === 2) {
                    $exclusiveUpper = [$upper[0], $upper[1] + 1, 0];
                    $upperOk = version_compare($lockedString, composerVersionString($exclusiveUpper), '<');
                } else {
                    $exclusiveUpper = [$upper[0] + 1, 0, 0];
                    $upperOk = version_compare($lockedString, composerVersionString($exclusiveUpper), '<');
                }
                if ($lowerOk && $upperOk) {
                    return true;
                }
            }
            continue;
        }
'''
s = s[:hyphen_line_start] + hyphen_replacement + s[hyphen_next_line_start:]

# 3) Composer graph validation recognizes virtual packages provided/replaced by locked packages.
composer_lock_function = r'''/** @param array<string,mixed> $manifest */
function validComposerLock(array $lock, array $manifest): bool
{
    if (!array_key_exists('packages', $lock) || !is_array($lock['packages'])
        || !array_key_exists('packages-dev', $lock) || !is_array($lock['packages-dev'])) {
        return false;
    }

    $prodVersions = [];
    $devVersions = [];
    $prodProviders = [];
    $devProviders = [];

    $indexPackages = static function (array $packages, array &$versions, array &$providers): bool {
        foreach ($packages as $package) {
            if (!is_array($package)
                || !isset($package['name'], $package['version'])
                || !is_string($package['name']) || trim($package['name']) === ''
                || !is_string($package['version']) || trim($package['version']) === '') {
                return false;
            }
            $name = trim($package['name']);
            $version = trim($package['version']);
            $versions[$name] = $version;

            if (isset($package['license'])) {
                if (!is_array($package['license'])) {
                    return false;
                }
                foreach ($package['license'] as $license) {
                    if (!is_string($license) || trim($license) === '') {
                        return false;
                    }
                }
            }
            if (isset($package['require']) && !is_array($package['require'])) {
                return false;
            }
            foreach (['provide', 'replace'] as $relation) {
                if (isset($package[$relation]) && !is_array($package[$relation])) {
                    return false;
                }
                foreach (($package[$relation] ?? []) as $virtual => $provided) {
                    if (!is_string($virtual) || trim($virtual) === '' || !is_string($provided) || trim($provided) === '') {
                        return false;
                    }
                    $provided = trim($provided);
                    if (strcasecmp($provided, 'self.version') === 0) {
                        $provided = $version;
                    }
                    $providers[trim($virtual)][] = $provided;
                }
            }
        }
        return true;
    };

    if (!$indexPackages($lock['packages'], $prodVersions, $prodProviders)
        || !$indexPackages($lock['packages-dev'], $devVersions, $devProviders)) {
        return false;
    }

    $allVersions = $prodVersions + $devVersions;
    $allProviders = $prodProviders;
    foreach ($devProviders as $name => $items) {
        foreach ($items as $item) {
            $allProviders[$name][] = $item;
        }
    }

    $constraintsIntersect = static function (string $left, string $right): bool {
        $candidates = [];
        foreach ([$left, $right] as $expression) {
            preg_match_all('/\d+(?:\.\d+){0,2}/', $expression, $matches);
            foreach ($matches[0] ?? [] as $raw) {
                $numeric = composerNumericVersion($raw);
                if ($numeric === null) {
                    continue;
                }
                $candidates[] = $numeric;
                $candidates[] = [$numeric[0], $numeric[1], $numeric[2] + 1];
                $candidates[] = [$numeric[0], $numeric[1] + 1, 0];
                $candidates[] = [$numeric[0] + 1, 0, 0];
                if ($numeric[2] > 0) {
                    $candidates[] = [$numeric[0], $numeric[1], $numeric[2] - 1];
                }
            }
        }
        $candidates[] = [0, 0, 0];
        foreach ($candidates as $candidate) {
            $version = composerVersionString($candidate);
            if (composerVersionSatisfies($version, $left) && composerVersionSatisfies($version, $right)) {
                return true;
            }
        }
        return false;
    };

    $satisfies = static function (string $name, string $constraint, array $versions, array $providers) use ($constraintsIntersect): bool {
        $lockedVersion = $versions[$name] ?? null;
        if (is_string($lockedVersion) && composerVersionSatisfies($lockedVersion, $constraint)) {
            return true;
        }
        foreach (($providers[$name] ?? []) as $provided) {
            if (!is_string($provided) || trim($provided) === '') {
                continue;
            }
            $provided = trim($provided);
            if ($provided === '*') {
                return true;
            }
            if (preg_match('/^v?\d+(?:\.\d+){0,2}$/', $provided) === 1) {
                if (composerVersionSatisfies($provided, $constraint)) {
                    return true;
                }
                continue;
            }
            if ($constraintsIntersect($provided, $constraint)) {
                return true;
            }
        }
        return false;
    };

    foreach (['require', 'require-dev'] as $section) {
        $requirements = $manifest[$section] ?? [];
        if (!is_array($requirements)) {
            return false;
        }
        foreach ($requirements as $name => $constraint) {
            if (!is_string($name) || trim($name) === '' || !is_string($constraint) || trim($constraint) === '') {
                return false;
            }
            if (composerPlatformRequirement($name)) {
                continue;
            }
            $versions = $section === 'require' ? $prodVersions : $allVersions;
            $providers = $section === 'require' ? $prodProviders : $allProviders;
            if (!$satisfies($name, $constraint, $versions, $providers)) {
                return false;
            }
        }
    }

    foreach (['packages', 'packages-dev'] as $section) {
        foreach ($lock[$section] as $package) {
            $requirements = $package['require'] ?? [];
            foreach ($requirements as $name => $constraint) {
                if (!is_string($name) || trim($name) === '' || !is_string($constraint) || trim($constraint) === '') {
                    return false;
                }
                if (composerPlatformRequirement($name)) {
                    continue;
                }
                if (!$satisfies($name, $constraint, $allVersions, $allProviders)) {
                    return false;
                }
            }
        }
    }
    return true;
}

'''
sub_once(
    r'/\*\* @param array<string,mixed> \$manifest \*/\nfunction validComposerLock\(array \$lock, array \$manifest\): bool\n\{.*?\n\}\n\n(?=/\*\* @return array<int,array<string,mixed>> \*/\nfunction npmVulnerabilities)',
    composer_lock_function,
    'Composer virtual package validation',
)

# 4) Secret scan: use HEAD tree types and blobs for regular files and symlinks.
secret_block = r'''foreach ($trackedPaths as $relativePath) {
    $modeInHead = headFileMode($root, $relativePath);
    if ($modeInHead === null) {
        $checks['secret_scan']['status'] = 'not_evaluated';
        $checks['secret_scan']['incomplete'] = true;
        $checks['secret_scan']['unreadable'][] = $relativePath;
        continue;
    }
    if (!in_array($modeInHead, ['100644', '100755', '120000'], true)) {
        $checks['secret_scan']['binary_skipped']++;
        continue;
    }
    $blob = headFileContent($root, $relativePath);
    if ($blob === null) {
        $checks['secret_scan']['status'] = 'not_evaluated';
        $checks['secret_scan']['incomplete'] = true;
        $checks['secret_scan']['unreadable'][] = $relativePath;
        continue;
    }
    if ($modeInHead === '120000') {
        $checks['secret_scan']['symlink_blobs_scanned']++;
    }
    if (str_contains(substr($blob, 0, 8192), "\0")) {
        $checks['secret_scan']['binary_skipped']++;
        continue;
    }
    $lines = preg_split('/\R/', $blob);
    if (!is_array($lines)) {
        $lines = [$blob];
    }
    foreach ($lines as $index => $line) {
        scanSecretLine($checks, $findings, $relativePath, $index + 1, $line, $secretRules, $allowlist, $level, $mode, $policy, $licensePolicy, $riskConfig);
    }
}

$stackRootsRaw ='''
sub_once(
    r'foreach \(\$trackedPaths as \$relativePath\) \{.*?\n\}\n\n\$stackRootsRaw =',
    secret_block,
    'Secret scan HEAD blobs',
)
s = s.replace("'scope' => 'tracked_text_tree'", "'scope' => 'tracked_head_text_tree'", 1)

# 5) Bind pre-generated audits to the reviewed lock and run live audits on HEAD materialization.
replace_once(
    """                $audit = null;
                $scaStatus = 'not_evaluated';
                $auditFile = envValue('SUPPLY_CHAIN_COMPOSER_AUDIT_FILE');""",
    """                $audit = null;
                $scaStatus = 'not_evaluated';
                $lockContent = headFileContent($root, $lockRelative);
                $auditFile = envValue('SUPPLY_CHAIN_COMPOSER_AUDIT_FILE');""",
    'Composer audit lock content',
)
replace_once(
    """                        if (validComposerAudit($candidate)) {
                            $audit = $candidate;
                            $scaStatus = 'evidence_file';
                        }""",
    """                        if (validComposerAudit($candidate)
                            && is_string($lockContent)
                            && auditBoundToLock($candidate, $lockContent)) {
                            $audit = $candidate;
                            $scaStatus = 'evidence_file';
                        }""",
    'Composer audit binding',
)
replace_once(
    """                    [$auditCode, $auditOut] = runCommand(['composer', 'audit', '--locked', '--format=json', '--no-interaction'], $stackDir);""",
    """                    [$auditCode, $auditOut] = runHeadAudit(
                        $root,
                        $stackRelative,
                        ['composer.json', 'composer.lock'],
                        ['composer', 'audit', '--locked', '--format=json', '--no-interaction']
                    );""",
    'Composer live audit on HEAD',
)
replace_once(
    """        $audit = null;
        $scaStatus = 'not_evaluated';
        $auditFile = envValue('SUPPLY_CHAIN_NPM_AUDIT_FILE');""",
    """        $audit = null;
        $scaStatus = 'not_evaluated';
        $lockContent = headFileContent($root, $nodeLockRelative);
        $auditFile = envValue('SUPPLY_CHAIN_NPM_AUDIT_FILE');""",
    'npm audit lock content',
)
replace_once(
    """                if (validNpmAudit($candidate)) {
                    $audit = $candidate;
                    $scaStatus = 'evidence_file';
                }""",
    """                if (validNpmAudit($candidate)
                    && is_string($lockContent)
                    && auditBoundToLock($candidate, $lockContent)) {
                    $audit = $candidate;
                    $scaStatus = 'evidence_file';
                }""",
    'npm audit binding',
)
replace_once(
    """            [$auditCode, $auditOut] = runCommand(['npm', 'audit', '--package-lock-only', '--json'], $stackDir);""",
    """            [$auditCode, $auditOut] = runHeadAudit(
                $root,
                $stackRelative,
                ['package.json', $nodeLockName],
                ['npm', 'audit', '--package-lock-only', '--json']
            );""",
    'npm live audit on HEAD',
)
s = s.replace(
    'SCA is NOT EVALUATED for this locked stack; evidence was absent or invalid. This is not a vulnerability finding and not a PASS.',
    'SCA is NOT EVALUATED for this locked stack; evidence was absent, invalid, not bound to the reviewed lock, or could not be executed against the reviewed HEAD. This is not a vulnerability finding and not a PASS.',
)
CHECK.write_text(s)

# Existing fixture audits become explicit evidence by carrying the reviewed lock hash.
run_check_new = r'''run_check() {
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
'''
for name in [
    'tests/security/SupplyChainPolicyTest.sh',
    'tests/security/SupplyChainReviewRegressionTest.sh',
    'tests/security/SupplyChainEvidenceScopeRegressionTest.sh',
    'tests/security/SupplyChainFinalReviewRegressionTest.sh',
]:
    p = Path(name)
    text = p.read_text()
    updated, count = re.subn(r'run_check\(\) \{\n.*?\n\}\n', lambda _: run_check_new, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{name}: run_check replacement count={count}')
    p.write_text(updated)

# A chmod in the working tree can no longer make committed evidence unreadable.
review_path = Path('tests/security/SupplyChainReviewRegressionTest.sh')
review = review_path.read_text()
replacement = r'''incomplete_secret="$(new_repo incomplete-secret)"
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

'''
review, count = re.subn(
    r'incomplete_secret="\$\(new_repo incomplete-secret\)".*?(?=echo "SUPPLY_CHAIN_REVIEW_REGRESSION_OK")',
    lambda _: replacement,
    review,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit(f'incomplete-secret regression replacement count={count}')
review_path.write_text(review)

# Dedicated regression for all five fresh P1 findings.
head_test = r'''#!/usr/bin/env bash
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
'''
Path('tests/security/SupplyChainHeadEvidenceRegressionTest.sh').write_text(head_test)

run_path = Path('tests/run.sh')
run_text = run_path.read_text()
marker = 'bash "$ROOT/tests/security/SupplyChainFinalReviewRegressionTest.sh"\n'
if marker not in run_text:
    raise SystemExit('tests/run.sh supply-chain marker missing')
run_path.write_text(run_text.replace(marker, marker + 'bash "$ROOT/tests/security/SupplyChainHeadEvidenceRegressionTest.sh"\n', 1))

policy = Path('security/supply-chain/POLICY.md')
policy_text = policy.read_text()
appendix = r'''

## Evidencia atribuible al HEAD revisado

- El secret scan evalúa el contenido y tipo versionados en el árbol de `HEAD`; no usa archivos regulares ni destinos de symlink del working tree como evidencia del commit reportado.
- Un audit npm/Composer pre-generado solo cuenta como evidencia si incluye `hache_lock_sha256` y ese SHA-256 coincide con el blob del lockfile revisado. Un reporte sin vínculo o con hash distinto queda `NOT EVALUATED`.
- Cuando el checker ejecuta `npm audit` o `composer audit`, materializa temporalmente desde `HEAD` únicamente el manifest y lockfile revisados, ejecuta allí la herramienta y elimina el temporal al terminar.
- `composer.lock` reconoce dependencias virtuales satisfechas mediante `provide`/`replace`; la validación de rangos conserva la semántica abreviada soportada por Composer, incluido `1.0 - 2.0`.
'''
if '## Evidencia atribuible al HEAD revisado' not in policy_text:
    policy.write_text(policy_text.rstrip() + appendix + '\n')
