<?php

declare(strict_types=1);

namespace HacheBase\Common;

use InvalidArgumentException;
use JsonException;

require_once __DIR__ . '/RequestContext.php';

final class StructuredLogger
{
    private const SEVERITIES = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'];
    private const REDACTED = '[REDACTED]';
    private const OBJECT_REDACTED = '[OBJECT_REDACTED]';
    private const MAX_STRING_LENGTH = 4096;

    /** @var callable(string): mixed */
    private $writer;

    public function __construct(
        private readonly string $service,
        private readonly string $environment,
        private readonly string $version = 'unknown',
        ?callable $writer = null,
    ) {
        if ($service === '' || $environment === '') {
            throw new InvalidArgumentException('service and environment are required.');
        }

        $this->writer = $writer ?? static fn (string $line): bool => error_log($line);
    }

    /**
     * Emit one JSON line with stable fields suitable for parsing and correlation.
     * Context is recursively redacted before serialization.
     *
     * @throws JsonException
     */
    public function log(
        string $severity,
        string $event,
        array $context = [],
        ?RequestContext $requestContext = null,
    ): void {
        $severity = strtoupper(trim($severity));
        if (!in_array($severity, self::SEVERITIES, true)) {
            throw new InvalidArgumentException('Unsupported log severity.');
        }

        $event = trim($event);
        if ($event === '') {
            throw new InvalidArgumentException('event is required.');
        }

        $requestContext ??= RequestContext::fromServer();

        $record = [
            'timestamp' => gmdate('Y-m-d\TH:i:s\Z'),
            'severity' => $severity,
            'environment' => $this->environment,
            'service' => $this->service,
            'version' => $this->version,
            'event' => $event,
            'request_id' => $requestContext->requestId(),
            'correlation_id' => $requestContext->correlationId(),
            'context' => self::redact($context),
        ];

        $line = json_encode(
            $record,
            JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR,
        );

        ($this->writer)($line);
    }

    public static function redact(mixed $value, ?string $key = null): mixed
    {
        if ($key !== null && self::isSensitiveKey($key)) {
            return self::REDACTED;
        }

        if (is_array($value)) {
            $redacted = [];
            foreach ($value as $childKey => $childValue) {
                $redacted[$childKey] = self::redact($childValue, is_string($childKey) ? $childKey : null);
            }
            return $redacted;
        }

        // Do not let json_encode() serialize arbitrary DTO/stdClass/JsonSerializable
        // instances after redaction. Their public or custom serialized payload can
        // expose credentials under fields this logger did not inspect.
        if (is_object($value)) {
            return self::OBJECT_REDACTED;
        }

        if (is_string($value) && strlen($value) > self::MAX_STRING_LENGTH) {
            return substr($value, 0, self::MAX_STRING_LENGTH) . '…[TRUNCATED]';
        }

        return $value;
    }

    private static function isSensitiveKey(string $key): bool
    {
        $normalized = strtolower(str_replace(['-', '.'], '_', $key));
        $fragments = [
            'password',
            'passwd',
            'token',
            'secret',
            'authorization',
            'cookie',
            'api_key',
            'apikey',
            'private_key',
            'cvv',
            'card_number',
        ];

        foreach ($fragments as $fragment) {
            if (str_contains($normalized, $fragment)) {
                return true;
            }
        }

        return false;
    }
}
