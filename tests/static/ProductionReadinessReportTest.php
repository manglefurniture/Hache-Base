<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$reporter = $root . '/tools/production-readiness/report.php';
$tmp = sys_get_temp_dir() . '/hache-readiness-report-' . bin2hex(random_bytes(6));
assert(mkdir($tmp, 0700, true));

register_shutdown_function(static function () use ($tmp): void {
    if (!is_dir($tmp)) {
        return;
    }
    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($tmp, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($iterator as $item) {
        if ($item->isDir()) {
            @rmdir($item->getPathname());
        } else {
            @unlink($item->getPathname());
        }
    }
    @rmdir($tmp);
});

/** @return array{int,string,string} */
function runReadinessReport(string $reporter, array $args): array
{
    $command = array_merge([PHP_BINARY, $reporter], $args);
    $spec = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $process = proc_open($command, $spec, $pipes);
    assert(is_resource($process));
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $rc = proc_close($process);
    return [$rc, is_string($stdout) ? $stdout : '', is_string($stderr) ? $stderr : ''];
}

/** @return array<string,array<string,mixed>> */
function controlsById(array $report): array
{
    $map = [];
    foreach ($report['controls'] as $control) {
        $map[$control['id']] = $control;
    }
    return $map;
}

[$rcA, $stdoutA, $stderrA] = runReadinessReport($reporter, ['--level', 'A']);
assert($rcA === 0, $stderrA);
$reportA = json_decode($stdoutA, true, 512, JSON_THROW_ON_ERROR);
assert($reportA['schema_version'] === 1);
assert($reportA['level'] === 'A');
assert($reportA['source']['standard'] === 'docs/production-readiness/PRODUCTION-READINESS-STANDARD.md');
assert($reportA['source']['canonical_control_count'] === 126);
assert($reportA['summary']['applicable_controls'] + $reportA['summary']['out_of_level_controls'] === 126);
assert($reportA['decision'] === 'NOT_A_PRODUCTION_READY_DECLARATION');
assert($reportA['summary']['blocking_or_required_unresolved'] > 0);
$controlsA = controlsById($reportA);
assert(count($controlsA) === 126);
assert($controlsA['A11Y-002']['scope'] === 'applicable');
assert($controlsA['A11Y-002']['effective_severity'] === 'REQUIRED');
assert($controlsA['SEC-003']['effective_severity'] === 'RECOMMENDED');
assert($controlsA['SEC-004']['scope'] === 'out_of_level');
assert($controlsA['DEP-006']['scope'] === 'out_of_level');
assert($controlsA['DPL-001']['effective_severity'] === 'BLOCKER');
foreach ($controlsA as $control) {
    if ($control['scope'] === 'applicable') {
        assert($control['evaluation']['state'] === 'NOT EVALUATED');
    } else {
        assert($control['evaluation'] === null);
    }
}

[$rcB, $stdoutB, $stderrB] = runReadinessReport($reporter, ['--level', 'B']);
assert($rcB === 0, $stderrB);
$reportB = json_decode($stdoutB, true, 512, JSON_THROW_ON_ERROR);
$controlsB = controlsById($reportB);
assert($controlsB['A11Y-002']['effective_severity'] === 'BLOCKER');
assert($controlsB['SEC-003']['effective_severity'] === 'REQUIRED');
assert($controlsB['SEC-008']['effective_severity'] === 'REQUIRED');
assert($controlsB['ROB-005']['scope'] === 'out_of_level');

[$rcC, $stdoutC, $stderrC] = runReadinessReport($reporter, ['--level', 'C']);
assert($rcC === 0, $stderrC);
$reportC = json_decode($stdoutC, true, 512, JSON_THROW_ON_ERROR);
$controlsC = controlsById($reportC);
assert($controlsC['SEC-008']['effective_severity'] === 'BLOCKER');
assert($controlsC['ROB-005']['effective_severity'] === 'BLOCKER');
assert($controlsC['DEP-006']['effective_severity'] === 'RECOMMENDED');
assert($controlsC['DPL-007']['effective_severity'] === 'REQUIRED');

$validEvidence = $tmp . '/valid-evidence.json';
file_put_contents($validEvidence, json_encode([
    'project' => ['name' => 'fixture', 'environment' => 'staging', 'commit' => 'abc123'],
    'controls' => [
        'GOV-001' => [
            'state' => 'PASS',
            'evidence' => ['docs/project-profile.md'],
            'note' => 'Perfil aprobado para el fixture. regex \\| fallback.',
            'reviewed_by' => 'fixture-reviewer',
            'reviewed_at' => '2026-09-04',
        ],
        'PERF-001' => [
            'state' => 'N/A',
            'justification' => 'No existe todavía tráfico de campo suficiente; se usa PERF-002.',
            'evidence' => ['reports/lab-baseline.md'],
            'reviewed_by' => 'fixture-reviewer',
            'reviewed_at' => '2026-09-04',
        ],
    ],
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

$jsonPath = $tmp . '/report.json';
$markdownPath = $tmp . '/report.md';
[$rcEvidence, $stdoutEvidence, $stderrEvidence] = runReadinessReport($reporter, [
    '--level', 'A',
    '--evidence', $validEvidence,
    '--json', $jsonPath,
    '--markdown', $markdownPath,
]);
assert($rcEvidence === 0, $stderrEvidence);
assert($stdoutEvidence === '');
$reportEvidence = json_decode((string) file_get_contents($jsonPath), true, 512, JSON_THROW_ON_ERROR);
$controlsEvidence = controlsById($reportEvidence);
assert($controlsEvidence['GOV-001']['evaluation']['state'] === 'PASS');
assert($controlsEvidence['GOV-001']['evaluation']['reviewed_by'] === 'fixture-reviewer');
assert($controlsEvidence['PERF-001']['evaluation']['state'] === 'N/A');
assert($controlsEvidence['GOV-002']['evaluation']['state'] === 'NOT EVALUATED');
$markdown = (string) file_get_contents($markdownPath);
assert(str_contains($markdown, 'No es una declaración de Production Ready'));
assert(str_contains($markdown, 'Standard SHA-256'));
assert(str_contains($markdown, '| GOV-001 | BLOCKER |'));
assert(str_contains($markdown, '| PASS | 1 |'));
assert(str_contains($markdown, 'Perfil aprobado para el fixture.'));
assert(str_contains($markdown, 'No existe todavía tráfico de campo suficiente; se usa PERF-002.'));
assert(str_contains($markdown, 'fixture-reviewer'));
assert(str_contains($markdown, '2026-09-04'));

$govRow = null;
foreach (explode(PHP_EOL, $markdown) as $line) {
    if (str_starts_with($line, '| GOV-001 |')) {
        $govRow = $line;
        break;
    }
}
assert(is_string($govRow));
$regexStart = strpos($govRow, 'regex ');
assert($regexStart !== false);
$innerPipe = strpos($govRow, '|', $regexStart + strlen('regex '));
assert($innerPipe !== false);
$backslashesBeforePipe = 0;
for ($i = $innerPipe - 1; $i >= 0 && $govRow[$i] === '\\'; $i--) {
    $backslashesBeforePipe++;
}
assert($backslashesBeforePipe === 3);

$missingHuman = $tmp . '/missing-human.json';
file_put_contents($missingHuman, json_encode([
    'controls' => [
        'GOV-001' => ['state' => 'PASS', 'evidence' => ['profile.md']],
    ],
]));
[$rcMissingHuman, , $errMissingHuman] = runReadinessReport($reporter, ['--level', 'A', '--evidence', $missingHuman]);
assert($rcMissingHuman === 2);
assert(str_contains($errMissingHuman, 'human_pass_or_na_requires_reviewer_and_date=GOV-001'));

$missingNa = $tmp . '/missing-na.json';
file_put_contents($missingNa, json_encode([
    'controls' => [
        'PERF-001' => ['state' => 'N/A', 'reviewed_by' => 'reviewer', 'reviewed_at' => '2026-09-04'],
    ],
]));
[$rcMissingNa, , $errMissingNa] = runReadinessReport($reporter, ['--level', 'A', '--evidence', $missingNa]);
assert($rcMissingNa === 2);
assert(str_contains($errMissingNa, 'na_requires_justification_and_evidence=PERF-001'));

$outOfLevelInvalid = $tmp . '/out-of-level-invalid.json';
file_put_contents($outOfLevelInvalid, json_encode([
    'controls' => [
        'SEC-004' => ['state' => 'BANANA'],
    ],
]));
[$rcOutOfLevelInvalid, , $errOutOfLevelInvalid] = runReadinessReport($reporter, ['--level', 'A', '--evidence', $outOfLevelInvalid]);
assert($rcOutOfLevelInvalid === 2);
assert(str_contains($errOutOfLevelInvalid, 'invalid_state=SEC-004:BANANA'));

$outOfLevelMissingReview = $tmp . '/out-of-level-missing-review.json';
file_put_contents($outOfLevelMissingReview, json_encode([
    'controls' => [
        'SEC-004' => ['state' => 'PASS', 'evidence' => ['tests/sec-004.md']],
    ],
]));
[$rcOutOfLevelMissingReview, , $errOutOfLevelMissingReview] = runReadinessReport($reporter, ['--level', 'A', '--evidence', $outOfLevelMissingReview]);
assert($rcOutOfLevelMissingReview === 2);
assert(str_contains($errOutOfLevelMissingReview, 'human_pass_or_na_requires_reviewer_and_date=SEC-004'));

$unknown = $tmp . '/unknown.json';
file_put_contents($unknown, json_encode(['controls' => ['NOPE-999' => ['state' => 'NOT EVALUATED']]]));
[$rcUnknown, , $errUnknown] = runReadinessReport($reporter, ['--level', 'A', '--evidence', $unknown]);
assert($rcUnknown === 2);
assert(str_contains($errUnknown, 'unknown_evidence_control=NOPE-999'));

$overrideStandard = $tmp . '/PRODUCTION-READINESS-STANDARD.override.md';
assert(copy($root . '/docs/production-readiness/PRODUCTION-READINESS-STANDARD.md', $overrideStandard));
[$rcOverride, $stdoutOverride, $stderrOverride] = runReadinessReport($reporter, [
    '--level', 'A',
    '--standard', $overrideStandard,
]);
assert($rcOverride === 0, $stderrOverride);
$reportOverride = json_decode($stdoutOverride, true, 512, JSON_THROW_ON_ERROR);
assert($reportOverride['source']['standard'] === realpath($overrideStandard));
assert($reportOverride['source']['sha256'] === hash_file('sha256', $overrideStandard));

[$rcInvalidLevel, , $errInvalidLevel] = runReadinessReport($reporter, ['--level', 'D']);
assert($rcInvalidLevel === 2);
assert(str_contains($errInvalidLevel, 'level_must_be_A_B_or_C'));

echo "PRODUCTION_READINESS_REPORT_OK\n";
