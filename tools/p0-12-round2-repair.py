from pathlib import Path

CHECK = Path('security/supply-chain/check.php')
s = CHECK.read_text()


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise SystemExit(f'{label}: start marker missing')
    j = text.find(end, i)
    if j < 0:
        raise SystemExit(f'{label}: end marker missing')
    return text[:i] + replacement + text[j:]


allow_start = '/** @return array<int,array{path:string,rule:string}> */\nfunction loadSecretAllowlist'
allow_end = '/** @param array<int,array{path:string,rule:string}> $allowlist */\nfunction secretAllowed'
allow_block = r'''/** @return array<int,array{path:string,rule:string}> */
function parseSecretAllowlist(string $raw, array $knownRules, string $source): array
{
    $rows = preg_split('/\R/', $raw);
    if (!is_array($rows)) {
        configError("unreadable_secret_allowlist source={$source}");
    }
    $entries = [];
    foreach ($rows as $row) {
        $row = trim($row);
        if ($row === '' || str_starts_with($row, '#')) {
            continue;
        }
        $parts = preg_split('/\s+/', $row, 2);
        if (!is_array($parts) || count($parts) !== 2) {
            configError("invalid_secret_allowlist_row value={$row}");
        }
        [$allowPath, $rule] = $parts;
        if (!preg_match('~^(?:tests/|fixtures/)[A-Za-z0-9._/-]+$~', $allowPath)) {
            configError("secret_allowlist_path_must_be_exact_fixture value={$allowPath}");
        }
        if (str_contains($allowPath, '..') || !array_key_exists($rule, $knownRules)) {
            configError("invalid_secret_allowlist_entry value={$row}");
        }
        $entries[] = ['path' => $allowPath, 'rule' => $rule];
    }
    return $entries;
}

/** @return array<int,array{path:string,rule:string}> */
function loadSecretAllowlist(string $path, array $knownRules): array
{
    if (!is_file($path)) {
        return [];
    }
    $raw = file_get_contents($path);
    if ($raw === false) {
        configError("unreadable_secret_allowlist path={$path}");
    }
    return parseSecretAllowlist($raw, $knownRules, $path);
}

/** @return array<int,array{path:string,rule:string}> */
function loadSecretAllowlistFromHead(string $root, string $relativePath, array $knownRules): array
{
    $raw = headFileContent($root, $relativePath);
    if ($raw === null) {
        return [];
    }
    return parseSecretAllowlist($raw, $knownRules, 'HEAD:' . $relativePath);
}

'''
s = replace_between(s, allow_start, allow_end, allow_block, 'allowlist loader')

npm_start = '/** @param array<string,mixed> $packages */\nfunction npmLockResolvesPackage'
npm_end = 'function composerPlatformRequirement(string $name): bool'
npm_block = r'''/** @return array{path:string,data:array<string,mixed>}|null */
function npmLockResolvedPackage(array $packages, string $fromPath, string $dependencyName): ?array
{
    $base = trim($fromPath, '/');
    while (true) {
        $candidate = ($base === '' ? '' : $base . '/') . 'node_modules/' . $dependencyName;
        if (isset($packages[$candidate]) && is_array($packages[$candidate])) {
            $data = $packages[$candidate];
            if (($data['link'] ?? false) === true) {
                $resolved = $data['resolved'] ?? null;
                if (!is_string($resolved) || trim($resolved) === '') {
                    return null;
                }
                $resolved = trim(str_replace('\\', '/', $resolved));
                while (str_starts_with($resolved, './')) {
                    $resolved = substr($resolved, 2);
                }
                $resolved = trim($resolved, '/');
                if ($resolved === '' || str_starts_with($resolved, '../') || str_contains($resolved, '/../')) {
                    return null;
                }
                if (!isset($packages[$resolved]) || !is_array($packages[$resolved])) {
                    return null;
                }
                return ['path' => $resolved, 'data' => $packages[$resolved]];
            }
            return ['path' => $candidate, 'data' => $data];
        }
        if ($base === '') {
            break;
        }
        $marker = '/node_modules/';
        $position = strrpos($base, $marker);
        $base = $position === false ? '' : substr($base, 0, $position);
    }
    return null;
}

/** @return array{0:int,1:int,2:int}|null */
function npmNumericVersion(string $version): ?array
{
    $value = trim($version);
    if (str_starts_with($value, 'v')) {
        $value = substr($value, 1);
    }
    if (preg_match('/^(\d+)\.(\d+)\.(\d+)$/', $value, $matches) !== 1) {
        return null;
    }
    return [(int)$matches[1], (int)$matches[2], (int)$matches[3]];
}

/** @param array{0:int,1:int,2:int} $version */
function npmVersionString(array $version): string
{
    return $version[0] . '.' . $version[1] . '.' . $version[2];
}

/** @param array{0:int,1:int,2:int} $locked */
function npmConstraintTokenSatisfied(array $locked, string $token): bool
{
    $token = trim($token);
    if ($token === '' || $token === '*' || strtolower($token) === 'x') {
        return true;
    }
    $lockedString = npmVersionString($locked);

    if (preg_match('/^([\^~])\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$/', $token, $matches) === 1) {
        $operator = $matches[1];
        $specified = isset($matches[3]) && $matches[3] !== '' ? (isset($matches[4]) && $matches[4] !== '' ? 3 : 2) : 1;
        $base = [(int)$matches[2], (int)($matches[3] ?? 0), (int)($matches[4] ?? 0)];
        if (version_compare($lockedString, npmVersionString($base), '<')) {
            return false;
        }
        if ($operator === '^') {
            if ($specified === 1 || $base[0] > 0) {
                $upper = [$base[0] + 1, 0, 0];
            } elseif ($specified === 2 || $base[1] > 0) {
                $upper = [0, $base[1] + 1, 0];
            } else {
                $upper = [0, 0, $base[2] + 1];
            }
        } else {
            $upper = $specified === 1 ? [$base[0] + 1, 0, 0] : [$base[0], $base[1] + 1, 0];
        }
        return version_compare($lockedString, npmVersionString($upper), '<');
    }

    if (preg_match('/^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$/', $token, $matches) === 1) {
        $specified = isset($matches[2]) && $matches[2] !== '' ? (isset($matches[3]) && $matches[3] !== '' ? 3 : 2) : 1;
        $base = [(int)$matches[1], (int)($matches[2] ?? 0), (int)($matches[3] ?? 0)];
        if ($specified === 3) {
            return version_compare($lockedString, npmVersionString($base), '=');
        }
        $upper = $specified === 1 ? [$base[0] + 1, 0, 0] : [$base[0], $base[1] + 1, 0];
        return version_compare($lockedString, npmVersionString($base), '>=')
            && version_compare($lockedString, npmVersionString($upper), '<');
    }

    if (preg_match('/^v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$/', $token, $matches) === 1) {
        if (in_array($matches[1], ['x', 'X', '*'], true)) {
            return true;
        }
        $major = (int)$matches[1];
        $minorRaw = $matches[2] ?? 'x';
        $patchRaw = $matches[3] ?? 'x';
        if (in_array($minorRaw, ['x', 'X', '*'], true)) {
            $lower = [$major, 0, 0];
            $upper = [$major + 1, 0, 0];
        } elseif (in_array($patchRaw, ['x', 'X', '*'], true)) {
            $minor = (int)$minorRaw;
            $lower = [$major, $minor, 0];
            $upper = [$major, $minor + 1, 0];
        } else {
            return false;
        }
        return version_compare($lockedString, npmVersionString($lower), '>=')
            && version_compare($lockedString, npmVersionString($upper), '<');
    }

    if (preg_match('/^(<=|>=|<|>|=)\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$/', $token, $matches) === 1) {
        $target = [(int)$matches[2], (int)($matches[3] ?? 0), (int)($matches[4] ?? 0)];
        return version_compare($lockedString, npmVersionString($target), $matches[1]);
    }

    return false;
}

function npmVersionSatisfies(string $version, string $constraint): bool
{
    $constraint = trim($constraint);
    if (str_starts_with($constraint, 'workspace:')) {
        $constraint = substr($constraint, strlen('workspace:'));
        if (in_array($constraint, ['', '*', '^', '~'], true)) {
            return npmNumericVersion($version) !== null;
        }
    }
    if ($constraint === '' || $constraint === '*') {
        return npmNumericVersion($version) !== null;
    }
    if (preg_match('~^(?:file:|link:|git\+|https?://|npm:)~i', $constraint) === 1) {
        return false;
    }
    $locked = npmNumericVersion($version);
    if ($locked === null) {
        return false;
    }
    $branches = preg_split('/\s*\|\|\s*/', $constraint);
    if (!is_array($branches)) {
        return false;
    }
    foreach ($branches as $branch) {
        $branch = trim($branch);
        if ($branch === '') {
            continue;
        }
        if (preg_match('/^v?(\d+(?:\.\d+){0,2})\s+-\s+v?(\d+(?:\.\d+){0,2})$/', $branch, $range) === 1) {
            $lowerParts = array_map('intval', explode('.', $range[1]));
            $upperPartsRaw = array_map('intval', explode('.', $range[2]));
            $lower = [$lowerParts[0] ?? 0, $lowerParts[1] ?? 0, $lowerParts[2] ?? 0];
            $upper = [$upperPartsRaw[0] ?? 0, $upperPartsRaw[1] ?? 0, $upperPartsRaw[2] ?? 0];
            $lockedString = npmVersionString($locked);
            $lowerOk = version_compare($lockedString, npmVersionString($lower), '>=');
            $upperSpecified = count($upperPartsRaw);
            if ($upperSpecified >= 3) {
                $upperOk = version_compare($lockedString, npmVersionString($upper), '<=');
            } elseif ($upperSpecified === 2) {
                $upperOk = version_compare($lockedString, npmVersionString([$upper[0], $upper[1] + 1, 0]), '<');
            } else {
                $upperOk = version_compare($lockedString, npmVersionString([$upper[0] + 1, 0, 0]), '<');
            }
            if ($lowerOk && $upperOk) {
                return true;
            }
            continue;
        }
        $tokens = preg_split('/\s+/', $branch);
        if (!is_array($tokens) || $tokens === []) {
            continue;
        }
        $all = true;
        foreach ($tokens as $token) {
            if ($token !== '' && !npmConstraintTokenSatisfied($locked, $token)) {
                $all = false;
                break;
            }
        }
        if ($all) {
            return true;
        }
    }
    return false;
}

/** @param array<string,mixed> $manifest */
function validNpmLock(array $lock, array $manifest): bool
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
        foreach (['dependencies', 'devDependencies', 'optionalDependencies'] as $section) {
            $dependencies = $data[$section] ?? [];
            if (!is_array($dependencies)) {
                return false;
            }
            foreach ($dependencies as $name => $constraint) {
                if (!is_string($name) || trim($name) === '' || !is_string($constraint) || trim($constraint) === '') {
                    return false;
                }
                $resolved = npmLockResolvedPackage($lock['packages'], $path, $name);
                if ($resolved === null) {
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
s = replace_between(s, npm_start, npm_end, npm_block, 'npm lock validation')

old_allow = "$allowlist = loadSecretAllowlist((string)envValue('SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE', $root . '/security/supply-chain/secret-scan.allowlist'), $secretRules);"
new_allow = r'''$allowlistOverride = envValue('SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE');
$allowlist = $allowlistOverride === null || $allowlistOverride === ''
    ? loadSecretAllowlistFromHead($root, 'security/supply-chain/secret-scan.allowlist', $secretRules)
    : loadSecretAllowlist($allowlistOverride, $secretRules);'''
if s.count(old_allow) != 1:
    raise SystemExit(f'allowlist main assignment count={s.count(old_allow)}')
s = s.replace(old_allow, new_allow, 1)
CHECK.write_text(s)


test_path = Path('tests/security/SupplyChainReviewRound2RegressionTest.sh')
test_path.write_text(r'''#!/usr/bin/env bash
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

write_bound_npm_audit() {
  local dir="$1"
  local out="$2"
  local lock_hash
  lock_hash="$(git -C "$dir" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
  printf '%s\n' "{\"auditReportVersion\":2,\"vulnerabilities\":{},\"hache_lock_sha256\":\"$lock_hash\"}" > "$out"
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

mismatch="$(new_repo npm-version-mismatch)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^2.0.0"}}' > "$mismatch/package.json"
cat > "$mismatch/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^2.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$mismatch"
write_bound_npm_audit "$mismatch" "$mismatch/npm-audit.json"
set +e
raw_check "$mismatch" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$mismatch/npm-audit.json" > "$mismatch/out.txt" 2>&1
mismatch_rc=$?
set -e
[[ "$mismatch_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$mismatch/out.txt"
grep -q 'rule=sca_unavailable' "$mismatch/out.txt"
grep -q 'rule=license_not_evaluated' "$mismatch/out.txt"
grep -q 'evidence_complete=0' "$mismatch/out.txt"

matching="$(new_repo npm-version-match)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^2.0.0"}}' > "$matching/package.json"
cat > "$matching/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^2.0.0"}},"node_modules/pkg":{"name":"pkg","version":"2.1.0","license":"MIT"}}}
JSON
commit_all "$matching"
write_bound_npm_audit "$matching" "$matching/npm-audit.json"
raw_check "$matching" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$matching/npm-audit.json" > "$matching/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$matching/out.txt"
grep -q 'evidence_complete=1' "$matching/out.txt"

workspace="$(new_repo npm-workspace-link)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"workspace-pkg":"workspace:*"}}' > "$workspace/package.json"
cat > "$workspace/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"workspace-pkg":"workspace:*"}},"node_modules/workspace-pkg":{"resolved":"packages/workspace-pkg","link":true},"packages/workspace-pkg":{"name":"workspace-pkg","version":"2.3.4","license":"MIT"}}}
JSON
commit_all "$workspace"
write_bound_npm_audit "$workspace" "$workspace/npm-audit.json"
raw_check "$workspace" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$workspace/npm-audit.json" > "$workspace/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace/out.txt"
grep -q 'evidence_complete=1' "$workspace/out.txt"

unsupported="$(new_repo npm-unsupported-constraint)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"file:../pkg"}}' > "$unsupported/package.json"
cat > "$unsupported/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"file:../pkg"}},"node_modules/pkg":{"name":"pkg","version":"1.0.0","license":"MIT"}}}
JSON
commit_all "$unsupported"
set +e
raw_check "$unsupported" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$unsupported/out.txt" 2>&1
unsupported_rc=$?
set -e
[[ "$unsupported_rc" -eq 1 ]]
grep -q 'rule=node_lock_invalid_format' "$unsupported/out.txt"
grep -q 'evidence_complete=0' "$unsupported/out.txt"

default_allow="$(new_repo default-allow-head)"
mkdir -p "$default_allow/tests"
secret_value="ghp_$(printf 'A%.0s' $(seq 1 40))"
printf '%s\n' "$secret_value" > "$default_allow/tests/fixture-secret.txt"
commit_all "$default_allow"
printf '%s\n' 'tests/fixture-secret.txt github_token' >> "$default_allow/security/supply-chain/secret-scan.allowlist"
set +e
raw_check "$default_allow" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$default_allow/out.txt" 2>&1
default_allow_rc=$?
set -e
[[ "$default_allow_rc" -eq 1 ]]
grep -q 'category=secret' "$default_allow/out.txt"
grep -q 'evidence_complete=1' "$default_allow/out.txt"
! grep -q "$secret_value" "$default_allow/out.txt"
! grep -q "$secret_value" "$default_allow/report.json"

cp "$default_allow/security/supply-chain/secret-scan.allowlist" "$TMP/explicit-allowlist"
raw_check "$default_allow" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE="$TMP/explicit-allowlist" > "$default_allow/override.txt"
grep -q 'enforced_blockers=0' "$default_allow/override.txt"

echo "SUPPLY_CHAIN_REVIEW_ROUND2_REGRESSION_OK"
''')

run_path = Path('tests/run.sh')
run = run_path.read_text()
marker = 'bash "$ROOT/tests/security/SupplyChainHeadEvidenceRegressionTest.sh"\n'
if run.count(marker) != 1:
    raise SystemExit(f'tests/run.sh marker count={run.count(marker)}')
run = run.replace(marker, marker + 'bash "$ROOT/tests/security/SupplyChainReviewRound2RegressionTest.sh"\n', 1)
run_path.write_text(run)

policy_path = Path('security/supply-chain/POLICY.md')
policy = policy_path.read_text()
old_node = 'Para npm, el lock soportado debe tener `lockfileVersion` 2/3, una entrada raíz válida y conjuntos de dependencias coherentes con `package.json`. Además, cada dependencia directa o transitiva declarada por un paquete debe resolverse desde ubicaciones alcanzables por la resolución jerárquica de Node; una copia anidada bajo un paquete hermano no satisface el requisito. Un grafo truncado queda inválido.'
new_node = old_node + ' La versión del paquete resuelto también debe satisfacer la restricción declarada. Los links/workspaces soportados se resuelven contra su entrada real del lock; protocolos o constraints que el checker no pueda interpretar de forma confiable no se elevan a evidencia completa y dejan el stack como inválido/NOT EVALUATED para SCA y licencias.'
if policy.count(old_node) != 1:
    raise SystemExit(f'POLICY npm paragraph count={policy.count(old_node)}')
policy = policy.replace(old_node, new_node, 1)
old_allow = '`secret-scan.allowlist` solo puede usarse para fixtures falsos deliberados. Cada entrada debe ser una **ruta exacta** bajo `tests/` o `fixtures/` y una regla exacta reconocida; no se permiten globs, `*` ni rutas de runtime como `src/`.'
new_allow = old_allow + ' La allowlist predeterminada se lee del blob versionado en `HEAD`, no del working tree. `SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE` es el único override explícito para aportar una allowlist externa.'
if policy.count(old_allow) != 1:
    raise SystemExit(f'POLICY allowlist paragraph count={policy.count(old_allow)}')
policy = policy.replace(old_allow, new_allow, 1)
policy_path.write_text(policy)
