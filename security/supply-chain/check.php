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
function loadJsonFile(string $path, bool $required = true): array
{
    if (!is_file($path)) {
        if ($required) {
            configError("missing_json_file path={$path}");
        }
        return [];
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
    if (str_starts_with($relative, '/') || preg_match('~^[A-Za-z]:[\\\\/]~', $relative)) {
        configError("stack_root_must_be_relative value={$relative}");
    }
    $candidate = realpath($root . DIRECTORY_SEPARATOR . $relative);
    if ($candidate === false || ($candidate !== $root && !str_starts_with($candidate, $root . DIRECTORY_SEPARATOR))) {
        configError("invalid_stack_root value={$relative}");
    }
    return $candidate;
}

/** @return array<int,array{path:string,rule:string}> */
function loadSecretAllowlist(string $path): array
{
    if (!is_file($path)) {
        return [];
    }
    $rows = file($path, FILE_IGNORE_NEW_LINES);
    if ($rows === false) {
        configError("unreadable_secret_allowlist path={$path}");
    }
    $result = [];
    foreach ($rows as $row) {
        $row = trim($row);
        if ($row === '' || str_starts_with($row, '#')) {
            continue;
        }
        $parts = preg_split('/\s+/', $row, 2);
        if (!is_array($parts) || count($parts) !== 2) {
            configError("invalid_secret_allowlist_row value={$row}");
        }
        $result[] = ['path' => $parts[0], 'rule' => $parts[1]];
    }
    return $result;
}

/** @param array<int,array{path:string,rule:string}> $allowlist */
function secretAllowed(array $allowlist, string $path, string $rule): bool
{
    foreach ($allowlist as $entry) {
        if ($entry['rule'] !== $rule && $entry['rule'] !== '*') {
            continue;
        }
        if (fnmatch($entry['path'], $path, FNM_PATHNAME)) {
            return true;
        }
    }
    return false;
}

function findingId(string $category, string $rule, string $location, string $subject): string
{
    return substr(hash('sha256', implode('|', [$category, $rule, $location, $subject])), 0, 20);
}

/** @param array<string,mixed> $licensePolicy */
function policyBlocks(string $category, string $rule, string $severity, string $level, array $licensePolicy): bool
{
    if ($category === 'secret' || $category === 'lockfile') {
        return true;
    }
    if ($category === 'sca') {
        if (!in_array($level, ['B', 'C'], true)) {
            return false;
        }
        return in_array($severity, ['critical', 'high'], true) || $rule === 'sca_unavailable';
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
        if (!is_array($entry) || (string)($entry['finding_id'] ?? '') !== $findingId) {
            continue;
        }
        foreach (['owner', 'approval_ref', 'mitigation', 'expires_at'] as $field) {
            if (trim((string)($entry[$field] ?? '')) === '') {
                return null;
            }
        }
        $expires = strtotime((string)$entry['expires_at'] . ' 23:59:59 UTC');
        if ($expires === false || $expires < time()) {
            return null;
        }
        return [
            'owner' => (string)$entry['owner'],
            'approval_ref' => (string)$entry['approval_ref'],
            'mitigation' => (string)$entry['mitigation'],
            'expires_at' => (string)$entry['expires_at'],
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
    $accepted = acceptedRiskFor($id, $riskConfig);
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

/** @return array<int,string> */
function trackedFiles(string $root): array
{
    [$code, $out, $err] = runCommand(['git', '-C', $root, 'ls-files', '-z'], $root);
    if ($code !== 0) {
        configError('git_ls_files_failed ' . trim($err));
    }
    return array_values(array_filter(explode("\0", $out), static fn(string $v): bool => $v !== ''));
}

function isProbablyBinary(string $content): bool
{
    return str_contains(substr($content, 0, 8192), "\0");
}

/** @return array<int,array<string,mixed>> */
function npmVulnerabilities(array $audit): array
{
    $result = [];
    $vulnerabilities = $audit['vulnerabilities'] ?? null;
    if (!is_array($vulnerabilities)) {
        return $result;
    }
    foreach ($vulnerabilities as $package => $data) {
        if (!is_array($data)) {
            continue;
        }
        $severity = normalizeSeverity((string)($data['severity'] ?? 'unknown'));
        $advisory = 'npm:' . $package;
        $title = 'npm audit finding';
        $url = '';
        $via = $data['via'] ?? [];
        if (is_array($via)) {
            foreach ($via as $entry) {
                if (is_array($entry)) {
                    if (isset($entry['source'])) {
                        $advisory = 'npm:' . (string)$entry['source'];
                    }
                    $title = (string)($entry['title'] ?? $title);
                    $url = (string)($entry['url'] ?? $url);
                    $entrySeverity = normalizeSeverity((string)($entry['severity'] ?? 'unknown'));
                    if (severityRank($entrySeverity) > severityRank($severity)) {
                        $severity = $entrySeverity;
                    }
                    break;
                }
            }
        }
        $result[] = ['package' => (string)$package, 'severity' => $severity, 'advisory' => $advisory, 'title' => $title, 'url' => $url];
    }
    return $result;
}

/** @return array<int,array<string,mixed>> */
function composerVulnerabilities(array $audit): array
{
    $result = [];
    $advisories = $audit['advisories'] ?? null;
    if (!is_array($advisories)) {
        return $result;
    }
    foreach ($advisories as $package => $items) {
        if (!is_array($items)) {
            continue;
        }
        foreach ($items as $entry) {
            if (!is_array($entry)) {
                continue;
            }
            $result[] = [
                'package' => (string)($entry['packageName'] ?? $package),
                'severity' => normalizeSeverity((string)($entry['severity'] ?? 'unknown')),
                'advisory' => (string)($entry['advisoryId'] ?? $entry['cve'] ?? ('composer:' . $package)),
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
    $packages = $lock['packages'] ?? null;
    if (!is_array($packages)) {
        return $result;
    }
    foreach ($packages as $path => $data) {
        if ($path === '' || !is_array($data)) {
            continue;
        }
        $name = (string)($data['name'] ?? basename((string)$path));
        $version = (string)($data['version'] ?? 'unknown');
        $license = $data['license'] ?? null;
        $licenses = [];
        if (is_string($license) && trim($license) !== '') {
            $licenses[] = trim($license);
        } elseif (is_array($license)) {
            foreach ($license as $item) {
                if (is_string($item) && trim($item) !== '') {
                    $licenses[] = trim($item);
                }
            }
        }
        $result[] = ['name' => $name, 'version' => $version, 'licenses' => array_values(array_unique($licenses))];
    }
    return $result;
}

/** @return array<int,array{name:string,version:string,licenses:array<int,string>}> */
function composerPackagesForLicense(array $lock): array
{
    $result = [];
    foreach (['packages', 'packages-dev'] as $section) {
        $packages = $lock[$section] ?? [];
        if (!is_array($packages)) {
            continue;
        }
        foreach ($packages as $data) {
            if (!is_array($data)) {
                continue;
            }
            $licenses = [];
            foreach (($data['license'] ?? []) as $item) {
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
$policyPath = (string)envValue('SUPPLY_CHAIN_POLICY_FILE', $root . '/security/supply-chain/policy.json');
$licensePolicyPath = (string)envValue('SUPPLY_CHAIN_LICENSE_POLICY_FILE', $root . '/security/supply-chain/license-policy.json');
$riskPath = (string)envValue('SUPPLY_CHAIN_ACCEPTED_RISK_FILE', $root . '/security/supply-chain/accepted-risk.json');
$allowlistPath = (string)envValue('SUPPLY_CHAIN_SECRET_ALLOWLIST_FILE', $root . '/security/supply-chain/secret-scan.allowlist');
$reportFile = (string)envValue('SUPPLY_CHAIN_REPORT_FILE', sys_get_temp_dir() . '/hache-supply-chain-report.json');
$disableExternalSca = envValue('SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA', '0') === '1';

$policy = loadJsonFile($policyPath);
$licensePolicy = loadJsonFile($licensePolicyPath);
$riskConfig = loadJsonFile($riskPath);
$allowlist = loadSecretAllowlist($allowlistPath);
$findings = [];
$checks = [
    'secret_scan' => ['status' => 'pass', 'scope' => 'tracked_current_tree'],
    'lockfiles' => ['status' => 'pass'],
    'sca' => [],
    'licenses' => [],
];

$secretRules = [
    'private_key' => '~-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----~',
    'aws_access_key' => '~\bAKIA[0-9A-Z]{16}\b~',
    'github_token' => '~\bgh[pousr]_[A-Za-z0-9]{20,}\b~',
    'slack_token' => '~\bxox[baprs]-[A-Za-z0-9-]{20,}\b~',
    'openai_key' => '~\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b~',
    'stripe_live_secret' => '~\bsk_live_[A-Za-z0-9]{16,}\b~',
    'google_api_key' => '~\bAIza[0-9A-Za-z_-]{30,}\b~',
];
foreach (trackedFiles($root) as $relativePath) {
    $fullPath = $root . DIRECTORY_SEPARATOR . $relativePath;
    if (!is_file($fullPath) || filesize($fullPath) > 2 * 1024 * 1024) {
        continue;
    }
    $content = file_get_contents($fullPath);
    if ($content === false || isProbablyBinary($content)) {
        continue;
    }
    $lines = preg_split('/\R/', $content);
    if (!is_array($lines)) {
        continue;
    }
    foreach ($lines as $index => $line) {
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
                $relativePath . ':' . ($index + 1),
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
}

$stackRootsRaw = trim((string)envValue('SUPPLY_CHAIN_STACK_ROOTS', '.'));
$stackRoots = array_values(array_unique(array_filter(array_map('trim', explode(',', $stackRootsRaw)), static fn(string $v): bool => $v !== '')));
if ($stackRoots === []) {
    $stackRoots = ['.'];
}
$stackSummaries = [];
foreach ($stackRoots as $stackRelative) {
    $stackDir = withinRoot($root, $stackRelative);
    $displayRoot = $stackRelative === '.' ? '.' : rtrim($stackRelative, '/');
    $composerManifest = $stackDir . '/composer.json';
    $composerLock = $stackDir . '/composer.lock';
    $nodeManifest = $stackDir . '/package.json';
    $nodeLocks = ['package-lock.json', 'npm-shrinkwrap.json', 'pnpm-lock.yaml', 'yarn.lock'];

    if (is_file($composerManifest)) {
        $stackSummaries[] = ['root' => $displayRoot, 'stack' => 'composer', 'lockfile' => is_file($composerLock) ? 'composer.lock' : null];
        if (!is_file($composerLock)) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', 'composer_lock_missing', 'high', $displayRoot . '/composer.json', 'composer', 'composer.json is tracked without composer.lock.', $level, $mode, $policy, $licensePolicy, $riskConfig);
        } else {
            $composerLockJson = loadJsonFile($composerLock);
            $denied = array_map('strval', is_array($licensePolicy['denied'] ?? null) ? $licensePolicy['denied'] : []);
            $reportMissing = (bool)($licensePolicy['report_missing'] ?? true);
            $licenseCount = 0;
            foreach (composerPackagesForLicense($composerLockJson) as $package) {
                $licenseCount++;
                if ($package['licenses'] === [] && $reportMissing) {
                    addFinding($findings, 'license', 'license_missing', 'medium', $displayRoot . '/composer.lock', $package['name'] . '@' . $package['version'], 'Dependency has no license metadata in lockfile; human/legal review required.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                }
                foreach ($package['licenses'] as $license) {
                    if (in_array($license, $denied, true)) {
                        addFinding($findings, 'license', 'license_denied', 'high', $displayRoot . '/composer.lock', $package['name'] . '@' . $package['version'] . '|' . $license, 'Dependency license matches project deny policy; no legal conclusion is inferred beyond the configured policy.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                    }
                }
            }
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'composer', 'packages_checked' => $licenseCount];

            $auditFile = envValue('SUPPLY_CHAIN_COMPOSER_AUDIT_FILE');
            $audit = null;
            $scaStatus = 'not_evaluated';
            if ($auditFile !== null && $auditFile !== '') {
                $audit = loadJsonFile($auditFile);
                $scaStatus = 'fixture';
            } elseif (!$disableExternalSca && commandExists('composer')) {
                [$auditCode, $auditOut] = runCommand(['composer', 'audit', '--locked', '--format=json', '--no-interaction'], $stackDir);
                $decoded = json_decode($auditOut, true);
                if (is_array($decoded)) {
                    $audit = $decoded;
                    $scaStatus = $auditCode === 0 ? 'pass' : 'findings';
                } else {
                    $scaStatus = 'unavailable';
                }
            } else {
                $scaStatus = 'unavailable';
            }
            if ($audit === null) {
                addFinding($findings, 'sca', 'sca_unavailable', 'high', $displayRoot . '/composer.lock', 'composer', 'SCA was not evaluated for this locked stack; do not treat this as PASS.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            } else {
                foreach (composerVulnerabilities($audit) as $vulnerability) {
                    addFinding($findings, 'sca', 'vulnerability', (string)$vulnerability['severity'], $displayRoot . '/composer.lock', (string)$vulnerability['package'] . '|' . (string)$vulnerability['advisory'], (string)$vulnerability['title'] . ((string)$vulnerability['url'] !== '' ? ' ' . (string)$vulnerability['url'] : ''), $level, $mode, $policy, $licensePolicy, $riskConfig);
                }
            }
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'composer', 'status' => $scaStatus];
        }
    }

    if (is_file($nodeManifest)) {
        $nodeLockName = null;
        foreach ($nodeLocks as $candidate) {
            if (is_file($stackDir . '/' . $candidate)) {
                $nodeLockName = $candidate;
                break;
            }
        }
        $stackSummaries[] = ['root' => $displayRoot, 'stack' => 'node', 'lockfile' => $nodeLockName];
        if ($nodeLockName === null) {
            $checks['lockfiles']['status'] = 'findings';
            addFinding($findings, 'lockfile', 'node_lock_missing', 'high', $displayRoot . '/package.json', 'node', 'package.json is tracked without a supported lockfile in the same stack root.', $level, $mode, $policy, $licensePolicy, $riskConfig);
        } elseif (in_array($nodeLockName, ['package-lock.json', 'npm-shrinkwrap.json'], true)) {
            $nodeLockPath = $stackDir . '/' . $nodeLockName;
            $nodeLockJson = loadJsonFile($nodeLockPath);
            $denied = array_map('strval', is_array($licensePolicy['denied'] ?? null) ? $licensePolicy['denied'] : []);
            $reportMissing = (bool)($licensePolicy['report_missing'] ?? true);
            $licenseCount = 0;
            foreach (npmPackagesForLicense($nodeLockJson) as $package) {
                $licenseCount++;
                if ($package['licenses'] === [] && $reportMissing) {
                    addFinding($findings, 'license', 'license_missing', 'medium', $displayRoot . '/' . $nodeLockName, $package['name'] . '@' . $package['version'], 'Dependency has no license metadata in lockfile; human/legal review required.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                }
                foreach ($package['licenses'] as $license) {
                    if (in_array($license, $denied, true)) {
                        addFinding($findings, 'license', 'license_denied', 'high', $displayRoot . '/' . $nodeLockName, $package['name'] . '@' . $package['version'] . '|' . $license, 'Dependency license matches project deny policy; no legal conclusion is inferred beyond the configured policy.', $level, $mode, $policy, $licensePolicy, $riskConfig);
                    }
                }
            }
            $checks['licenses'][] = ['root' => $displayRoot, 'stack' => 'node', 'packages_checked' => $licenseCount];

            $auditFile = envValue('SUPPLY_CHAIN_NPM_AUDIT_FILE');
            $audit = null;
            $scaStatus = 'not_evaluated';
            if ($auditFile !== null && $auditFile !== '') {
                $audit = loadJsonFile($auditFile);
                $scaStatus = 'fixture';
            } elseif (!$disableExternalSca && commandExists('npm')) {
                [$auditCode, $auditOut] = runCommand(['npm', 'audit', '--package-lock-only', '--json'], $stackDir);
                $decoded = json_decode($auditOut, true);
                if (is_array($decoded) && !isset($decoded['error'])) {
                    $audit = $decoded;
                    $scaStatus = $auditCode === 0 ? 'pass' : 'findings';
                } else {
                    $scaStatus = 'unavailable';
                }
            } else {
                $scaStatus = 'unavailable';
            }
            if ($audit === null) {
                addFinding($findings, 'sca', 'sca_unavailable', 'high', $displayRoot . '/' . $nodeLockName, 'node', 'SCA was not evaluated for this locked stack; do not treat this as PASS.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            } else {
                foreach (npmVulnerabilities($audit) as $vulnerability) {
                    addFinding($findings, 'sca', 'vulnerability', (string)$vulnerability['severity'], $displayRoot . '/' . $nodeLockName, (string)$vulnerability['package'] . '|' . (string)$vulnerability['advisory'], (string)$vulnerability['title'] . ((string)$vulnerability['url'] !== '' ? ' ' . (string)$vulnerability['url'] : ''), $level, $mode, $policy, $licensePolicy, $riskConfig);
                }
            }
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'status' => $scaStatus];
        } else {
            addFinding($findings, 'sca', 'sca_unavailable', 'high', $displayRoot . '/' . $nodeLockName, 'node:' . $nodeLockName, 'This baseline records the lockfile but has no built-in SCA parser for this Node lockfile. Provide project-specific SCA evidence; do not treat this as PASS.', $level, $mode, $policy, $licensePolicy, $riskConfig);
            $checks['sca'][] = ['root' => $displayRoot, 'stack' => 'node', 'status' => 'not_evaluated', 'lockfile' => $nodeLockName];
        }
    }
}

usort($findings, static function (array $a, array $b): int {
    $severityCompare = severityRank((string)$b['severity']) <=> severityRank((string)$a['severity']);
    return $severityCompare !== 0 ? $severityCompare : strcmp((string)$a['id'], (string)$b['id']);
});
$potentialBlockers = count(array_filter($findings, static fn(array $f): bool => (bool)$f['policy_blocking'] && $f['accepted_risk'] === null));
$enforcedBlockers = count(array_filter($findings, static fn(array $f): bool => (bool)$f['effective_blocking']));
$acceptedCount = count(array_filter($findings, static fn(array $f): bool => $f['accepted_risk'] !== null));
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
    "SUPPLY_CHAIN_SUMMARY mode=%s level=%s findings=%d potential_blockers=%d enforced_blockers=%d accepted_risks=%d report=%s\n",
    $mode,
    $level,
    count($findings),
    $potentialBlockers,
    $enforcedBlockers,
    $acceptedCount,
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
