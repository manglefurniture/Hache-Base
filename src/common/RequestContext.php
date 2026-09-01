<?php

declare(strict_types=1);

namespace HacheBase\Common;

final class RequestContext
{
    private const MAX_ID_LENGTH = 128;

    private function __construct(
        private readonly string $requestId,
        private readonly string $correlationId,
    ) {
    }

    /**
     * Build request/correlation identifiers from trusted request metadata.
     * Invalid external identifiers are never propagated; a local identifier is generated instead.
     */
    public static function fromServer(?array $server = null): self
    {
        $server ??= $_SERVER;

        $requestId = self::normalizeExternalId($server['HTTP_X_REQUEST_ID'] ?? null)
            ?? self::generateId();
        $correlationId = self::normalizeExternalId($server['HTTP_X_CORRELATION_ID'] ?? null)
            ?? $requestId;

        return new self($requestId, $correlationId);
    }

    /**
     * Create a context explicitly. Useful for jobs, webhooks, tests and adapters.
     */
    public static function create(?string $requestId = null, ?string $correlationId = null): self
    {
        $normalizedRequestId = self::normalizeExternalId($requestId) ?? self::generateId();
        $normalizedCorrelationId = self::normalizeExternalId($correlationId) ?? $normalizedRequestId;

        return new self($normalizedRequestId, $normalizedCorrelationId);
    }

    public function requestId(): string
    {
        return $this->requestId;
    }

    public function correlationId(): string
    {
        return $this->correlationId;
    }

    /** @return array{X-Request-Id: string, X-Correlation-Id: string} */
    public function responseHeaders(): array
    {
        return [
            'X-Request-Id' => $this->requestId,
            'X-Correlation-Id' => $this->correlationId,
        ];
    }

    public static function normalizeExternalId(mixed $value): ?string
    {
        if (!is_string($value)) {
            return null;
        }

        $value = trim($value);
        if ($value === '' || strlen($value) > self::MAX_ID_LENGTH) {
            return null;
        }

        return preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]*$/', $value) === 1
            ? $value
            : null;
    }

    private static function generateId(): string
    {
        return bin2hex(random_bytes(16));
    }
}
