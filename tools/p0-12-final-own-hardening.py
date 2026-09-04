from pathlib import Path

CHECK = Path('security/supply-chain/check.php')
ROUND3 = Path('tests/security/SupplyChainReviewRound3RegressionTest.sh')

text = CHECK.read_text()
start = text.index('/** @return array<int,string>|null */\nfunction npmWorkspacePatterns')
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

function npmDependencySectionsMatch(array $manifest, array $lockPackage): bool
{
    foreach (['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as $section) {
        $manifestDependencies = $manifest[$section] ?? [];
        $lockDependencies = $lockPackage[$section] ?? [];
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
    return true;
}

/** @return array<string,bool>|null */
function npmOptionalPeers(array $package): ?array
{
    $peers = $package['peerDependencies'] ?? [];
    $meta = $package['peerDependenciesMeta'] ?? [];
    if (!is_array($peers) || !is_array($meta)) {
        return null;
    }
    $optional = [];
    foreach ($meta as $peerName => $metadata) {
        if (!is_string($peerName) || trim($peerName) === '' || !is_array($metadata)
            || !array_key_exists($peerName, $peers)) {
            return null;
        }
        foreach (array_keys($metadata) as $metadataKey) {
            if ($metadataKey !== 'optional') {
                return null;
            }
        }
        if (array_key_exists('optional', $metadata) && !is_bool($metadata['optional'])) {
            return null;
        }
        if (($metadata['optional'] ?? false) === true) {
            $optional[$peerName] = true;
        }
    }
    ksort($optional);
    return $optional;
}

/** @param array<string,mixed> $manifest @param array<string,array<string,mixed>> $workspaceManifests */
function validNpmLock(array $lock, array $manifest, array $workspaceManifests = []): bool
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
    if (!npmDependencySectionsMatch($manifest, $rootPackage)) {
        return false;
    }
    $manifestOptionalPeers = npmOptionalPeers($manifest);
    $rootOptionalPeers = npmOptionalPeers($rootPackage);
    if ($manifestOptionalPeers === null || $rootOptionalPeers === null || $manifestOptionalPeers !== $rootOptionalPeers) {
        return false;
    }

    $workspacePatterns = npmWorkspacePatterns($manifest);
    if ($workspacePatterns === null) {
        return false;
    }
    if ($workspacePatterns !== []) {
        $expectedWorkspaces = [];
        foreach ($workspaceManifests as $workspacePath => $workspaceManifest) {
            if (!is_string($workspacePath) || !is_array($workspaceManifest)) {
                return false;
            }
            $workspacePath = trim(str_replace('\\', '/', $workspacePath), '/');
            if ($workspacePath === '' || str_starts_with($workspacePath, '../') || str_contains($workspacePath, '/../')
                || str_contains('/' . $workspacePath . '/', '/node_modules/')) {
                return false;
            }
            foreach ($workspacePatterns as $pattern) {
                if (npmWorkspacePatternMatches($pattern, $workspacePath)) {
                    $expectedWorkspaces[$workspacePath] = $workspaceManifest;
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
        foreach ($expectedWorkspaces as $workspacePath => $workspaceManifest) {
            $workspaceData = $lock['packages'][$workspacePath] ?? null;
            if (!is_array($workspaceData)
                || !isset($workspaceData['name'], $workspaceData['version'])
                || !is_string($workspaceData['name']) || trim($workspaceData['name']) === ''
                || !is_string($workspaceData['version']) || trim($workspaceData['version']) === '') {
                return false;
            }
            $manifestName = $workspaceManifest['name'] ?? null;
            if (!is_string($manifestName) || trim($manifestName) === '' || trim($manifestName) !== trim($workspaceData['name'])) {
                return false;
            }
            if (array_key_exists('version', $workspaceManifest)) {
                if (!is_string($workspaceManifest['version']) || trim($workspaceManifest['version']) === ''
                    || trim($workspaceManifest['version']) !== trim($workspaceData['version'])) {
                    return false;
                }
            }
            if (!npmDependencySectionsMatch($workspaceManifest, $workspaceData)) {
                return false;
            }
            $workspaceOptionalPeers = npmOptionalPeers($workspaceManifest);
            $lockWorkspaceOptionalPeers = npmOptionalPeers($workspaceData);
            if ($workspaceOptionalPeers === null || $lockWorkspaceOptionalPeers === null
                || $workspaceOptionalPeers !== $lockWorkspaceOptionalPeers) {
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
        $optionalPeers = npmOptionalPeers($data);
        if ($optionalPeers === null) {
            return false;
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
                $optionalPeer = $section === 'peerDependencies' && isset($optionalPeers[$name]);
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

old_index = "            $name = trim($package['name']);\n            $version = trim($package['version']);\n            $versions[$name] = $version;"
new_index = "            $name = trim($package['name']);\n            $version = trim($package['version']);\n            if (array_key_exists($name, $versions)) {\n                return false;\n            }\n            $versions[$name] = $version;"
if old_index not in text:
    raise SystemExit('composer package index marker not found')
text = text.replace(old_index, new_index, 1)

old_after_index = r'''    if (!$indexPackages($lock['packages'], $prodVersions, $prodProviders)
        || !$indexPackages($lock['packages-dev'], $devVersions, $devProviders)) {
        return false;
    }

    $allVersions = $prodVersions + $devVersions;
'''
new_after_index = r'''    if (!$indexPackages($lock['packages'], $prodVersions, $prodProviders)
        || !$indexPackages($lock['packages-dev'], $devVersions, $devProviders)) {
        return false;
    }
    if (array_intersect_key($prodVersions, $devVersions) !== []) {
        return false;
    }

    $allVersions = $prodVersions + $devVersions;
'''
if old_after_index not in text:
    raise SystemExit('composer post-index marker not found')
text = text.replace(old_after_index, new_after_index, 1)

old_workspace_call = r'''        $workspacePackagePaths = [];
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
new_workspace_call = r'''        $workspaceManifests = [];
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
            $workspaceManifests[$workspacePath] = loadJsonFromHead($root, $trackedPath);
        }
        if (!validNpmLock($lock, $resolved['manifest'], $workspaceManifests)) {'''
if old_workspace_call not in text:
    raise SystemExit('workspace caller marker not found')
text = text.replace(old_workspace_call, new_workspace_call, 1)
CHECK.write_text(text)

round3 = ROUND3.read_text()
marker = 'echo "SUPPLY_CHAIN_REVIEW_ROUND3_REGRESSION_OK"\n'
if marker not in round3:
    raise SystemExit('round3 end marker not found')
extra = r'''
workspace_drift="$(new_repo npm-workspace-manifest-drift)"
mkdir -p "$workspace_drift/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","workspaces":["packages/*"]}' > "$workspace_drift/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0","dependencies":{"b":"^1.0.0"}}' > "$workspace_drift/packages/a/package.json"
cat > "$workspace_drift/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{"name":"a","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$workspace_drift"
set +e
raw_check "$workspace_drift" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_drift/out.txt" 2>&1
workspace_drift_rc=$?
set -e
[[ "$workspace_drift_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$workspace_drift/out.txt"

root_peer_meta="$(new_repo npm-root-peer-meta-drift)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","peerDependencies":{"peer":"1.0.0"}}' > "$root_peer_meta/package.json"
cat > "$root_peer_meta/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","peerDependencies":{"peer":"1.0.0"},"peerDependenciesMeta":{"peer":{"optional":true}}}}}
JSON
commit_all "$root_peer_meta"
set +e
raw_check "$root_peer_meta" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$root_peer_meta/out.txt" 2>&1
root_peer_meta_rc=$?
set -e
[[ "$root_peer_meta_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$root_peer_meta/out.txt"

composer_duplicate="$(new_repo composer-duplicate-package)"
printf '%s\n' '{"name":"fixture/app","require":{"vendor/a":"^1.0"}}' > "$composer_duplicate/composer.json"
cat > "$composer_duplicate/composer.lock" <<'JSON'
{"packages":[{"name":"vendor/a","version":"1.0.0"}],"packages-dev":[{"name":"vendor/a","version":"1.1.0"}]}
JSON
commit_all "$composer_duplicate"
set +e
raw_check "$composer_duplicate" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_duplicate/out.txt" 2>&1
composer_duplicate_rc=$?
set -e
[[ "$composer_duplicate_rc" -eq 1 ]]
grep -q 'rule=composer_lock_invalid_format' "$composer_duplicate/out.txt"

'''
if 'npm-workspace-manifest-drift' not in round3:
    round3 = round3.replace(marker, extra + marker, 1)
ROUND3.write_text(round3)
