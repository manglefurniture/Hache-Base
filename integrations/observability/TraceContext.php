<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Observability;

final class TraceContext
{
    private function __construct(
        private readonly string $traceId,
        private readonly string $spanId,
        private readonly ?string $parentSpanId,
        private readonly bool $sampled,
    ) {
    }

    public static function root(bool $sampled = true): self
    {
        return new self(self::randomHex(16), self::randomHex(8), null, $sampled);
    }

    public static function childOf(self $parent): self
    {
        return new self(
            $parent->traceId,
            self::randomHex(8),
            $parent->spanId,
            $parent->sampled,
        );
    }

    /**
     * Parse a W3C traceparent v00 header as a remote parent context.
     *
     * Only lowercase fixed-width hexadecimal identifiers are accepted. Invalid
     * or all-zero identifiers are rejected instead of being propagated.
     */
    public static function fromTraceparent(?string $traceparent): ?self
    {
        if (!is_string($traceparent)) {
            return null;
        }

        $traceparent = trim($traceparent);
        if (preg_match('/^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/', $traceparent, $matches) !== 1) {
            return null;
        }

        [, $traceId, $remoteSpanId, $flags] = $matches;
        if (self::isAllZero($traceId) || self::isAllZero($remoteSpanId)) {
            return null;
        }

        return new self(
            $traceId,
            $remoteSpanId,
            null,
            (hexdec($flags) & 0x01) === 0x01,
        );
    }

    public function traceId(): string
    {
        return $this->traceId;
    }

    public function spanId(): string
    {
        return $this->spanId;
    }

    public function parentSpanId(): ?string
    {
        return $this->parentSpanId;
    }

    public function sampled(): bool
    {
        return $this->sampled;
    }

    /**
     * Header value to propagate this local span as the parent downstream.
     */
    public function traceparent(): string
    {
        return sprintf(
            '00-%s-%s-%s',
            $this->traceId,
            $this->spanId,
            $this->sampled ? '01' : '00',
        );
    }

    /** @return array{trace_id: string, span_id: string, parent_span_id: ?string, sampled: bool} */
    public function toArray(): array
    {
        return [
            'trace_id' => $this->traceId,
            'span_id' => $this->spanId,
            'parent_span_id' => $this->parentSpanId,
            'sampled' => $this->sampled,
        ];
    }

    private static function randomHex(int $bytes): string
    {
        return bin2hex(random_bytes($bytes));
    }

    private static function isAllZero(string $identifier): bool
    {
        return trim($identifier, '0') === '';
    }
}
