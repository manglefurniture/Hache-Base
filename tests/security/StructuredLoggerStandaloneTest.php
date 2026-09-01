<?php

declare(strict_types=1);

use HacheBase\Common\StructuredLogger;

require_once __DIR__ . '/../../src/common/StructuredLogger.php';

$lines = [];
$logger = new StructuredLogger(
    'standalone-logger-test',
    'test',
    'standalone',
    static function (string $line) use (&$lines): void {
        $lines[] = $line;
    },
);

// Regression: StructuredLogger must be usable by itself and create a default
// RequestContext without consumers manually loading RequestContext.php first.
$logger->log('info', 'standalone.context');
assert(count($lines) === 1);
$standaloneRecord = json_decode($lines[0], true, 512, JSON_THROW_ON_ERROR);
assert($standaloneRecord['request_id'] !== '');
assert($standaloneRecord['correlation_id'] !== '');

$lines = [];
$dangerousDto = new class implements JsonSerializable {
    public string $password = 'must-not-leak-public';

    public function jsonSerialize(): mixed
    {
        return [
            'password' => 'must-not-leak-jsonserialize',
            'token' => 'must-not-leak-token',
        ];
    }
};

$logger->log('warn', 'standalone.object-redaction', [
    'dto' => $dangerousDto,
    'safe' => 'visible',
]);

assert(count($lines) === 1);
assert(!str_contains($lines[0], 'must-not-leak-public'));
assert(!str_contains($lines[0], 'must-not-leak-jsonserialize'));
assert(!str_contains($lines[0], 'must-not-leak-token'));

$objectRecord = json_decode($lines[0], true, 512, JSON_THROW_ON_ERROR);
assert($objectRecord['context']['dto'] === '[OBJECT_REDACTED]');
assert($objectRecord['context']['safe'] === 'visible');

echo "STRUCTURED_LOGGER_STANDALONE_OK\n";
