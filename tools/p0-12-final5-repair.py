from pathlib import Path

CHECK = Path('security/supply-chain/check.php')
RUN = Path('tests/run.sh')
ROUND3 = Path('tests/security/SupplyChainReviewRound3RegressionTest.sh')

text = CHECK.read_text()

start = text.index('/** @param array<string,mixed> $manifest */\nfunction validNpmLock')
end = text.index('\nfunction composerPlatformRequirement', start)
new_npm = r'''/** @return array<int,string>|null */
function npmWorkspacePatterns(array $manifest): ?array
{
    if (!array_key_exists('workspaces', $manifest)) {
        return [];
    }
    $raw = $manifest['workspaces'];
    if (!is_array($raw)) {
        return null;
    }
    if (array_is_list($raw)) {
        $items = $raw;
    } else {
        if (!isset($raw['packages']) || !is_array($raw['packages']) || !array_is_list($raw['packages'])) {
            return null;
        }
        $items = $raw['packages'];
    }
    $patterns = [];
    foreach ($items as $item) {
        if (!is_string($item)) {
            return null;
        }
        $pattern = trim(str_replace('\\', '/', $item));
        while (str_starts_with($pattern, './')) {
            $pattern = substr($pattern, 2);
        }
        $pattern = trim($pattern, '/');
        if ($pattern === '' || str_starts_with($pattern, '../') || str_contains($pattern, '/../')
            || str_starts_with($pattern, '!') || preg_match('/[{}\\[\\]]/', $pattern) === 1) {
            return null;
        }
        $patterns[$pattern] = true;
    }
    return array_keys($patterns);
}

function npmWorkspacePatternMatches(string $pattern, string $path): bool
{
    $regex = '';
    $length = strlen($pattern);
    for ($i = 0; $i < $length; $i++) {
        $char = $pattern[$i];
        if ($char === '*') {
            if ($i + 1 < $length && $pattern[$i + 1] === '*') {
                $regex .= '.*';
                $i++;
            } else {
                $regex .= '[^/]*';
            }
            continue;
        }
        if ($char === '?') {
            $regex .= '[^/]';
            continue;
        }
        $regex .= preg_quote($char, '~');
    }
    return preg_match('~^' . $regex . '$~D', $path) === 1;
}

/** @param array<string,mixed> $manifest @param array<int,string> $workspacePackagePaths */
function validNpmLock(array $lock, array $manifest, array $workspacePackagePaths = []): bool
{
    if (!isset($lock['lockfileVersion'])
        || !is_int($lock['lockfileVersion'])
        || !in_array($lock['lockfileVersion'], [2, 3], true)
        || !array_key_exists('packages', $lock)
        || !is_array($lock['packages'])
        || !array_key_exists('', $lock['packages'])
        || !is_array($lock['packages'][''])) {
        return false;
    }
    $rootPackage = $lock['packages'][''];
    foreach (['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as $section) {
        $manifestDependencies = $manifest[$section] ?? [];
        $lockDependencies = $rootPackage[$section] ?? [];
        if (!is_array($manifestDependencies) || !is_array($lockDependencies)) {
            return false;
        }
        foreach ([$manifestDependencies, $lockDependencies] as $dependencies) {
            foreach ($dependencies as $name => $constraint) {
                if (!is_string($name) || trim($name) === '' || !is_string($constraint) || trim($constraint) === '') {
                    return false;
                }
            }
        }
        ksort($manifestDependencies);
        ksort($lockDependencies);
        if ($manifestDependencies !== $lockDependencies) {
            return false;
        }
    }

    $workspacePatterns = npmWorkspacePatterns($manifest);
    if ($workspacePatterns === null) {
        return false;
    }
    if ($workspacePatterns !== []) {
        $expectedWorkspaces = [];
        foreach ($workspacePackagePaths as $workspacePath) {
            if (!is_string($workspacePath)) {
                return false;
            }
            $workspacePath = trim(str_replace('\\', '/', $workspacePath), '/');
            if ($workspacePath === '' || str_starts_with($workspacePath, '../') || str_contains($workspacePath, '/../')
                || str_contains('/' . $workspacePath . '/', '/node_modules/')) {
                return false;
            }
            foreach ($workspacePatterns as $pattern) {
                if (npmWorkspacePatternMatches($pattern, $workspacePath)) {
                    $expectedWorkspaces[$workspacePath] = true;
                    break;
                }
            }
        }
        foreach ($workspacePatterns as $pattern) {
            $matched = false;
            foreach (array_keys($expectedWorkspaces) as $workspacePath) {
                if (npmWorkspacePatternMatches($pattern, $workspacePath)) {
                    $matched = true;
                    break;
                }
            }
            if (!$matched) {
                return false;
            }
        }
        foreach (array_keys($expectedWorkspaces) as $workspacePath) {
            $workspaceData = $lock['packages'][$workspacePath] ?? null;
            if (!is_array($workspaceData)
                || !isset($workspaceData['name'], $workspaceData['version'])
                || !is_string($workspaceData['name']) || trim($workspaceData['name']) === ''
                || !is_string($workspaceData['version']) || trim($workspaceData['version']) === '') {
                return false;
            }
            $workspaceName = trim($workspaceData['name']);
            $linkPath = 'node_modules/' . $workspaceName;
            $linkData = $lock['packages'][$linkPath] ?? null;
            if (!is_array($linkData) || ($linkData['link'] ?? false) !== true
                || !isset($linkData['resolved']) || !is_string($linkData['resolved'])) {
                return false;
            }
            $resolved = trim(str_replace('\\', '/', $linkData['resolved']));
            while (str_starts_with($resolved, './')) {
                $resolved = substr($resolved, 2);
            }
            if (trim($resolved, '/') !== $workspacePath) {
                return false;
            }
        }
    }

    foreach ($lock['packages'] as $path => $data) {
        if (!is_string($path) || !is_array($data)) {
            return false;
        }
        foreach (['name', 'version'] as $field) {
            if (isset($data[$field]) && !is_string($data[$field])) {
                return false;
            }
        }
        if ($path !== '' && (($data['link'] ?? false) !== true) && (!isset($data['version']) || trim((string)$data['version']) === '')) {
            return false;
        }
        if (($data['link'] ?? false) === true && (!isset($data['resolved']) || !is_string($data['resolved']) || trim($data['resolved']) === '')) {
            return false;
        }
        if (isset($data['license'])) {
            if (!is_string($data['license']) && !is_array($data['license'])) {
                return false;
            }
            if (is_array($data['license'])) {
                foreach ($data['license'] as $license) {
                    if (!is_string($license)) {
                        return false;
                    }
                }
            }
        }
        $peerMeta = $data['peerDependenciesMeta'] ?? [];
        if (!is_array($peerMeta)) {
            return false;
        }
        foreach ($peerMeta as $peerName => $metadata) {
            if (!is_string($peerName) || trim($peerName) === '' || !is_array($metadata)) {
                return false;
            }
            if (array_key_exists('optional', $metadata) && !is_bool($metadata['optional'])) {
                return false;
            }
        }
        foreach (['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as $section) {
            $dependencies = $data[$section] ?? [];
            if (!is_array($dependencies)) {
                return false;
            }
            foreach ($dependencies as $name => $constraint) {
                if (!is_string($name) || trim($name) === '' || !is_string($constraint) || trim($constraint) === '') {
                    return false;
                }
                $resolved = npmLockResolvedPackage($lock['packages'], $path, $name);
                $optionalPeer = $section === 'peerDependencies'
                    && isset($peerMeta[$name])
                    && is_array($peerMeta[$name])
                    && (($peerMeta[$name]['optional'] ?? false) === true);
                if ($resolved === null) {
                    if ($optionalPeer) {
                        continue;
                    }
                    return false;
                }
                $resolvedVersion = $resolved['data']['version'] ?? null;
                if (!is_string($resolvedVersion) || trim($resolvedVersion) === '' || !npmVersionSatisfies($resolvedVersion, $constraint)) {
                    return false;
                }
            }
        }
    }
    return true;
}
'''
text = text[:start] + new_npm + text[end:]

old_composer = r'''    foreach (['packages', 'packages-dev'] as $section) {
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
'''
new_composer = r'''    foreach (['packages', 'packages-dev'] as $section) {
        $availableVersions = $section === 'packages' ? $prodVersions : $allVersions;
        $availableProviders = $section === 'packages' ? $prodProviders : $allProviders;
        foreach ($lock[$section] as $package) {
            $requirements = $package['require'] ?? [];
            foreach ($requirements as $name => $constraint) {
                if (!is_string($name) || trim($name) === '' || !is_string($constraint) || trim($constraint) === '') {
                    return false;
                }
                if (composerPlatformRequirement($name)) {
                    continue;
                }
                if (!$satisfies($name, $constraint, $availableVersions, $availableProviders)) {
                    return false;
                }
            }
        }
    }
'''
if old_composer not in text:
    raise SystemExit('composer transitive block not found')
text = text.replace(old_composer, new_composer, 1)

old_secret = "'private_key' => '~-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----~',"
new_secret = "'private_key' => '~-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----~',"
if old_secret not in text:
    raise SystemExit('private key rule not found')
text = text.replace(old_secret, new_secret, 1)

old_stack = r'''$stackRootsRaw = trim((string)envValue('SUPPLY_CHAIN_STACK_ROOTS', '.'));
$rawStackRoots = array_values(array_filter(array_map('trim', explode(',', $stackRootsRaw)), static fn(string $value): bool => $value !== ''));
if ($rawStackRoots === []) {
    $rawStackRoots = ['.'];
}
'''
new_stack = r'''$stackRootsOverride = envValue('SUPPLY_CHAIN_STACK_ROOTS');
$stackRootsExplicit = $stackRootsOverride !== null && trim($stackRootsOverride) !== '';
$stackRootsRaw = trim((string)($stackRootsExplicit ? $stackRootsOverride : '.'));
$rawStackRoots = array_values(array_filter(array_map('trim', explode(',', $stackRootsRaw)), static fn(string $value): bool => $value !== ''));
if ($rawStackRoots === []) {
    $rawStackRoots = ['.'];
}
'''
if old_stack not in text:
    raise SystemExit('stack root setup not found')
text = text.replace(old_stack, new_stack, 1)

old_count = r'''foreach ($stackRoots as $stackRelative) {
    withinRoot($root, $stackRelative);
    if (isset($trackedFileSet[stackFileRelative($stackRelative, 'composer.json')])) {
        $composerStackCount++;
    }
    if (isset($trackedFileSet[stackFileRelative($stackRelative, 'package.json')])) {
        $nodeStackCount++;
    }
}
'''
new_count = r'''foreach ($stackRoots as $stackRelative) {
    withinRoot($root, $stackRelative);
    $hasComposerManifest = isset($trackedFileSet[stackFileRelative($stackRelative, 'composer.json')]);
    $hasNodeManifest = isset($trackedFileSet[stackFileRelative($stackRelative, 'package.json')]);
    if ($stackRootsExplicit && !$hasComposerManifest && !$hasNodeManifest) {
        configError('stack_root_without_manifest root=' . $stackRelative);
    }
    if ($hasComposerManifest) {
        $composerStackCount++;
    }
    if ($hasNodeManifest) {
        $nodeStackCount++;
    }
}
'''
if old_count not in text:
    raise SystemExit('stack count block not found')
text = text.replace(old_count, new_count, 1)

old_call = "        if (!validNpmLock($lock, $resolved['manifest'])) {"
new_call = r'''        $workspacePackagePaths = [];
        $stackPrefix = $stackRelative === '.' ? '' : rtrim($stackRelative, '/') . '/';
        foreach ($trackedPaths as $trackedPath) {
            if ($stackPrefix !== '' && !str_starts_with($trackedPath, $stackPrefix)) {
                continue;
            }
            $withinStack = $stackPrefix === '' ? $trackedPath : substr($trackedPath, strlen($stackPrefix));
            if ($withinStack === 'package.json' || !str_ends_with($withinStack, '/package.json')) {
                continue;
            }
            $workspacePath = substr($withinStack, 0, -strlen('/package.json'));
            if ($workspacePath === '' || str_contains('/' . $workspacePath . '/', '/node_modules/')) {
                continue;
            }
            $workspacePackagePaths[] = $workspacePath;
        }
        if (!validNpmLock($lock, $resolved['manifest'], $workspacePackagePaths)) {'''
if old_call not in text:
    raise SystemExit('validNpmLock call not found')
text = text.replace(old_call, new_call, 1)

CHECK.write_text(text)

round3 = r'''#!/usr/bin/env bash
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

echo "SUPPLY_CHAIN_REVIEW_ROUND3_REGRESSION_OK"
'''
ROUND3.write_text(round3)

run = RUN.read_text()
needle = 'bash "$ROOT/tests/security/SupplyChainReviewRound2RegressionTest.sh"\n'
if needle not in run:
    raise SystemExit('round2 invocation not found')
if 'SupplyChainReviewRound3RegressionTest.sh' not in run:
    run = run.replace(needle, needle + 'bash "$ROOT/tests/security/SupplyChainReviewRound3RegressionTest.sh"\n', 1)
RUN.write_text(run)
