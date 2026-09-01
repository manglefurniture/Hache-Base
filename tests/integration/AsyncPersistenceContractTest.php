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

$canonicalStates = array_keys($states);
sort($canonicalStates);
assert(count($canonicalStates) === 8);

$constraints = [
    'chk_integration_outbox_operation_state',
    'chk_integration_claim_operation_state',
];

foreach ($constraints as $constraintName) {
    $pattern = '/CONSTRAINT\s+' . preg_quote($constraintName, '/')
        . '\s+CHECK\s*\(\s*operation_state\s+IN\s*\((.*?)\)\s*\)/is';

    assert(
        preg_match($pattern, $sql, $match) === 1,
        sprintf('Missing or unparsable state constraint: %s', $constraintName),
    );

    preg_match_all("/'([^']+)'/", $match[1], $stateMatches);
    $sqlStates = $stateMatches[1];
    sort($sqlStates);

    assert(
        $sqlStates === $canonicalStates,
        sprintf(
            'SQL state vocabulary drift in %s: expected [%s], got [%s]',
            $constraintName,
            implode(', ', $canonicalStates),
            implode(', ', $sqlStates),
        ),
    );
}

assert(str_contains($sql, 'source VARCHAR(80) COLLATE utf8mb4_bin'));
assert(str_contains($sql, 'external_event_id VARCHAR(191) COLLATE utf8mb4_bin'));
assert(str_contains($sql, 'idempotency_key VARCHAR(191) COLLATE utf8mb4_bin'));
assert(str_contains($sql, 'scope_name VARCHAR(80) COLLATE utf8mb4_bin'));
assert(str_contains($sql, 'claim_key VARCHAR(191) COLLATE utf8mb4_bin'));
assert(substr_count($sql, 'operation_state VARCHAR(32) COLLATE utf8mb4_bin') === 2);

assert(str_contains($sql, 'UNIQUE KEY uq_integration_inbox_source_event'));
assert(str_contains($sql, 'UNIQUE KEY uq_integration_outbox_idempotency'));
assert(str_contains($sql, 'UNIQUE KEY uq_integration_claim_scope_key'));
assert(str_contains($sql, 'dispatch_started_at'));
assert(str_contains($sql, 'effect_started_at'));
assert(!preg_match('/\bCREATE\s+(TRIGGER|PROCEDURE|EVENT)\b/i', $sql));

echo "ASYNC_PERSISTENCE_CONTRACT_OK\n";
