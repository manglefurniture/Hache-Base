<?php

declare(strict_types=1);

use HacheBase\Common\AsyncOperationState;

require_once __DIR__ . '/../../src/common/AsyncOperationState.php';

assert(AsyncOperationState::isKnown(AsyncOperationState::REQUESTED));
assert(AsyncOperationState::isAuthoritativeSuccess(AsyncOperationState::CONFIRMED));
assert(!AsyncOperationState::isAuthoritativeSuccess(AsyncOperationState::ACCEPTED));
assert(!AsyncOperationState::isTerminal(AsyncOperationState::ACCEPTED));
assert(AsyncOperationState::requiresFollowUp(AsyncOperationState::OUTCOME_UNKNOWN));
assert(AsyncOperationState::mayRetry(AsyncOperationState::RETRY_PENDING));
assert(!AsyncOperationState::mayRetry(AsyncOperationState::OUTCOME_UNKNOWN));

assert(AsyncOperationState::canTransition(AsyncOperationState::REQUESTED, AsyncOperationState::ACCEPTED));
assert(AsyncOperationState::canTransition(AsyncOperationState::OUTCOME_UNKNOWN, AsyncOperationState::RECONCILING));
assert(!AsyncOperationState::canTransition(AsyncOperationState::OUTCOME_UNKNOWN, AsyncOperationState::RETRY_PENDING));
assert(!AsyncOperationState::canTransition(AsyncOperationState::CONFIRMED, AsyncOperationState::REQUESTED));

$fixturePath = __DIR__ . '/../fixtures/async-operations/scenarios.json';
$fixture = json_decode((string) file_get_contents($fixturePath), true, 512, JSON_THROW_ON_ERROR);
assert(isset($fixture['scenarios']) && is_array($fixture['scenarios']));

foreach ($fixture['scenarios'] as $scenario) {
    assert(is_string($scenario['operation_id'] ?? null));
    assert(isset($scenario['events']) && is_array($scenario['events']) && $scenario['events'] !== []);

    foreach ($scenario['events'] as $event) {
        $from = $event['from'] ?? '';
        $to = $event['to'] ?? '';
        AsyncOperationState::assertTransition($from, $to);
        assert(is_string($event['request_id'] ?? null));
        assert(is_string($event['correlation_id'] ?? null));
    }
}

$invalidTransitionRejected = false;
try {
    AsyncOperationState::assertTransition(AsyncOperationState::ACCEPTED, AsyncOperationState::RETRY_PENDING);
} catch (InvalidArgumentException) {
    $invalidTransitionRejected = true;
}
assert($invalidTransitionRejected);

$unknownStateRejected = false;
try {
    AsyncOperationState::isTerminal('delivered');
} catch (InvalidArgumentException) {
    $unknownStateRejected = true;
}
assert($unknownStateRejected);

echo "ASYNC_OPERATION_STATE_OK\n";
