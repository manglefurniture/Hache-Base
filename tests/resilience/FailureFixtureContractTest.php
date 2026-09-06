<?php

declare(strict_types=1);

use HacheBase\Tests\Fixtures\Failures\FailureFixture;
use HacheBase\Tests\Fixtures\Failures\FailureFixtureException;

require_once __DIR__ . '/../fixtures/failures/FailureFixture.php';

/** @return array{category: string, phase: string, http_status: ?int, retry_after_seconds: ?int} */
function captureFailure(FailureFixture $fixture): array
{
    try {
        $fixture->invoke(static fn (): string => 'success');
        assert(false, 'Expected scripted failure.');
    } catch (FailureFixtureException $failure) {
        return $failure->metadata();
    }
}

$cases = [
    'timeout' => [
        FailureFixtureException::timeout(),
        [
            'category' => FailureFixtureException::TIMEOUT,
            'phase' => FailureFixtureException::PHASE_OPERATION,
            'http_status' => null,
            'retry_after_seconds' => null,
        ],
    ],
    '429' => [
        FailureFixtureException::http429(17),
        [
            'category' => FailureFixtureException::HTTP_429,
            'phase' => FailureFixtureException::PHASE_RESPONSE,
            'http_status' => 429,
            'retry_after_seconds' => 17,
        ],
    ],
    '503' => [
        FailureFixtureException::http5xx(503),
        [
            'category' => FailureFixtureException::HTTP_5XX,
            'phase' => FailureFixtureException::PHASE_RESPONSE,
            'http_status' => 503,
            'retry_after_seconds' => null,
        ],
    ],
    'dns' => [
        FailureFixtureException::dns(),
        [
            'category' => FailureFixtureException::DNS,
            'phase' => FailureFixtureException::PHASE_CONNECT,
            'http_status' => null,
            'retry_after_seconds' => null,
        ],
    ],
    'storage' => [
        FailureFixtureException::storage(),
        [
            'category' => FailureFixtureException::STORAGE,
            'phase' => FailureFixtureException::PHASE_STORAGE,
            'http_status' => null,
            'retry_after_seconds' => null,
        ],
    ],
];

foreach ($cases as $name => [$failure, $expected]) {
    $fixture = FailureFixture::failOnce($failure);
    assert($fixture->attempts() === 0, "{$name}: initial attempts");
    assert($fixture->remainingScriptedSteps() === 2, "{$name}: initial script length");
    assert(captureFailure($fixture) === $expected, "{$name}: metadata mismatch");
    assert($fixture->attempts() === 1, "{$name}: failed attempt counted");
    assert($fixture->remainingScriptedSteps() === 1, "{$name}: one scripted success remains");

    $successCalls = 0;
    $result = $fixture->invoke(static function () use (&$successCalls, $name): string {
        $successCalls++;
        return "ok-{$name}";
    });
    assert($result === "ok-{$name}");
    assert($successCalls === 1);
    assert($fixture->attempts() === 2);
    assert($fixture->remainingScriptedSteps() === 0);

    // Once the script is exhausted, the harness stays transparent.
    assert($fixture->invoke(static fn (): string => 'steady') === 'steady');
    assert($fixture->attempts() === 3);
}

$repeated = FailureFixture::failRepeatedly(FailureFixtureException::http5xx(502), 3);
for ($attempt = 1; $attempt <= 3; $attempt++) {
    $metadata = captureFailure($repeated);
    assert($metadata['category'] === FailureFixtureException::HTTP_5XX);
    assert($metadata['http_status'] === 502);
    assert($repeated->attempts() === $attempt);
}
assert($repeated->invoke(static fn (): string => 'recovered') === 'recovered');
assert($repeated->attempts() === 4);

$scripted = new FailureFixture([
    FailureFixtureException::dns(),
    FailureFixtureException::timeout(),
    null,
]);
assert(captureFailure($scripted)['category'] === FailureFixtureException::DNS);
assert(captureFailure($scripted)['category'] === FailureFixtureException::TIMEOUT);
assert($scripted->invoke(static fn (): int => 204) === 204);

foreach (
    [
        static fn () => FailureFixtureException::http429(-1),
        static fn () => FailureFixtureException::http5xx(499),
        static fn () => FailureFixtureException::http5xx(600),
        static fn () => FailureFixture::failRepeatedly(FailureFixtureException::timeout(), 0),
        static fn () => new FailureFixture(['invalid']),
    ] as $invalid
) {
    try {
        $invalid();
        assert(false, 'Expected InvalidArgumentException.');
    } catch (InvalidArgumentException) {
        // Expected.
    }
}

// Contract boundary: failure metadata contains no retry/reconcile/final-state decision.
$metadataKeys = array_keys(FailureFixtureException::timeout()->metadata());
sort($metadataKeys);
assert($metadataKeys === ['category', 'http_status', 'phase', 'retry_after_seconds']);

echo "FAILURE_FIXTURE_CONTRACT_OK\n";
