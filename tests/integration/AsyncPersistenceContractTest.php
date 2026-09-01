<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/common/AsyncOperationState.php';

use HacheBase\Common\AsyncOperationState;

$sqlPath = __DIR__ . '/../../database/modules/async-inbox-outbox.sql';
$sql = file_get_contents($sqlPath);
if ($sql === false) {
    throw new RuntimeException('Cannot read async-inbox-outbox.sql');
}

$reflection = new ReflectionClass(AsyncOperationState::class);
$states = [];
foreach ($reflection->getConstants() as $value) {
    if (is_string($value) && AsyncOperationState::isKnown($value)) {
        $states[$value] = true;
    }
}

assert(count($states) === 8);

foreach (array_keys($states) as $state) {
    $quoted = "'" . $state . "'";
    assert(
        substr_count($sql, $quoted) >= 2,
        sprintf('State %s must be constrained in outbox and idempotency claims', $state),
    );
}

assert(str_contains($sql, 'UNIQUE KEY uq_integration_inbox_source_event'));
assert(str_contains($sql, 'UNIQUE KEY uq_integration_outbox_idempotency'));
assert(str_contains($sql, 'UNIQUE KEY uq_integration_claim_scope_key'));
assert(str_contains($sql, 'dispatch_started_at'));
assert(str_contains($sql, 'effect_started_at'));
assert(!preg_match('/\bCREATE\s+(TRIGGER|PROCEDURE|EVENT)\b/i', $sql));

echo "ASYNC_PERSISTENCE_CONTRACT_OK\n";
