<?php

declare(strict_types=1);

use HacheBase\Common\RequestContext;
use HacheBase\Common\StructuredLogger;
use HacheBase\Security\ApiResponse;

require_once __DIR__ . '/../../src/common/RequestContext.php';
require_once __DIR__ . '/../../src/common/StructuredLogger.php';
require_once __DIR__ . '/../../security/api-response.php';

$context = RequestContext::create('req-123', 'corr-456');
assert($context->requestId() === 'req-123');
assert($context->correlationId() === 'corr-456');
assert(RequestContext::normalizeExternalId('abc.DEF-123:xyz') === 'abc.DEF-123:xyz');
assert(RequestContext::normalizeExternalId('bad id with spaces') === null);
assert(RequestContext::normalizeExternalId(str_repeat('a', 129)) === null);

$fromServer = RequestContext::fromServer([
    'HTTP_X_REQUEST_ID' => 'external-req',
    'HTTP_X_CORRELATION_ID' => 'external-corr',
]);
assert($fromServer->requestId() === 'external-req');
assert($fromServer->correlationId() === 'external-corr');

$invalidFromServer = RequestContext::fromServer([
    'HTTP_X_REQUEST_ID' => "unsafe\nheader",
]);
assert($invalidFromServer->requestId() !== "unsafe\nheader");
assert(strlen($invalidFromServer->requestId()) === 32);

$expectedCodes = [
    400 => ApiResponse::ERROR_BAD_REQUEST,
    401 => ApiResponse::ERROR_UNAUTHORIZED,
    403 => ApiResponse::ERROR_FORBIDDEN,
    404 => ApiResponse::ERROR_NOT_FOUND,
    409 => ApiResponse::ERROR_CONFLICT,
    422 => ApiResponse::ERROR_VALIDATION_FAILED,
    429 => ApiResponse::ERROR_RATE_LIMITED,
    500 => ApiResponse::ERROR_INTERNAL,
    503 => ApiResponse::ERROR_SERVICE_UNAVAILABLE,
];

foreach ($expectedCodes as $status => $expectedCode) {
    $definition = ApiResponse::errorDefinition($status);
    assert($definition['code'] === $expectedCode);
    assert($definition['message'] !== '');
}

$unsupportedThrown = false;
try {
    ApiResponse::errorDefinition(418);
} catch (InvalidArgumentException) {
    $unsupportedThrown = true;
}
assert($unsupportedThrown === true);

$errorPayload = ApiResponse::errorPayload('PROJECT_CONFLICT', 'Safe public message.', $context);
assert($errorPayload === [
    'ok' => false,
    'error' => [
        'code' => 'PROJECT_CONFLICT',
        'message' => 'Safe public message.',
    ],
    'request_id' => 'req-123',
]);

$successPayload = ApiResponse::successPayload(['status' => 'ok'], $context);
assert($successPayload['ok'] === true);
assert($successPayload['data']['status'] === 'ok');
assert($successPayload['request_id'] === 'req-123');

$lines = [];
$logger = new StructuredLogger(
    'hache-base-test',
    'test',
    'commit-test',
    static function (string $line) use (&$lines): void {
        $lines[] = $line;
    },
);

$logger->log('warn', 'provider.retry', [
    'attempt' => 2,
    'token' => 'must-not-leak',
    'nested' => [
        'Authorization' => 'Bearer must-not-leak',
        'customer_id' => 'safe-id',
    ],
], $context);

assert(count($lines) === 1);
$record = json_decode($lines[0], true, 512, JSON_THROW_ON_ERROR);
assert($record['severity'] === 'WARN');
assert($record['service'] === 'hache-base-test');
assert($record['environment'] === 'test');
assert($record['version'] === 'commit-test');
assert($record['event'] === 'provider.retry');
assert($record['request_id'] === 'req-123');
assert($record['correlation_id'] === 'corr-456');
assert($record['context']['attempt'] === 2);
assert($record['context']['token'] === '[REDACTED]');
assert($record['context']['nested']['Authorization'] === '[REDACTED]');
assert($record['context']['nested']['customer_id'] === 'safe-id');

$invalidSeverityThrown = false;
try {
    $logger->log('TRACE', 'invalid', [], $context);
} catch (InvalidArgumentException) {
    $invalidSeverityThrown = true;
}
assert($invalidSeverityThrown === true);

echo "PRODUCTION_READINESS_CORE_OK\n";
