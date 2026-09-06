<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Observability;

use HacheBase\Common\RequestContext;
use HacheBase\Common\StructuredLogger;
use InvalidArgumentException;
use Throwable;

require_once __DIR__ . '/TelemetryExporter.php';
require_once __DIR__ . '/TraceContext.php';
require_once __DIR__ . '/../../src/common/RequestContext.php';
require_once __DIR__ . '/../../src/common/StructuredLogger.php';

final class ObservabilityBridge
{
    private const SEVERITIES = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'];
    private const MAX_NAME_LENGTH = 160;
    private const ATTRIBUTE_REDACTED = '[REDACTED]';
    private const PRIVATE_ATTRIBUTE_FRAGMENTS = [
        'email',
        'phone',
        'address',
        'user_id',
        'customer_id',
        'client_id',
        'student_id',
        'ip_address',
        'user_agent',
        'referrer',
        'session_id',
        'query_string',
        'full_url',
    ];

    /** @var null|callable(Throwable): void */
    private $onExportFailure;

    public function __construct(
        private readonly string $service,
        private readonly string $environment,
        private readonly string $version,
        private readonly TelemetryExporter $exporter,
        private readonly bool $failOpen = true,
        ?callable $onExportFailure = null,
    ) {
        if (trim($service) === '' || trim($environment) === '' || trim($version) === '') {
            throw new InvalidArgumentException('service, environment and version are required.');
        }

        $this->onExportFailure = $onExportFailure;
    }

    public function event(
        string $severity,
        string $name,
        array $attributes = [],
        ?RequestContext $requestContext = null,
        ?TraceContext $traceContext = null,
    ): void {
        $severity = strtoupper(trim($severity));
        if (!in_array($severity, self::SEVERITIES, true)) {
            throw new InvalidArgumentException('Unsupported event severity.');
        }

        $record = $this->baseRecord('log', $name, $attributes, $requestContext, $traceContext);
        $record['severity'] = $severity;
        $this->emit($record);
    }

    public function counter(
        string $name,
        int|float $value = 1,
        array $attributes = [],
        ?RequestContext $requestContext = null,
        ?TraceContext $traceContext = null,
    ): void {
        if (!is_finite((float) $value) || $value < 0) {
            throw new InvalidArgumentException('Counter value must be finite and non-negative.');
        }

        $record = $this->baseRecord('metric', $name, $attributes, $requestContext, $traceContext);
        $record['metric_type'] = 'counter';
        $record['value'] = $value;
        $this->emit($record);
    }

    public function histogram(
        string $name,
        int|float $value,
        string $unit,
        array $attributes = [],
        ?RequestContext $requestContext = null,
        ?TraceContext $traceContext = null,
    ): void {
        if (!is_finite((float) $value)) {
            throw new InvalidArgumentException('Histogram value must be finite.');
        }

        $unit = trim($unit);
        if ($unit === '' || strlen($unit) > 32 || preg_match('/[\x00-\x1F\x7F]/', $unit) === 1) {
            throw new InvalidArgumentException('Histogram unit is invalid.');
        }

        $record = $this->baseRecord('metric', $name, $attributes, $requestContext, $traceContext);
        $record['metric_type'] = 'histogram';
        $record['value'] = $value;
        $record['unit'] = $unit;
        $this->emit($record);
    }

    /**
     * Measure one operation and emit one span record.
     *
     * The callback receives the local TraceContext and RequestContext so an
     * outbound adapter can propagate traceparent plus the existing correlation
     * headers. Telemetry export is fail-open by default.
     */
    public function measure(
        string $name,
        callable $operation,
        array $attributes = [],
        ?RequestContext $requestContext = null,
        ?TraceContext $parentTrace = null,
    ): mixed {
        $requestContext ??= RequestContext::fromServer();
        $localTrace = $parentTrace === null
            ? TraceContext::root()
            : TraceContext::childOf($parentTrace);

        $startNs = hrtime(true);
        $startedAt = self::nowUtc();

        try {
            $result = $operation($localTrace, $requestContext);
        } catch (Throwable $exception) {
            try {
                $this->emitSpan(
                    $name,
                    $startedAt,
                    $startNs,
                    'ERROR',
                    array_merge($attributes, ['exception_type' => $exception::class]),
                    $requestContext,
                    $localTrace,
                );
            } catch (Throwable) {
                // Never replace the original business exception with telemetry failure.
            }

            throw $exception;
        }

        $this->emitSpan(
            $name,
            $startedAt,
            $startNs,
            'OK',
            $attributes,
            $requestContext,
            $localTrace,
        );

        return $result;
    }

    private function emitSpan(
        string $name,
        string $startedAt,
        int $startNs,
        string $status,
        array $attributes,
        RequestContext $requestContext,
        TraceContext $traceContext,
    ): void {
        $record = $this->baseRecord('span', $name, $attributes, $requestContext, $traceContext);
        $record['started_at'] = $startedAt;
        $record['ended_at'] = self::nowUtc();
        $record['duration_ms'] = max(0, (hrtime(true) - $startNs) / 1_000_000);
        $record['status'] = $status;
        $this->emit($record);
    }

    /** @return array<string, mixed> */
    private function baseRecord(
        string $kind,
        string $name,
        array $attributes,
        ?RequestContext $requestContext,
        ?TraceContext $traceContext,
    ): array {
        $name = self::normalizeName($name);
        $requestContext ??= RequestContext::fromServer();
        $traceContext ??= TraceContext::root();

        return [
            'schema_version' => 1,
            'kind' => $kind,
            'timestamp' => self::nowUtc(),
            'service' => trim($this->service),
            'environment' => trim($this->environment),
            'version' => trim($this->version),
            'name' => $name,
            'request_id' => $requestContext->requestId(),
            'correlation_id' => $requestContext->correlationId(),
            ...$traceContext->toArray(),
            'attributes' => self::sanitizeAttributes(StructuredLogger::redact($attributes)),
        ];
    }

    /** @param array<string, mixed> $record */
    private function emit(array $record): void
    {
        try {
            $this->exporter->export($record);
        } catch (Throwable $exception) {
            if ($this->onExportFailure !== null) {
                try {
                    ($this->onExportFailure)($exception);
                } catch (Throwable) {
                    // Failure reporting must not create a second product-path failure.
                }
            }

            if (!$this->failOpen) {
                throw $exception;
            }
        }
    }

    private static function normalizeName(string $name): string
    {
        $name = trim($name);
        if (
            $name === ''
            || strlen($name) > self::MAX_NAME_LENGTH
            || preg_match('/[\x00-\x1F\x7F]/', $name) === 1
        ) {
            throw new InvalidArgumentException('Telemetry name is invalid.');
        }

        return $name;
    }

    private static function sanitizeAttributes(mixed $value, ?string $key = null): mixed
    {
        if ($key !== null) {
            $normalized = strtolower(str_replace(['-', '.'], '_', $key));
            foreach (self::PRIVATE_ATTRIBUTE_FRAGMENTS as $fragment) {
                if (str_contains($normalized, $fragment)) {
                    return self::ATTRIBUTE_REDACTED;
                }
            }
        }

        if (!is_array($value)) {
            return $value;
        }

        $sanitized = [];
        foreach ($value as $childKey => $childValue) {
            $sanitized[$childKey] = self::sanitizeAttributes(
                $childValue,
                is_string($childKey) ? $childKey : null,
            );
        }

        return $sanitized;
    }

    private static function nowUtc(): string
    {
        return gmdate('Y-m-d\TH:i:s\Z');
    }
}
