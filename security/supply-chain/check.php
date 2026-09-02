#!/usr/bin/env php
<?php
declare(strict_types=1);

function envValue(string $name, ?string $default = null): ?string
{
    $value = getenv($name);
    return $value === false ? $default : $value;
}

function configError(string $message): never
{
    fwrite(STDERR, "SUPPLY_CHAIN_CONFIG_ERROR {$message}\n");
    exit(2);
}

/** @return array{0:int,1:string,2:string} */
function runCommand(array $command, string $cwd): array
{
    $spec = [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $process = proc_open($command, $spec, $pipes, $cwd);
    if (!is_resource($process)) {
        return [127, '', 'unable to start process'];
    }
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $code = proc_close($process);
    return [$code, $stdout === false ? '' : $stdout, $stderr === false ? '' : $stderr];
}

function commandExists(string $command): bool
{
    $path = getenv('PATH') ?: '';
    foreach (explode(PATH_SEPARATOR, $path) as $dir) {
        if ($dir !== '' && is_file($dir . DIRECTORY_SEPARATOR . $command) && is_executable($dir . DIRECTORY_SEPARATOR . $command)) {
            return true;
        }
    }
    return false;
}

/** @return array<string,mixed> */
function loadJsonFile(string $path): array
{
    if (!is_file($path)) {
        configError("missing_json_file path={$path}");
    }
    $raw = file_get_contents($path);
    if ($raw === false) {
        configError("unreadable_json_file path={$path}");
    }
    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        configError("invalid_json_file path={$path}");
    }
    return $decoded;
}

function headFileContent(string $root, string $relativePath): ?string
{
    [$code, $out] = runCommand(['git', '-C', $root, 'show', 'HEAD:' . $relativePath], $root);
    return $code === 0 ? $out : null;
}


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

/** @return array<string,mixed> */
function loadJsonFromHead(string $root, string $relativePath): array
{
    $raw = headFileContent($root, $relativePath);
    if ($raw === null) {
        configError("missing_head_json path={$relativePath}");
    }
    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        configError("invalid_head_json path={$relativePath}");
    }
    return $decoded;
}

function normalizeSeverity(?string $severity): string
{
    $value = strtolower(trim((string)$severity));
    return in_array($value, ['critical', 'high', 'medium', 'low'], true) ? $value : 'unknown';
}

function severityRank(string $severity): int
{
    return match ($severity) {
        'critical' => 4,
        'high' => 3,
        'medium' => 2,
        'low' => 1,
        default => 0,
    };
}

function withinRoot(string $root, string $relative): string
{
    if ($relative === '' || $relative === '.') {
        return $root;
    }
    if (str_starts_with($relative, '/') || preg_match('~^[A-Za-z]:[\\/]~', $relative)) {
        configError("stack_root_must_be_relative value={$relative}");
    }
    $candidate = realpath($root . DIRECTORY_SEPARATOR . $relative);
    if ($candidate === false || ($candidate !== $root && !str_starts_with($candidate, $root . DIRECTORY_SEPARATOR))) {
        configError("invalid_stack_root value={$relative}");
    }
    return $candidate;
}

function stackFileRelative(string $stackRelative, string $file): string
{
    if ($stackRelative === '' || $stackRelative === '.') {
        return $file;
    }
    return trim($stackRelative, '/') . '/' . $file;
}

/** @return array<int,string> */
function trackedFiles(string $root): array
{
    [$code, $out, $err] = runCommand(['git', '-C', $root, 'ls-tree', '-rz', '--name-only', '--full-tree', 'HEAD'], $root);
    if ($code !== 0) {
        configError('git_ls_tree_failed ' . trim($err));
    }
    return array_values(array_filter(explode("\0", $out), static fn(string $value): bool => $value !== ''));
}

function findingId(string $category, string $rule, string $location, string $subject): string
{
    return substr(hash('sha256', implode('|', [$category, $rule, $location, $subject])), 0, 20);
}

/** @return array<int,array{path:string,rule:string}> */
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

/** @param array<int,array{path:string,rule:string}> $allowlist */
function secretAllowed(array $allowlist, string $path, string $rule): bool
{
    foreach ($allowlist as $entry) {
        if ($entry['path'] === $path && $entry['rule'] === $rule) {
            return true;
        }
    }
    return false;
}

/** @param array<string,mixed> $licensePolicy */
function policyBlocks(string $category, string $rule, string $severity, string $level, array $licensePolicy): bool
{
    if ($category === 'secret' || $category === 'lockfile') {
        return true;
    }
    if ($category === 'sca') {
        return $rule === 'vulnerability'
            && in_array($level, ['B', 'C'], true)
            && in_array($severity, ['critical', 'high'], true);
    }
    if ($category === 'license') {
        if ($rule === 'license_denied') {
            return (bool)($licensePolicy['block_denied'] ?? true);
        }
        if ($rule === 'license_missing') {
            return (bool)($licensePolicy['block_missing'] ?? false);
        }
    }
    return false;
}

/** @param array<string,mixed> $riskConfig */
function acceptedRiskFor(string $findingId, array $riskConfig): ?array
{
    $exceptions = $riskConfig['exceptions'] ?? [];
    if (!is_array($exceptions)) {
        configError('accepted_risk.exceptions must be an array');
    }
    foreach ($exceptions as $entry) {
        if (!is_array($entry) || !isset($entry['finding_id']) || !is_string($entry['finding_id']) || $entry['finding_id'] !== $findingId) {
            continue;
        }
        foreach (['owner', 'approval_ref', 'mitigation', 'expires_at'] as $field) {
            if (!array_key_exists($field, $entry) || !is_string($entry[$field]) || trim($entry[$field]) === '') {
                return null;
            }
        }
        $date = $entry['expires_at'];
        if (preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $date, $parts) !== 1) {
            return null;
        }
        $year = (int)$parts[1];
        $month = (int)$parts[2];
        $day = (int)$parts[3];
        if (!checkdate($month, $day, $year)) {
            return null;
        }
        $expires = strtotime($date . ' 23:59:59 UTC');
        if ($expires === false || $expires < time()) {
            return null;
        }
        return [
            'owner' => $entry['owner'],
            'approval_ref' => $entry['approval_ref'],
            'mitigation' => $entry['mitigation'],
            'expires_at' => $date,
        ];
    }
    return null;
}

/** @param array<int,array<string,mixed>> $findings */
function addFinding(
    array &$findings,
    string $category,
    string $rule,
    string $severity,
    string $location,
    string $subject,
    string $detail,
    string $level,
    string $mode,
    array $policy,
    array $licensePolicy,
    array $riskConfig
): void {
    $severity = normalizeSeverity($severity);
    $id = findingId($category, $rule, $location, $subject);
    $policyBlocking = policyBlocks($category, $rule, $severity, $level, $licensePolicy);
    $accepted = ($category === 'sca' && $rule === 'vulnerability') ? acceptedRiskFor($id, $riskConfig) : null;
    $baselineBlocks = $policy['baseline_blocks'] ?? ['secret', 'lockfile'];
    if (!is_array($baselineBlocks)) {
        configError('policy.baseline_blocks must be an array');
    }
    $enforcedByMode = $mode === 'block' || ($mode === 'baseline' && in_array($category, $baselineBlocks, true));
    $effectiveBlocking = $policyBlocking && $accepted === null && $enforcedByMode;
    $slaMap = $policy['sla_hours'] ?? [];
    $slaHours = is_array($slaMap) && isset($slaMap[$severity]) ? (int)$slaMap[$severity] : null;
    $findings[] = [
        'id' => $id,
        'category' => $category,
        'rule' => $rule,
        'severity' => $severity,
        'location' => $location,
        'subject' => $subject,
        'detail' => $detail,
        'policy_blocking' => $policyBlocking,
        'accepted_risk' => $accepted,
        'enforced_by_mode' => $enforcedByMode,
        'effective_blocking' => $effectiveBlocking,
        'sla_hours' => $slaHours,
    ];
}

function validNpmAudit(array $audit): bool
{
    if (!isset($audit['auditReportVersion'])
        || !is_int($audit['auditReportVersion'])
        || !array_key_exists('vulnerabilities', $audit)
        || !is_array($audit['vulnerabilities'])
        || isset($audit['error'])) {
        return false;
    }
    foreach ($audit['vulnerabilities'] as $package => $data) {
        if (!is_string($package) || trim($package) === '' || !is_array($data) || !array_key_exists('via', $data) || !is_array($data['via'])) {
            return false;
        }
        if (!isset($data['severity']) || !is_string($data['severity']) || normalizeSeverity($data['severity']) === 'unknown') {
            return false;
        }
        foreach ($data['via'] as $entry) {
            if (is_string($entry)) {
                if (trim($entry) === '') {
                    return false;
                }
                continue;
            }
            if (!is_array($entry)) {
                return false;
            }
            if (!array_key_exists('source', $entry)
                || (!is_int($entry['source']) && (!is_string($entry['source']) || trim($entry['source']) === ''))) {
                return false;
            }
            if (!array_key_exists('severity', $entry)
                || !is_string($entry['severity'])
                || normalizeSeverity($entry['severity']) === 'unknown') {
                return false;
            }
            foreach (['title', 'url'] as $field) {
                if (isset($entry[$field]) && !is_string($entry[$field])) {
                    return false;
                }
            }
        }
    }
    return true;
}

function validComposerAudit(array $audit): bool
{
    if (!array_key_exists('advisories', $audit) || !is_array($audit['advisories'])) {
        return false;
    }
    foreach ($audit['advisories'] as $package => $items) {
        if (!is_string($package) || trim($package) === '' || !is_array($items)) {
            return false;
        }
        foreach ($items as $entry) {
            if (!is_array($entry)) {
                return false;
            }
            $packageName = $entry['packageName'] ?? $package;
            if (!is_string($packageName) || trim($packageName) === '') {
                return false;
            }
            if (!isset($entry['severity']) || !is_string($entry['severity']) || normalizeSeverity($entry['severity']) === 'unknown') {
                return false;
            }
            $advisoryId = $entry['advisoryId'] ?? null;
            $cve = $entry['cve'] ?? null;
            $hasIdentity = (is_string($advisoryId) && trim($advisoryId) !== '') || (is_string($cve) && trim($cve) !== '');
            if (!$hasIdentity) {
                return false;
            }
            foreach (['packageName', 'advisoryId', 'cve', 'title', 'link'] as $field) {
                if (isset($entry[$field]) && !is_string($entry[$field])) {
                    return false;
                }
            }
        }
    }
    return true;
}

/** @return array{0:int,1:int,2:int}|null */
function composerNumericVersion(string $version): ?array
{
    $value = trim($version);
    if (str_starts_with($value, 'v')) {
        $value = substr($value, 1);
    }
    if (preg_match('/^(\d+)(?:\.(\d+))?(?:\.(\d+))?/', $value, $matches) !== 1) {
        return null;
    }
    return [(int)$matches[1], (int)($matches[2] ?? 0), (int)($matches[3] ?? 0)];
}

/** @param array{0:int,1:int,2:int} $version */
function composerVersionString(array $version): string
{
    return $version[0] . '.' . $version[1] . '.' . $version[2];
}

/** @param array{0:int,1:int,2:int} $locked */
function composerConstraintTokenSatisfied(array $locked, string $token): bool
{
    $token = trim(preg_replace('/@(?:dev|stable|beta|alpha|RC)$/i', '', $token) ?? $token);
    if ($token === '' || $token === '*') {
        return true;
    }
    $lockedString = composerVersionString($locked);

    if (preg_match('/^([\^~])\s*v?(\d+(?:\.\d+){0,2})$/', $token, $matches) === 1) {
        $operator = $matches[1];
        $parts = array_map('intval', explode('.', $matches[2]));
        $specified = count($parts);
        $base = [$parts[0] ?? 0, $parts[1] ?? 0, $parts[2] ?? 0];
        if (version_compare($lockedString, composerVersionString($base), '<')) {
            return false;
        }
        if ($operator === '^') {
            if ($specified === 1) {
                $upper = [$base[0] + 1, 0, 0];
            } elseif ($base[0] > 0) {
                $upper = [$base[0] + 1, 0, 0];
            } elseif ($specified === 2 || $base[1] > 0) {
                $upper = [0, $base[1] + 1, 0];
            } else {
                $upper = [0, 0, $base[2] + 1];
            }
        } else {
            $upper = $specified >= 3 ? [$base[0], $base[1] + 1, 0] : [$base[0] + 1, 0, 0];
        }
        return version_compare($lockedString, composerVersionString($upper), '<');
    }

    if (preg_match('/^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?[.](?:\*|x|X)$/', $token, $matches) === 1
        || preg_match('/^v?(\d+)(?:\.(\d+))?\.(?:\*|x|X)$/', $token, $matches) === 1) {
        $major = (int)$matches[1];
        $minor = isset($matches[2]) && $matches[2] !== '' ? (int)$matches[2] : null;
        $lower = [$major, $minor ?? 0, 0];
        $upper = $minor === null ? [$major + 1, 0, 0] : [$major, $minor + 1, 0];
        return version_compare($lockedString, composerVersionString($lower), '>=')
            && version_compare($lockedString, composerVersionString($upper), '<');
    }

    if (preg_match('/^(<=|>=|<|>|!=|=)?\s*v?(\d+(?:\.\d+){0,2})$/', $token, $matches) === 1) {
        $operator = $matches[1] !== '' ? $matches[1] : '=';
        $target = composerNumericVersion($matches[2]);
        return $target !== null && version_compare($lockedString, composerVersionString($target), $operator);
    }

    return false;
}

function composerVersionSatisfies(string $version, string $constraint): bool
{
    $constraint = trim($constraint);
    if ($constraint === '' || $constraint === '*') {
        return true;
    }
    $locked = composerNumericVersion($version);
    if ($locked === null) {
        return trim($version) === $constraint;
    }
    $branches = preg_split('/\s*\|\|?\s*/', $constraint);
    if (!is_array($branches)) {
        return false;
    }
    foreach ($branches as $branch) {
        $branch = trim($branch);
        if ($branch === '') {
            continue;
        }
        if (preg_match('/^v?(\d+(?:\.\d+){0,2})\s+-\s+v?(\d+(?:\.\d+){0,2})$/', $branch, $range) === 1) {
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
        $tokens = preg_split('/(?:\s*,\s*|\s+)/', $branch);
        if (!is_array($tokens) || $tokens === []) {
            continue;
        }
        $all = true;
        foreach ($tokens as $token) {
            if ($token !== '' && !composerConstraintTokenSatisfied($locked, $token)) {
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

/** @return array{path:string,data:array<string,mixed>}|null */
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

function composerPlatformRequirement(string $name): bool
{
    return $name === 'php'
        || $name === 'hhvm'
        || str_starts_with($name, 'php-')
        || str_starts_with($name, 'ext-')
        || str_starts_with($name, 'lib-')
        || $name === 'composer-plugin-api'
        || $name === 'composer-runtime-api';
}

/** @param array<string,mixed> $manifest */
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

/** @return array<int,array<string,mixed>> */
function npmVulnerabilities(array $audit): array
{
    $result = [];
    foreach ((array)($audit['vulnerabilities'] ?? []) as $package => $data) {
        if (!is_array($data)) {
            continue;
        }
        $packageSeverity = normalizeSeverity((string)($data['severity'] ?? 'unknown'));
        $objectAdvisories = 0;
        $seen = [];
        foreach ((array)($data['via'] ?? []) as $entry) {
            if (!is_array($entry)) {
                continue;
            }
            $objectAdvisories++;
            $advisory = isset($entry['source']) ? 'npm:' . (string)$entry['source'] : 'npm:' . $package . ':via:' . $objectAdvisories;
            $key = (string)$package . '|' . $advisory;
            if (isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $severity = normalizeSeverity((string)($entry['severity'] ?? $packageSeverity));
            if ($severity === 'unknown') {
                $severity = $packageSeverity;
            }
            $result[] = [
                'package' => (string)$package,
                'severity' => $severity,
                'advisory' => $advisory,
                'title' => (string)($entry['title'] ?? 'npm audit finding'),
                'url' => (string)($entry['url'] ?? ''),
            ];
        }
        if ($objectAdvisories === 0) {
            $result[] = [
                'package' => (string)$package,
                'severity' => $packageSeverity,
                'advisory' => 'npm:' . (string)$package,
                'title' => 'npm audit package finding',
                'url' => '',
            ];
        }
    }
    return $result;
}

/** @return array<int,array<string,mixed>> */
function composerVulnerabilities(array $audit): array
{
    $result = [];
    foreach ((array)($audit['advisories'] ?? []) as $package => $items) {
        if (!is_array($items)) {
            continue;
        }
        foreach ($items as $entry) {
            if (!is_array($entry)) {
                continue;
            }
            $advisoryId = isset($entry['advisoryId']) && is_string($entry['advisoryId']) ? trim($entry['advisoryId']) : '';
            $cve = isset($entry['cve']) && is_string($entry['cve']) ? trim($entry['cve']) : '';
            $advisory = $advisoryId !== '' ? $advisoryId : ($cve !== '' ? $cve : ('composer:' . $package));
            $result[] = [
                'package' => (string)($entry['packageName'] ?? $package),
                'severity' => normalizeSeverity((string)($entry['severity'] ?? 'unknown')),
                'advisory' => $advisory,
                'title' => (string)($entry['title'] ?? 'composer audit finding'),
                'url' => (string)($entry['link'] ?? ''),
            ];
        }
    }
    return $result;
}

/** @return array<int,array{name:string,version:string,licenses:array<int,string>}> */
function npmPackagesForLicense(array $lock): array
{
    $result = [];
    foreach ((array)($lock['packages'] ?? []) as $path => $data) {
        if ($path === '' || !is_array($data)) {
            continue;
        }
        $licenses = [];
        $license = $data['license'] ?? null;
        if (is_string($license) && trim($license) !== '') {
            $licenses[] = trim($license);
        } elseif (is_array($license)) {
            foreach ($license as $item) {
                if (is_string($item) && trim($item) !== '') {
                    $licenses[] = trim($item);
                }
            }
        }
        $result[] = [
            'name' => (string)($data['name'] ?? basename((string)$path)),
            'version' => (string)($data['version'] ?? 'unknown'),
            'licenses' => array_values(array_unique($licenses)),
        ];
    }
    return $result;
}

/** @return array<int,array{name:string,version:string,licenses:array<int,string>}> */
function composerPackagesForLicense(array $lock): array
{
    $result = [];
    foreach (['packages', 'packages-dev'] as $section) {
        foreach ((array)($lock[$section] ?? []) as $data) {
            if (!is_array($data)) {
                continue;
            }
            $licenses = [];
            foreach ((array)($data['license'] ?? []) as $item) {
                if (is_string($item) && trim($item) !== '') {
                    $licenses[] = trim($item);
                }
            }
            $result[] = [
                'name' => (string)($data['name'] ?? 'unknown'),
                'version' => (string)($data['version'] ?? 'unknown'),
                'licenses' => array_values(array_unique($licenses)),
            ];
        }
    }
    return $result;
}

/** @return array{manager:?string,lock:?string,error:?string,manifest:array<string,mixed>} */
function resolveNodeLock(string $root, string $stackDir, string $stackRelative, array $headFileSet): array
{
    $manifestRelative = stackFileRelative($stackRelative, 'package.json');
    $manifest = loadJsonFromHead($root, $manifestRelative);
    $declared = $manifest['packageManager'] ?? '';
    if (!is_string($declared)) {
        return ['manager' => null, 'lock' => null, 'error' => 'unsupported_package_manager', 'manifest' => $manifest];
    }
    $declared = trim($declared);
    $manager = null;
    if ($declared !== '') {
        if (preg_match('/^(npm|yarn|pnpm)@/', $declared, $matches) !== 1) {
            return ['manager' => null, 'lock' => null, 'error' => 'unsupported_package_manager', 'manifest' => $manifest];
        }
        $manager = $matches[1];
    }
    $recognized = ['package-lock.json', 'npm-shrinkwrap.json', 'yarn.lock', 'pnpm-lock.yaml'];
    $headLocks = [];
    $diskLocks = [];
    foreach ($recognized as $candidate) {
        $relative = stackFileRelative($stackRelative, $candidate);
        if (isset($headFileSet[$relative])) {
            $headLocks[] = $candidate;
        }
        if (is_file($stackDir . '/' . $candidate)) {
            $diskLocks[] = $candidate;
        }
    }
    if (count($headLocks) > 1) {
        return ['manager' => $manager, 'lock' => null, 'error' => 'ambiguous_node_lockfiles', 'manifest' => $manifest];
    }
    if ($headLocks === []) {
        if ($diskLocks !== []) {
            return ['manager' => $manager, 'lock' => count($diskLocks) === 1 ? $diskLocks[0] : null, 'error' => 'node_lock_untracked', 'manifest' => $manifest];
        }
        return ['manager' => $manager, 'lock' => null, 'error' => 'node_lock_missing', 'manifest' => $manifest];
    }
    $lock = $headLocks[0];
    $expected = match ($manager) {
        'npm' => ['package-lock.json', 'npm-shrinkwrap.json'],
        'yarn' => ['yarn.lock'],
        'pnpm' => ['pnpm-lock.yaml'],
        default => $recognized,
    };
    if (!in_array($lock, $expected, true)) {
        return ['manager' => $manager, 'lock' => $lock, 'error' => 'node_lock_manager_mismatch', 'manifest' => $manifest];
    }
    return ['manager' => $manager, 'lock' => $lock, 'error' => null, 'manifest' => $manifest];
}

/** @param array<string,string> $secretRules */
function scanSecretLine(array &$checks, array &$findings, string $relativePath, int $lineNumber, string $line, array $secretRules, array $allowlist, string $level, string $mode, array $policy, array $licensePolicy, array $riskConfig): void
{
    foreach ($secretRules as $rule => $regex) {
        if (preg_match($regex, $line) !== 1 || secretAllowed($allowlist, $relativePath, $rule)) {
            continue;
        }
        $checks['secret_scan']['status'] = 'findings';
        addFinding(
            $findings,
            'secret',
            $rule,
            'critical',
            $relativePath . ':' . $lineNumber,
            $relativePath . '|' . $rule,
            'High-confidence secret signature matched; value redacted. Revoke/rotate if real and remove from Git history as required.',
            $level,
            $mode,
            $policy,
            $licensePolicy,
            $riskConfig
        );
    }
}

$mode = strtolower((string)envValue('SUPPLY_CHAIN_MODE', 'report'));
if (!in_array($mode, ['report', 'baseline', 'block'], true)) {
    configError("invalid_mode value={$mode}");
}
$level = strtoupper((string)envValue('SUPPLY_CHAIN_LEVEL', 'A'));
if (!in_array($level, ['A', 'B', 'C'], true)) {
    configError("invalid_level value={$level}");
}
$rootRaw = (string)envValue('SUPPLY_CHAIN_ROOT', dirname(__DIR__, 2));
$root = realpath($rootRaw);
if ($root === false || !is_dir($root)) {
    configError("invalid_root path={$rootRaw}");
}
$policy = loadJsonFile((string)envValue('SUPPLY_CHAIN_POLICY_FILE', $root . '/security/supply-chain/policy.json'));
$licensePolicy = loadJsonFile((string)envValue('SUPPLY_CHAIN_LICENSE_POLICY_FILE', $root . '/security/supply-chain/license-policy.json'));
$riskConfig = loadJsonFile((string)envValue('SUPPLY_CHAIN_ACCEPTED_RISK_FILE', $root . '/security/supply-chain/accepted-risk.json'));
$reportFile = (string)envValue('SUPPLY_CHAIN_REPORT_FILE', sys_get_temp_dir() . '/hache-supply-chain-report.json');
$disableExternalSca = envValue('SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA', '0') === '1';

$secretRules = [
    'private_key' => '~-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----~',
    'aws_access_key' => '~\bAKIA[0-9A-Z]{16}\b~',
    'github_token' => '~\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,})\b~',
    'slack_token' => '~\bxox[baprs]-[A-Za-z0-9-]{20,}\b~',
    'openai_key' => '~\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b~',
    'stripe_live_secret' => '~\bsk_live_[A-Za-z0-9]{16,}\b~',
    'google_api_key' => '~\bAIza[0-9A-Za-z_-]{30,}\b~',
];
$allowlistOverride = envValue('SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE');
$allowlist = $allowlistOverride === null || $allowlistOverride === ''
    ? loadSecretAllowlistFromHead($root, 'security/supply-chain/secret-scan.allowlist', $secretRules)
    : loadSecretAllowlist($allowlistOverride, $secretRules);
$findings = [];
$checks = [
    'secret_scan' => ['status' => 'pass', 'scope' => 'tracked_head_text_tree', 'binary_skipped' => 0, 'symlink_blobs_scanned' => 0, 'incomplete' => false],
    'lockfiles' => ['status' => 'pass'],
    'sca' => [],
    'licenses' => [],
];
$trackedPaths = trackedFiles($root);
$trackedFileSet = array_fill_keys($trackedPaths, true);

foreach ($trackedPaths as $relativePath) {
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

$stackRootsRaw = trim((string)envValue('SUPPLY_CHAIN_STACK_ROOTS', '.'));
$stackRoots = array_values(array_unique(array_filter(array_map('trim', explode(',', $stackRootsRaw)), static fn(string $value): bool => $value !== '')));
if ($stackRoots === []) {
    $stackRoots = ['.'];
}
$stackSummaries = [];
$deniedLicenses = array_map('strval', is_array($licensePolicy['denied'] ?? null) ? $licensePolicy['denied'] : []);
$reportMissingLicense = (bool)($licensePolicy['report_missing'] ?? true);
$composerStackCount = 0;
$nodeStackCount = 0;
foreach ($stackRoots as $stackRelative) {
    withinRoot($root, $stackRelative);
    if (isset($trackedFileSet[stackFileRelative($stackRelative, 'composer.json')])) {
        $composerStackCount++;
    }
    if (isset($trackedFileSet[stackFileRelative($stackRelative, 'package.json')])) {
        $nodeStackCount++;
    }
}

foreach ($stackRoots as $stackRelative) {
    $stackDir = withinRoot($root, $stackRelative);
    $displayRoot = $stackRelative === '.' ? '.' : rtrim($stackRelative, '/');
    $composerManifestRelative = stackFileRelative($stackRelative, 'composer.json');
    $nodeManifestRelative = stackFileRelative($stackRelative, 'package.json');

    if (isset($trackedFileSet[$composerManifestRelative])) {
        $composerManifest = loadJsonFromHead($root, $composerManifestRelative);
        $lockRelative = stackFileRelative($stackRelative, 'composer.lock');
        $lockOnDisk = is_file($stackDir . '/composer.lock');
        $lockInHead = isset($trackedFileSet[$lockRelative]);
        $stackSummaries[] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => $lockInHead ? 'composer.lock' : ($lockOnDisk ? 'composer.lock' : null), 'lockfile_tracked' => $lockInHead];
        if (!$lockInHead) {
            $rule = $lockOnDisk ? 'composer_lock_untracked' : 'composer_lock_missing';
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', $rule, 'high', $displayRoot . '/composer.json', 'composer', $lockOnDisk ? 'composer.lock exists locally or in the index but is absent from the reviewed HEAD tree.' : 'composer.json is in HEAD without composer.lock.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => $lockOnDisk ? 'composer.lock' : null, 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/composer.json', 'composer:' . $rule, 'License inventory is NOT EVALUATED because a committed composer.lock was not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => $lockOnDisk ? 'composer.lock' : null, 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/composer.json', 'composer:' . $rule, 'SCA is NOT EVALUATED because a committed composer.lock was not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
        } else {
            $lock = loadJsonFromHead($root, $lockRelative);
            if (!validComposerLock($lock, $composerManifest)) {
                $checks['lockfiles']['status'] = 'findings';
                addFinding($findings, 'lockfile', 'composer_lock_invalid_format', 'high', $displayRoot . '/composer.lock', 'composer', 'composer.lock is structurally invalid, truncated, or its locked versions do not satisfy composer.json/package requirements; reproducible dependency evidence is not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => 'composer.lock', 'status' => 'not_evaluated', 'packages_checked' => null];
                addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/composer.lock', 'composer:invalid-lock', 'License inventory is NOT EVALUATED because composer.lock is invalid, truncated, or mismatched.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => 'composer.lock', 'status' => 'not_evaluated'];
                addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/composer.lock', 'composer:invalid-lock', 'SCA is NOT EVALUATED because composer.lock is invalid, truncated, or mismatched.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            } else {
                $licenseCount = 0;
                foreach (composerPackagesForLicense($lock) as $package) {
                    $licenseCount++;
                    if ($package['licenses'] === [] && $reportMissingLicense) {
                        addFinding($findings, 'license', 'license_missing', 'medium', $displayRoot . '/composer.lock', $package['name'] . '@' . $package['version'], 'Dependency has no license metadata in lockfile; human/legal review required.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                    }
                    foreach ($package['licenses'] as $license) {
                        if (in_array($license, $deniedLicenses, true)) {
                            addFinding($findings, 'license', 'license_denied', 'high', $displayRoot . '/composer.lock', $package['name'] . '@' . $package['version'] . '|' . $license, 'Dependency license matches project deny policy; no universal legal conclusion is inferred.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                        }
                    }
                }
                $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'composer', 'status' => 'evaluated', 'packages_checked' => $licenseCount];
                $audit = null;
                $scaStatus = 'not_evaluated';
                $lockContent = headFileContent($root, $lockRelative);
                $auditFile = envValue('SUPPLY_CHAIN_COMPOSER_AUDIT_FILE');
                if ($auditFile !== null && $auditFile !== '') {
                    if ($composerStackCount === 1) {
                        $candidate = loadJsonFile($auditFile);
                        if (validComposerAudit($candidate)
                            && is_string($lockContent)
                            && auditBoundToLock($candidate, $lockContent)) {
                            $audit = $candidate;
                            $scaStatus = 'evidence_file';
                        }
                    }
                } elseif (!$disableExternalSca && commandExists('composer')) {
                    [$auditCode, $auditOut] = runHeadAudit(
                        $root,
                        $stackRelative,
                        ['composer.json', 'composer.lock'],
                        ['composer', 'audit', '--locked', '--format=json', '--no-interaction']
                    );
                    $decoded = json_decode($auditOut, true);
                    if (is_array($decoded) && validComposerAudit($decoded)) {
                        $audit = $decoded;
                        $scaStatus = $auditCode === 0 ? 'pass' : 'findings';
                    }
                }
                if ($audit === null) {
                    $scopeDetail = ($auditFile !== null && $auditFile !== '' && $composerStackCount > 1)
                        ? 'A single pre-generated Composer audit file cannot be attributed across multiple Composer stacks; SCA is NOT EVALUATED.'
                        : 'SCA is NOT EVALUATED for this locked stack; evidence was absent, invalid, not bound to the reviewed lock, or could not be executed against the reviewed HEAD. This is not a vulnerability finding and not a PASS.';
                    addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/composer.lock', 'composer', $scopeDetail, $level, $mode, $policy, $licensePolicy, $riskConfig);
                } else {
                    foreach (composerVulnerabilities($audit) as $vulnerability) {
                        addFinding($findings, 'sca', 'vulnerability', (string)$vulnerability['severity'], $displayRoot . '/composer.lock', (string)$vulnerability['package'] . '|' . (string)$vulnerability['advisory'], (string)$vulnerability['title'] . ((string)$vulnerability['url'] !== '' ? ' ' . (string)$vulnerability['url'] : ''), $level, $mode, $policy, $licensePolicy, $riskConfig);
                    }
                }
                $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'composer', 'status' => $audit === null ? 'not_evaluated' : $scaStatus];
            }
        }
    }

    if (isset($trackedFileSet[$nodeManifestRelative])) {
        $resolved = resolveNodeLock($root, $stackDir, $stackRelative, $trackedFileSet);
        $resolvedLockRelative = $resolved['lock'] !== null ? stackFileRelative($stackRelative, (string)$resolved['lock']) : null;
        $resolvedLockTracked = $resolvedLockRelative !== null && isset($trackedFileSet[$resolvedLockRelative]);
        $stackSummaries[] = ['root' => $displayRoot, 'stack' => 'node', 'package_manager' => $resolved['manager'], 'lockfile' => $resolved['lock'], 'lockfile_tracked' => $resolvedLockTracked];
        if ($resolved['error'] !== null) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', $resolved['error'], 'high', $displayRoot . '/package.json', 'node', 'Node lockfile is missing from HEAD, uncommitted, ambiguous, unsupported, or does not match packageManager.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $resolved['lock'], 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/package.json', 'node:' . $resolved['error'], 'License inventory is NOT EVALUATED because a usable committed Node lockfile was not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $resolved['lock'], 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/package.json', 'node:' . $resolved['error'], 'SCA is NOT EVALUATED because a usable committed Node lockfile was not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            continue;
        }
        $nodeLockName = (string)$resolved['lock'];
        $nodeLockRelative = stackFileRelative($stackRelative, $nodeLockName);
        if (!in_array($nodeLockName, ['package-lock.json', 'npm-shrinkwrap.json'], true)) {
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'License inventory is NOT EVALUATED for this lockfile; provide project-specific evidence.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'SCA is NOT EVALUATED for this lockfile; provide project-specific evidence.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            continue;
        }
        $lock = loadJsonFromHead($root, $nodeLockRelative);
        if (!validNpmLock($lock, $resolved['manifest'])) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', 'node_lock_invalid_format', 'high', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'npm lockfile format is unsupported, structurally invalid, truncated, or does not match package.json; reproducible dependency evidence is not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'License inventory is NOT EVALUATED because the npm lockfile is invalid, unsupported, truncated, or mismatched.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'SCA is NOT EVALUATED because the npm lockfile is invalid, unsupported, truncated, or mismatched.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            continue;
        }
        $licenseCount = 0;
        foreach (npmPackagesForLicense($lock) as $package) {
            $licenseCount++;
            if ($package['licenses'] === [] && $reportMissingLicense) {
                addFinding($findings, 'license', 'license_missing', 'medium', $displayRoot . '/' . $nodeLockName, $package['name'] . '@' . $package['version'], 'Dependency has no license metadata in lockfile; human/legal review required.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            }
            foreach ($package['licenses'] as $license) {
                if (in_array($license, $deniedLicenses, true)) {
                    addFinding($findings, 'license', 'license_denied', 'high', $displayRoot . '/' . $nodeLockName, $package['name'] . '@' . $package['version'] . '|' . $license, 'Dependency license matches project deny policy; no universal legal conclusion is inferred.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                }
            }
        }
        $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'status' => 'evaluated', 'packages_checked' => $licenseCount];
        $audit = null;
        $scaStatus = 'not_evaluated';
        $lockContent = headFileContent($root, $nodeLockRelative);
        $auditFile = envValue('SUPPLY_CHAIN_NPM_AUDIT_FILE');
        if ($auditFile !== null && $auditFile !== '') {
            if ($nodeStackCount === 1) {
                $candidate = loadJsonFile($auditFile);
                if (validNpmAudit($candidate)
                    && is_string($lockContent)
                    && auditBoundToLock($candidate, $lockContent)) {
                    $audit = $candidate;
                    $scaStatus = 'evidence_file';
                }
            }
        } elseif (!$disableExternalSca && commandExists('npm')) {
            [$auditCode, $auditOut] = runHeadAudit(
                $root,
                $stackRelative,
                ['package.json', $nodeLockName],
                ['npm', 'audit', '--package-lock-only', '--json']
            );
            $decoded = json_decode($auditOut, true);
            if (is_array($decoded) && validNpmAudit($decoded)) {
                $audit = $decoded;
                $scaStatus = $auditCode === 0 ? 'pass' : 'findings';
            }
        }
        if ($audit === null) {
            $scopeDetail = ($auditFile !== null && $auditFile !== '' && $nodeStackCount > 1)
                ? 'A single pre-generated npm audit file cannot be attributed across multiple Node stacks; SCA is NOT EVALUATED.'
                : 'SCA is NOT EVALUATED for this locked stack; evidence was absent, invalid, not bound to the reviewed lock, or could not be executed against the reviewed HEAD. This is not a vulnerability finding and not a PASS.';
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/' . $nodeLockName, 'node', $scopeDetail, $level, $mode, $policy, $licensePolicy, $riskConfig);
        } else {
            foreach (npmVulnerabilities($audit) as $vulnerability) {
                addFinding($findings, 'sca', 'vulnerability', (string)$vulnerability['severity'], $displayRoot . '/' . $nodeLockName, (string)$vulnerability['package'] . '|' . (string)$vulnerability['advisory'], (string)$vulnerability['title'] . ((string)$vulnerability['url'] !== '' ? ' ' . (string)$vulnerability['url'] : ''), $level, $mode, $policy, $licensePolicy, $riskConfig);
            }
        }
        $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'status' => $audit === null ? 'not_evaluated' : $scaStatus];
    }
}

usort($findings, static function (array $a, array $b): int {
    $severityCompare = severityRank((string)$b['severity']) <=> severityRank((string)$a['severity']);
    return $severityCompare !== 0 ? $severityCompare : strcmp((string)$a['id'], (string)$b['id']);
});
$potentialBlockers = count(array_filter($findings, static fn(array $finding): bool => (bool)$finding['policy_blocking'] && $finding['accepted_risk'] === null));
$enforcedBlockers = count(array_filter($findings, static fn(array $finding): bool => (bool)$finding['effective_blocking']));
$acceptedCount = count(array_filter($findings, static fn(array $finding): bool => $finding['accepted_risk'] !== null));
$notEvaluatedCount = count(array_filter($findings, static fn(array $finding): bool => in_array((string)$finding['rule'], ['sca_unavailable', 'license_not_evaluated'], true)));
if (($checks['secret_scan']['incomplete'] ?? false) === true) {
    $notEvaluatedCount++;
}
[$commitCode, $commitOut] = runCommand(['git', '-C', $root, 'rev-parse', 'HEAD'], $root);
$commit = $commitCode === 0 ? trim($commitOut) : 'unknown';
$report = [
    'schema' => 'hache-supply-chain-v1',
    'generated_at_utc' => gmdate('c'),
    'commit' => $commit,
    'mode' => $mode,
    'level' => $level,
    'stack_roots' => $stackSummaries,
    'checks' => $checks,
    'summary' => [
        'findings' => count($findings),
        'potential_blockers' => $potentialBlockers,
        'enforced_blockers' => $enforcedBlockers,
        'accepted_risks' => $acceptedCount,
        'not_evaluated' => $notEvaluatedCount,
        'evidence_complete' => $notEvaluatedCount === 0,
    ],
    'findings' => $findings,
];
$reportDir = dirname($reportFile);
if (!is_dir($reportDir) && !mkdir($reportDir, 0700, true) && !is_dir($reportDir)) {
    configError("cannot_create_report_dir path={$reportDir}");
}
$json = json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
if ($json === false || file_put_contents($reportFile, $json . "\n") === false) {
    configError("cannot_write_report path={$reportFile}");
}
printf(
    "SUPPLY_CHAIN_SUMMARY mode=%s level=%s findings=%d potential_blockers=%d enforced_blockers=%d accepted_risks=%d not_evaluated=%d evidence_complete=%d report=%s\n",
    $mode,
    $level,
    count($findings),
    $potentialBlockers,
    $enforcedBlockers,
    $acceptedCount,
    $notEvaluatedCount,
    $report['summary']['evidence_complete'] ? 1 : 0,
    $reportFile
);
foreach ($findings as $finding) {
    printf(
        "SUPPLY_CHAIN_FINDING id=%s category=%s severity=%s rule=%s location=%s policy_blocking=%d accepted=%d enforced=%d\n",
        $finding['id'],
        $finding['category'],
        $finding['severity'],
        $finding['rule'],
        str_replace(["\n", "\r", ' '], ['_', '_', '_'], (string)$finding['location']),
        $finding['policy_blocking'] ? 1 : 0,
        $finding['accepted_risk'] !== null ? 1 : 0,
        $finding['effective_blocking'] ? 1 : 0
    );
}
exit($enforcedBlockers > 0 ? 1 : 0);
