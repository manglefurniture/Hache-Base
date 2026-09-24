<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/common/ReadModelContract.php';

use HacheBase\Common\ReadModelContract;

$forwardCoverage = ReadModelContract::coverage(
    ReadModelContract::COVERAGE_FORWARD_ONLY,
    '2026-09-24T12:00:00Z',
);
assert($forwardCoverage['history_reconstructed'] === false);

$zero = ReadModelContract::metric([
    'id' => 'confirmed_items',
    'authority' => 'project-owned authoritative query',
    'numerator' => 'confirmed items in the selected scope',
    'denominator' => 'not applicable for this count',
    'exclusions' => 'invalidated items',
    'cutoff_at' => '2026-09-24T12:00:00Z',
    'timezone' => 'UTC',
    'coverage' => $forwardCoverage,
    'availability' => ReadModelContract::AVAILABLE,
    'value' => 0,
]);
assert($zero['value'] === 0);
assert($zero['coverage']['state'] === ReadModelContract::COVERAGE_FORWARD_ONLY);

$unavailableAsZeroRejected = false;
try {
    ReadModelContract::metric([
        'id' => 'unknown_items',
        'authority' => 'project-owned authoritative query',
        'numerator' => 'unknown',
        'denominator' => 'unknown',
        'exclusions' => 'unknown',
        'cutoff_at' => '2026-09-24T12:00:00Z',
        'timezone' => 'UTC',
        'coverage' => ReadModelContract::coverage(ReadModelContract::COVERAGE_NOT_EVALUATED, null),
        'availability' => ReadModelContract::NOT_EVALUATED,
        'value' => 0,
    ]);
} catch (InvalidArgumentException) {
    $unavailableAsZeroRejected = true;
}
assert($unavailableAsZeroRejected === true);

$missingCoverageMarkerRejected = false;
try {
    ReadModelContract::coverage(ReadModelContract::COVERAGE_FORWARD_ONLY, null);
} catch (InvalidArgumentException) {
    $missingCoverageMarkerRejected = true;
}
assert($missingCoverageMarkerRejected === true);

$evidence = ReadModelContract::operationalEvidence([
    'collector' => 'daily_read_model_evidence',
    'observed_at' => '2026-09-24T12:00:00Z',
    'read_only' => true,
    'read_only_transaction' => 'completed',
    'pii_minimized' => true,
    'decision' => ReadModelContract::HUMAN_REVIEW_REQUIRED,
]);
assert($evidence['decision'] === ReadModelContract::HUMAN_REVIEW_REQUIRED);

$automaticPassRejected = false;
try {
    ReadModelContract::operationalEvidence([
        'collector' => 'daily_read_model_evidence',
        'observed_at' => '2026-09-24T12:00:00Z',
        'read_only' => true,
        'read_only_transaction' => 'completed',
        'pii_minimized' => true,
        'decision' => 'pass',
    ]);
} catch (InvalidArgumentException) {
    $automaticPassRejected = true;
}
assert($automaticPassRejected === true);

echo "ReadModelContractTest OK\n";
