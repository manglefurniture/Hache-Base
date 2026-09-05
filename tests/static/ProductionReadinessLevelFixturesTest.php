<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$fixtureDir = $root . '/tests/level-fixtures/fixtures';
$runSh = (string) file_get_contents($root . '/tests/run.sh');
$workflow = (string) file_get_contents($root . '/.github/workflows/ci.yml');
$roadmap = (string) file_get_contents($root . '/docs/production-readiness/PRODUCTION-READINESS-ROADMAP.md');
$standard = (string) file_get_contents($root . '/docs/production-readiness/PRODUCTION-READINESS-STANDARD.md');
$fixtureDoc = (string) file_get_contents($root . '/docs/production-readiness/LEVEL-A-B-C-FIXTURES.md');
$formBDoc = (string) file_get_contents($root . '/docs/production-readiness/FORM-B-FIXTURE.md');
$reporter = $root . '/tools/production-readiness/report.php';

assert(str_contains($standard, '| **A — Informativo**'));
assert(str_contains($standard, '| **B — Interactivo**'));
assert(str_contains($standard, '| **C — Crítico**'));
assert(str_contains($roadmap, 'Un fixture A, B y C demuestra clasificación y checklist.'));
assert(str_contains($roadmap, 'Fixtures A/B/C cubren headers, errores, CUF y budgets.'));
assert(str_contains($formBDoc, 'Nivel B'));
assert(str_contains($fixtureDoc, 'criterio de salida P0'));
assert(str_contains($fixtureDoc, 'criterio de salida P1'));
assert(str_contains($fixtureDoc, 'no declara Production Ready'));
assert(str_contains($fixtureDoc, 'regresiones compartidas'));

/** @return array{int,string,string} */
function runLevelReporter(string $reporter, string $level): array
{
    $spec = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $process = proc_open([PHP_BINARY, $reporter, '--level', $level], $spec, $pipes);
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
function levelControlsById(array $report): array
{
    $byId = [];
    foreach ($report['controls'] as $control) {
        $byId[$control['id']] = $control;
    }
    return $byId;
}

function assertExactKeys(array $value, array $expected, string $label): void
{
    $actual = array_keys($value);
    sort($actual);
    sort($expected);
    assert($actual === $expected, $label . '_keys_drift');
}

function assertFixturePath(string $root, string $relativePath, string $label): void
{
    assert($relativePath !== '', $label . '_empty');
    assert(!str_contains($relativePath, '..'), $label . '_parent_escape');
    assert(is_file($root . '/' . $relativePath), $label . '_missing_' . $relativePath);
}

$expectedLevels = ['A', 'B', 'C'];
$fixtures = [];
$executionContract = $runSh . "\n" . $workflow;
$coverageKeys = ['classification', 'checklist', 'headers', 'errors', 'cuf', 'budgets'];
$requiredExecutableEvidence = [
    'tests/http/ProductionReadinessHttpTest.sh',
    'tests/security/HeadersTest.php',
    'tests/security/ProductionReadinessCoreTest.php',
    'tests/browser/config-contract.mjs',
    'tests/performance/ReleaseBudgetTest.mjs',
    'tests/form-b/ProductionReadinessFormBTest.sh',
    'tests/integration/InboxOutboxMariaDbTest.sh',
];
$cufKeys = [
    'id',
    'level',
    'technical_owner',
    'business_owner',
    'goal',
    'precondition',
    'steps',
    'observable_result',
    'authoritative_result',
    'mutations',
    'integrations',
    'failure_states',
    'idempotency_key',
    'concurrency_behavior',
    'automated_test',
    'smoke_contract',
    'signals',
    'recovery',
];

foreach ($requiredExecutableEvidence as $relativePath) {
    assertFixturePath($root, $relativePath, 'required_executable_evidence');
    assert(str_contains($executionContract, $relativePath), 'required_evidence_not_executed_in_ci_' . $relativePath);
}

foreach ($expectedLevels as $level) {
    $path = $fixtureDir . '/level-' . strtolower($level) . '.json';
    assert(is_file($path), 'missing_fixture_' . $level);
    $fixture = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
    assertExactKeys($fixture, [
        'schema_version',
        'fixture_id',
        'level',
        'name',
        'report_level',
        'classification',
        'cufs',
        'coverage',
        'disclaimer',
    ], 'fixture_' . $level);
    assert($fixture['schema_version'] === 1);
    assert($fixture['level'] === $level);
    assert($fixture['report_level'] === $level);
    assert(is_string($fixture['fixture_id']) && $fixture['fixture_id'] !== '');
    assert(is_string($fixture['name']) && $fixture['name'] !== '');
    assert(is_string($fixture['disclaimer']) && str_contains($fixture['disclaimer'], 'fixture'));

    assertExactKeys($fixture['classification'], ['profile', 'rationale', 'signals'], 'classification_' . $level);
    assert(is_string($fixture['classification']['profile']) && $fixture['classification']['profile'] !== '');
    assert(is_string($fixture['classification']['rationale']) && $fixture['classification']['rationale'] !== '');
    assert(is_array($fixture['classification']['signals']));

    assert(is_array($fixture['cufs']) && count($fixture['cufs']) >= 1);
    foreach ($fixture['cufs'] as $cuf) {
        assertExactKeys($cuf, $cufKeys, 'cuf_' . $level);
        assert($cuf['level'] === $level, 'cuf_level_drift_' . $level);
        foreach ([
            'id',
            'technical_owner',
            'business_owner',
            'goal',
            'precondition',
            'observable_result',
            'authoritative_result',
            'mutations',
            'integrations',
            'idempotency_key',
            'concurrency_behavior',
            'automated_test',
            'smoke_contract',
            'recovery',
        ] as $field) {
            assert(is_string($cuf[$field]) && trim($cuf[$field]) !== '', 'cuf_' . $level . '_' . $field);
        }
        foreach (['steps', 'failure_states', 'signals'] as $field) {
            assert(is_array($cuf[$field]) && count($cuf[$field]) >= 1, 'cuf_' . $level . '_' . $field);
        }
        assertFixturePath($root, $cuf['automated_test'], 'cuf_' . $level . '_automated_test');
        assertFixturePath($root, $cuf['smoke_contract'], 'cuf_' . $level . '_smoke_contract');
        assert(str_contains($executionContract, $cuf['automated_test']), 'cuf_test_not_executed_' . $cuf['automated_test']);
        assert(str_contains($executionContract, $cuf['smoke_contract']), 'cuf_smoke_not_connected_' . $cuf['smoke_contract']);
    }

    assertExactKeys($fixture['coverage'], $coverageKeys, 'coverage_' . $level);
    foreach ($coverageKeys as $category) {
        assert(is_array($fixture['coverage'][$category]) && count($fixture['coverage'][$category]) >= 1, 'coverage_empty_' . $level . '_' . $category);
        foreach ($fixture['coverage'][$category] as $relativePath) {
            assert(is_string($relativePath));
            assertFixturePath($root, $relativePath, 'coverage_' . $level . '_' . $category);
        }
    }

    [$rc, $stdout, $stderr] = runLevelReporter($reporter, $level);
    assert($rc === 0, $stderr);
    $report = json_decode($stdout, true, 512, JSON_THROW_ON_ERROR);
    assert($report['schema_version'] === 1);
    assert($report['level'] === $level);
    assert($report['source']['canonical_control_count'] === 126);
    assert($report['decision'] === 'NOT_A_PRODUCTION_READY_DECLARATION');
    assert($report['summary']['applicable_controls'] + $report['summary']['out_of_level_controls'] === 126);
    foreach ($report['controls'] as $control) {
        if ($control['scope'] === 'applicable') {
            assert($control['evaluation']['state'] === 'NOT EVALUATED');
        }
    }

    $fixtures[$level] = [
        'fixture' => $fixture,
        'controls' => levelControlsById($report),
    ];
}

$aSignals = $fixtures['A']['fixture']['classification']['signals'];
foreach ($aSignals as $value) {
    assert($value === false, 'level_a_must_not_hide_escalation_signal');
}
assert($fixtures['A']['fixture']['classification']['profile'] === 'informational');
assert($fixtures['A']['controls']['SEC-004']['scope'] === 'out_of_level');
assert($fixtures['A']['fixture']['cufs'][0]['idempotency_key'] === 'N/A — read-only flow');

$bSignals = $fixtures['B']['fixture']['classification']['signals'];
assert($fixtures['B']['fixture']['classification']['profile'] === 'interactive');
assert($bSignals['accepts_user_input'] === true);
assert($bSignals['remote_mutation'] === true);
assert($bSignals['duplicate_or_loss_material_harm'] === false);
assert($fixtures['B']['controls']['SEC-008']['scope'] === 'applicable');
assert($fixtures['B']['controls']['ROB-005']['scope'] === 'out_of_level');
assert(in_array('tests/form-b/ProductionReadinessFormBTest.sh', $fixtures['B']['fixture']['coverage']['cuf'], true));
assert(str_contains($fixtures['B']['fixture']['cufs'][0]['concurrency_behavior'], 'does not claim durable'));

$cSignals = $fixtures['C']['fixture']['classification']['signals'];
assert($fixtures['C']['fixture']['classification']['profile'] === 'critical');
assert($cSignals['critical_capacity_or_inventory'] === true);
assert($cSignals['external_state_change'] === true);
assert($cSignals['duplicate_or_loss_material_harm'] === true);
assert($fixtures['C']['controls']['ROB-005']['scope'] === 'applicable');
assert(in_array('tests/integration/InboxOutboxMariaDbTest.sh', $fixtures['C']['fixture']['coverage']['cuf'], true));
assert(str_contains($fixtures['C']['fixture']['cufs'][0]['recovery'], 'do not issue a second critical mutation'));

foreach ($expectedLevels as $level) {
    foreach (['headers', 'errors', 'cuf', 'budgets'] as $requiredCoverage) {
        assert(count($fixtures[$level]['fixture']['coverage'][$requiredCoverage]) >= 1);
    }
}

assert(str_contains($runSh, 'ProductionReadinessLevelFixturesTest.php'));

echo "PRODUCTION_READINESS_LEVEL_FIXTURES_OK\n";
