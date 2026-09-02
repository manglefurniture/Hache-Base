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

/** @return array<int,string> */
function trackedFiles(string $root): array
{
    [$code, $out, $err] = runCommand(['git', '-C', $root, 'ls-files', '-z'], $root);
    if ($code !== 0) {
        configError('git_ls_files_failed ' . trim($err));
    }
    return array_values(array_filter(explode("\0", $out), static fn(string $value): bool => $value !== ''));
}

function findingId(string $category, string $rule, string $location, string $subject): string
{
    return substr(hash('sha256', implode('|', [$category, $rule, $location, $subject])), 0, 20);
}

/** @return array<int,array{path:string,rule:string}> */
function loadSecretAllowlist(string $path, array $knownRules): array
{
    if (!is_file($path)) {
        return [];
    }
    $rows = file($path, FILE_IGNORE_NEW_LINES);
    if ($rows === false) {
        configError("unreadable_secret_allowlist path={$path}");
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
        if (isset($data['license'])) {
            if (is_string($data['license'])) {
                continue;
            }
            if (!is_array($data['license'])) {
                return false;
            }
            foreach ($data['license'] as $license) {
                if (!is_string($license)) {
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
    if (!array_key_exists('packages', $lock)
        || !is_array($lock['packages'])
        || !array_key_exists('packages-dev', $lock)
        || !is_array($lock['packages-dev'])) {
        return false;
    }

    $prodNames = [];
    $devNames = [];
    foreach ([['packages', &$prodNames], ['packages-dev', &$devNames]] as &$sectionConfig) {
        [$section, &$names] = $sectionConfig;
        foreach ($lock[$section] as $package) {
            if (!is_array($package)
                || !isset($package['name'], $package['version'])
                || !is_string($package['name'])
                || trim($package['name']) === ''
                || !is_string($package['version'])
                || trim($package['version']) === '') {
                return false;
            }
            $names[$package['name']] = true;
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
        }
    }
    unset($sectionConfig, $names);

    foreach (['require', 'require-dev'] as $section) {
        $requirements = $manifest[$section] ?? [];
        if (!is_array($requirements)) {
            return false;
        }
        foreach ($requirements as $name => $constraint) {
            if (!is_string($name)
                || trim($name) === ''
                || !is_string($constraint)
                || trim($constraint) === '') {
                return false;
            }
            if (composerPlatformRequirement($name)) {
                continue;
            }
            $present = isset($prodNames[$name]) || ($section === 'require-dev' && isset($devNames[$name]));
            if (!$present) {
                return false;
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
function resolveNodeLock(string $stackDir): array
{
    $manifest = loadJsonFile($stackDir . '/package.json');
    $declared = trim((string)($manifest['packageManager'] ?? ''));
    $manager = null;
    if ($declared !== '') {
        if (preg_match('/^(npm|yarn|pnpm)@/', $declared, $matches) !== 1) {
            return ['manager' => null, 'lock' => null, 'error' => 'unsupported_package_manager', 'manifest' => $manifest];
        }
        $manager = $matches[1];
    }
    $allLocks = [];
    foreach (['package-lock.json', 'npm-shrinkwrap.json', 'yarn.lock', 'pnpm-lock.yaml'] as $candidate) {
        if (is_file($stackDir . '/' . $candidate)) {
            $allLocks[] = $candidate;
        }
    }
    if (count($allLocks) > 1) {
        return ['manager' => $manager, 'lock' => null, 'error' => 'ambiguous_node_lockfiles', 'manifest' => $manifest];
    }
    if ($allLocks === []) {
        return ['manager' => $manager, 'lock' => null, 'error' => 'node_lock_missing', 'manifest' => $manifest];
    }
    $lock = $allLocks[0];
    $expected = match ($manager) {
        'npm' => ['package-lock.json', 'npm-shrinkwrap.json'],
        'yarn' => ['yarn.lock'],
        'pnpm' => ['pnpm-lock.yaml'],
        default => ['package-lock.json', 'npm-shrinkwrap.json', 'yarn.lock', 'pnpm-lock.yaml'],
    };
    if (!in_array($lock, $expected, true)) {
        return ['manager' => $manager, 'lock' => $lock, 'error' => 'node_lock_manager_mismatch', 'manifest' => $manifest];
    }
    return ['manager' => $manager, 'lock' => $lock, 'error' => null, 'manifest' => $manifest];
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
    'github_token' => '~\bgh[pousr]_[A-Za-z0-9]{20,}\b~',
    'slack_token' => '~\bxox[baprs]-[A-Za-z0-9-]{20,}\b~',
    'openai_key' => '~\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b~',
    'stripe_live_secret' => '~\bsk_live_[A-Za-z0-9]{16,}\b~',
    'google_api_key' => '~\bAIza[0-9A-Za-z_-]{30,}\b~',
];
$allowlist = loadSecretAllowlist(
    (string)envValue('SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE', $root . '/security/supply-chain/secret-scan.allowlist'),
    $secretRules
);
$findings = [];
$checks = [
    'secret_scan' => ['status' => 'pass', 'scope' => 'tracked_text_tree', 'binary_skipped' => 0, 'incomplete' => false],
    'lockfiles' => ['status' => 'pass'],
    'sca' => [],
    'licenses' => [],
];

foreach (trackedFiles($root) as $relativePath) {
    $fullPath = $root . DIRECTORY_SEPARATOR . $relativePath;
    if (!is_file($fullPath)) {
        continue;
    }
    $handle = fopen($fullPath, 'rb');
    if ($handle === false) {
        $checks['secret_scan']['status'] = 'not_evaluated';
        $checks['secret_scan']['incomplete'] = true;
        $checks['secret_scan']['unreadable'][] = $relativePath;
        continue;
    }
    $prefix = fread($handle, 8192);
    if ($prefix === false) {
        fclose($handle);
        $checks['secret_scan']['status'] = 'not_evaluated';
        $checks['secret_scan']['incomplete'] = true;
        $checks['secret_scan']['unreadable'][] = $relativePath;
        continue;
    }
    if (str_contains($prefix, "\0")) {
        fclose($handle);
        $checks['secret_scan']['binary_skipped']++;
        continue;
    }
    rewind($handle);
    $lineNumber = 0;
    while (($line = fgets($handle)) !== false) {
        $lineNumber++;
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
    fclose($handle);
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
    $stackDir = withinRoot($root, $stackRelative);
    if (is_file($stackDir . '/composer.json')) {
        $composerStackCount++;
    }
    if (is_file($stackDir . '/package.json')) {
        $nodeStackCount++;
    }
}

foreach ($stackRoots as $stackRelative) {
    $stackDir = withinRoot($root, $stackRelative);
    $displayRoot = $stackRelative === '.' ? '.' : rtrim($stackRelative, '/');

    if (is_file($stackDir . '/composer.json')) {
        $composerManifest = loadJsonFile($stackDir . '/composer.json');
        $lockPath = $stackDir . '/composer.lock';
        $stackSummaries[] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => is_file($lockPath) ? 'composer.lock' : null];
        if (!is_file($lockPath)) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', 'composer_lock_missing', 'high', $displayRoot . '/composer.json', 'composer', 'composer.json is tracked without composer.lock.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => null, 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/composer.json', 'composer:missing-lock', 'License inventory is NOT EVALUATED because composer.lock is missing.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => null, 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/composer.json', 'composer:missing-lock', 'SCA is NOT EVALUATED because composer.lock is missing.', $level, $mode, $policy, $licensePolicy, $riskConfig);
        } else {
            $lock = loadJsonFile($lockPath);
            if (!validComposerLock($lock, $composerManifest)) {
                $checks['lockfiles']['status'] = 'findings';
                addFinding($findings, 'lockfile', 'composer_lock_invalid_format', 'high', $displayRoot . '/composer.lock', 'composer', 'composer.lock is structurally invalid or does not cover direct non-platform requirements from composer.json; reproducible dependency evidence is not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => 'composer.lock', 'status' => 'not_evaluated', 'packages_checked' => null];
                addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/composer.lock', 'composer:invalid-lock', 'License inventory is NOT EVALUATED because composer.lock is invalid or mismatched to composer.json.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => 'composer.lock', 'status' => 'not_evaluated'];
                addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/composer.lock', 'composer:invalid-lock', 'SCA is NOT EVALUATED because composer.lock is invalid or mismatched to composer.json.', $level, $mode, $policy, $licensePolicy, $riskConfig);
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
                $auditFile = envValue('SUPPLY_CHAIN_COMPOSER_AUDIT_FILE');
                if ($auditFile !== null && $auditFile !== '') {
                    if ($composerStackCount === 1) {
                        $candidate = loadJsonFile($auditFile);
                        if (validComposerAudit($candidate)) {
                            $audit = $candidate;
                            $scaStatus = 'evidence_file';
                        }
                    }
                } elseif (!$disableExternalSca && commandExists('composer')) {
                    [$auditCode, $auditOut] = runCommand(['composer', 'audit', '--locked', '--format=json', '--no-interaction'], $stackDir);
                    $decoded = json_decode($auditOut, true);
                    if (is_array($decoded) && validComposerAudit($decoded)) {
                        $audit = $decoded;
                        $scaStatus = $auditCode === 0 ? 'pass' : 'findings';
                    }
                }
                if ($audit === null) {
                    $scopeDetail = ($auditFile !== null && $auditFile !== '' && $composerStackCount > 1)
                        ? 'A single pre-generated Composer audit file cannot be attributed across multiple Composer stacks; SCA is NOT EVALUATED. Split the invocation or run Composer audit per stack.'
                        : 'SCA is NOT EVALUATED for this locked stack; evidence was absent or invalid. This is not a vulnerability finding and not a PASS.';
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

    if (is_file($stackDir . '/package.json')) {
        $resolved = resolveNodeLock($stackDir);
        $stackSummaries[] = ['root' => $displayRoot, 'stack' => 'node', 'package_manager' => $resolved['manager'], 'lockfile' => $resolved['lock']];
        if ($resolved['error'] !== null) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', $resolved['error'], 'high', $displayRoot . '/package.json', 'node', 'Node lockfile is missing, ambiguous, unsupported, or does not match packageManager.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $resolved['lock'], 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/package.json', 'node:' . $resolved['error'], 'License inventory is NOT EVALUATED because a usable Node lockfile was not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $resolved['lock'], 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/package.json', 'node:' . $resolved['error'], 'SCA is NOT EVALUATED because a usable Node lockfile was not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            continue;
        }

        $nodeLockName = (string)$resolved['lock'];
        if (!in_array($nodeLockName, ['package-lock.json', 'npm-shrinkwrap.json'], true)) {
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'License inventory is NOT EVALUATED for this lockfile; provide project-specific evidence.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'SCA is NOT EVALUATED for this lockfile; provide project-specific evidence.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            continue;
        }

        $nodeLockPath = $stackDir . '/' . $nodeLockName;
        $lock = loadJsonFile($nodeLockPath);
        if (!validNpmLock($lock, $resolved['manifest'])) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', 'node_lock_invalid_format', 'high', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'npm lockfile format is unsupported, structurally invalid, or does not match the manifest dependency sets; reproducible dependency evidence is not established.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated', 'packages_checked' => null];
            addFinding($findings, 'license', 'license_not_evaluated', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'License inventory is NOT EVALUATED because the npm lockfile format is invalid, unsupported, or mismatched to package.json.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName, 'status' => 'not_evaluated'];
            addFinding($findings, 'sca', 'sca_unavailable', 'unknown', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'SCA is NOT EVALUATED because the npm lockfile format is invalid, unsupported, or mismatched to package.json.', $level, $mode, $policy, $licensePolicy, $riskConfig);
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
        $auditFile = envValue('SUPPLY_CHAIN_NPM_AUDIT_FILE');
        if ($auditFile !== null && $auditFile !== '') {
            if ($nodeStackCount === 1) {
                $candidate = loadJsonFile($auditFile);
                if (validNpmAudit($candidate)) {
                    $audit = $candidate;
                    $scaStatus = 'evidence_file';
                }
            }
        } elseif (!$disableExternalSca && commandExists('npm')) {
            [$auditCode, $auditOut] = runCommand(['npm', 'audit', '--package-lock-only', '--json'], $stackDir);
            $decoded = json_decode($auditOut, true);
            if (is_array($decoded) && validNpmAudit($decoded)) {
                $audit = $decoded;
                $scaStatus = $auditCode === 0 ? 'pass' : 'findings';
            }
        }
        if ($audit === null) {
            $scopeDetail = ($auditFile !== null && $auditFile !== '' && $nodeStackCount > 1)
                ? 'A single pre-generated npm audit file cannot be attributed across multiple Node stacks; SCA is NOT EVALUATED. Split the invocation or run npm audit per stack.'
                : 'SCA is NOT EVALUATED for this locked stack; evidence was absent or invalid. This is not a vulnerability finding and not a PASS.';
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