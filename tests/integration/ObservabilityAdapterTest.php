<?php

declare(strict_types=1);

use HacheBase\Common\RequestContext;
use HacheBase\Integrations\Observability\ObservabilityBridge;
use HacheBase\Integrations\Observability\TelemetryExporter;
use HacheBase\Integrations\Observability\TraceContext;

require_once __DIR__ . '/../../integrations/observability/ObservabilityBridge.php';

final class MemoryTelemetryExporter implements TelemetryExporter
{
    /** @var list<array<string, mixed>> */
    public array $records = [];

    public function export(array $record): void
    {
        $this->records[] = $record;
    }
}

final class ThrowingTelemetryExporter implements TelemetryExporter
{
    public function export(array $record): void
    {
        throw new RuntimeException('export unavailable');
    }
}

$incoming = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01';
$remote = TraceContext::fromTraceparent($incoming);
assert($remote !== null);
assert($remote->traceId() === '4bf92f3577b34da6a3ce929d0e0e4736');
assert($remote->spanId() === '00f067aa0ba902b7');
assert($remote->parentSpanId() === null);
assert($remote->sampled() === true);
assert($remote->traceparent() === $incoming);

$child = TraceContext::childOf($remote);
assert($child->traceId() === $remote->traceId());
assert($child->spanId() !== $remote->spanId());
assert($child->parentSpanId() === $remote->spanId());
assert(preg_match('/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/', $child->traceparent()) === 1);

assert(TraceContext::fromTraceparent(null) === null);
assert(TraceContext::fromTraceparent('00-00000000000000000000000000000000-00f067aa0ba902b7-01') === null);
assert(TraceContext::fromTraceparent('00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01') === null);
assert(TraceContext::fromTraceparent(strtoupper($incoming)) === null);
assert(TraceContext::fromTraceparent('ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01') === null);

$requestContext = RequestContext::create('req-observe-1', 'corr-observe-1');
$exporter = new MemoryTelemetryExporter();
$bridge = new ObservabilityBridge('fixture-service', 'test', 'git-test', $exporter);

// A boundary-scoped default may be injected once and reused for records in that
// request/job. A bridge without that boundary must reject omitted context rather
// than caching an identifier across persistent worker requests.
$boundaryContext = RequestContext::create('req-boundary-1', 'corr-boundary-1');
$boundaryExporter = new MemoryTelemetryExporter();
$boundaryBridge = new ObservabilityBridge(
    'fixture-service',
    'test',
    'git-test',
    $boundaryExporter,
    true,
    null,
    $boundaryContext,
);
$boundaryBridge->event('info', 'fixture.boundary_context.event');
$boundaryBridge->counter('fixture.boundary_context.counter');
assert(count($boundaryExporter->records) === 2);
assert($boundaryExporter->records[0]['request_id'] === 'req-boundary-1');
assert($boundaryExporter->records[1]['request_id'] === 'req-boundary-1');
assert($boundaryExporter->records[0]['correlation_id'] === 'corr-boundary-1');
assert($boundaryExporter->records[1]['correlation_id'] === 'corr-boundary-1');

$missingContextExporter = new MemoryTelemetryExporter();
$missingContextBridge = new ObservabilityBridge('fixture-service', 'test', 'git-test', $missingContextExporter);
try {
    $missingContextBridge->event('info', 'fixture.missing_context');
    assert(false, 'Expected missing RequestContext failure.');
} catch (InvalidArgumentException $exception) {
    assert(str_contains($exception->getMessage(), 'RequestContext is required'));
}
assert($missingContextExporter->records === []);

$dangerousObject = new class implements JsonSerializable {
    public function jsonSerialize(): mixed
    {
        return ['token' => 'must-not-leak'];
    }
};

$bridge->event('info', 'fixture.requested', [
    'safe' => 'visible',
    'token' => 'must-not-leak-token',
    'email' => 'person@example.com',
    'nested' => ['phone' => '+529981234567'],
    'object' => $dangerousObject,
], $requestContext, $child);

assert(count($exporter->records) === 1);
$event = $exporter->records[0];
assert($event['schema_version'] === 1);
assert($event['kind'] === 'log');
assert($event['severity'] === 'INFO');
assert($event['service'] === 'fixture-service');
assert($event['environment'] === 'test');
assert($event['version'] === 'git-test');
assert($event['request_id'] === 'req-observe-1');
assert($event['correlation_id'] === 'corr-observe-1');
assert($event['trace_id'] === $child->traceId());
assert($event['span_id'] === $child->spanId());
assert($event['attributes']['safe'] === 'visible');
assert($event['attributes']['token'] === '[REDACTED]');
assert($event['attributes']['email'] === '[REDACTED]');
assert($event['attributes']['nested']['phone'] === '[REDACTED]');
assert($event['attributes']['object'] === '[OBJECT_REDACTED]');
$eventJson = json_encode($event, JSON_THROW_ON_ERROR);
assert(!str_contains($eventJson, 'must-not-leak'));
assert(!str_contains($eventJson, 'person@example.com'));
assert(!str_contains($eventJson, '+529981234567'));

$bridge->counter('fixture.requests', 2, ['route_template' => '/fixture/{id}'], $requestContext, $child);
$counter = $exporter->records[1];
assert($counter['kind'] === 'metric');
assert($counter['metric_type'] === 'counter');
assert($counter['value'] === 2);
assert($counter['attributes']['route_template'] === '/fixture/{id}');

$bridge->histogram('fixture.latency', 12.5, 'ms', ['provider' => 'fixture'], $requestContext, $child);
$histogram = $exporter->records[2];
assert($histogram['metric_type'] === 'histogram');
assert($histogram['value'] === 12.5);
assert($histogram['unit'] === 'ms');

$localTrace = null;
$result = $bridge->measure(
    'fixture.operation',
    static function (TraceContext $trace, RequestContext $context) use (&$localTrace, $remote): int {
        $localTrace = $trace;
        assert($trace->traceId() === $remote->traceId());
        assert($trace->parentSpanId() === $remote->spanId());
        assert($context->requestId() === 'req-observe-1');
        return 42;
    },
    ['cuf' => 'fixture'],
    $requestContext,
    $remote,
);
assert($result === 42);
assert($localTrace instanceof TraceContext);
$span = $exporter->records[3];
assert($span['kind'] === 'span');
assert($span['status'] === 'OK');
assert($span['trace_id'] === $remote->traceId());
assert($span['parent_span_id'] === $remote->spanId());
assert(is_float($span['duration_ms']) || is_int($span['duration_ms']));
assert($span['duration_ms'] >= 0);

try {
    $bridge->measure(
        'fixture.failed',
        static function (): never {
            throw new DomainException('business message must not enter telemetry');
        },
        ['safe' => 'failure'],
        $requestContext,
        $remote,
    );
    assert(false, 'Expected business exception.');
} catch (DomainException $exception) {
    assert($exception->getMessage() === 'business message must not enter telemetry');
}

$failedSpan = $exporter->records[4];
assert($failedSpan['kind'] === 'span');
assert($failedSpan['status'] === 'ERROR');
assert($failedSpan['attributes']['exception_type'] === DomainException::class);
assert(!str_contains(json_encode($failedSpan, JSON_THROW_ON_ERROR), 'business message must not enter telemetry'));

// An invalid telemetry name must be rejected before the business callback runs.
$invalidMeasureExecuted = false;
try {
    $bridge->measure(
        "fixture\ninvalid",
        static function () use (&$invalidMeasureExecuted): int {
            $invalidMeasureExecuted = true;
            return 1;
        },
        [],
        $requestContext,
        $remote,
    );
    assert(false, 'Expected invalid span name failure.');
} catch (InvalidArgumentException) {
    // Expected.
}
assert($invalidMeasureExecuted === false);
assert(count($exporter->records) === 5);

$failureCount = 0;
$failOpenBridge = new ObservabilityBridge(
    'fixture-service',
    'test',
    'git-test',
    new ThrowingTelemetryExporter(),
    true,
    static function (Throwable $exception) use (&$failureCount): void {
        assert($exception instanceof RuntimeException);
        $failureCount++;
    },
);
$failOpenBridge->event('warn', 'fixture.export_failed', [], $requestContext, $child);
assert($failureCount === 1);

$strictBridge = new ObservabilityBridge(
    'fixture-service',
    'test',
    'git-test',
    new ThrowingTelemetryExporter(),
    false,
);
try {
    $strictBridge->event('error', 'fixture.strict_export', [], $requestContext, $child);
    assert(false, 'Expected strict export failure.');
} catch (RuntimeException $exception) {
    assert($exception->getMessage() === 'export unavailable');
}

try {
    $strictBridge->measure(
        'fixture.original_error',
        static function (): never {
            throw new LogicException('original business error');
        },
        [],
        $requestContext,
        $remote,
    );
    assert(false, 'Expected original business failure.');
} catch (LogicException $exception) {
    assert($exception->getMessage() === 'original business error');
}

foreach (
    [
        static fn () => $bridge->counter('fixture.bad_counter', -1),
        static fn () => $bridge->histogram('fixture.bad_histogram', INF, 'ms'),
        static fn () => $bridge->event('verbose', 'fixture.bad_severity'),
        static fn () => $bridge->event('info', "fixture\nbad_name"),
    ] as $invalidOperation
) {
    try {
        $invalidOperation();
        assert(false, 'Expected InvalidArgumentException.');
    } catch (InvalidArgumentException) {
        // Expected.
    }
}

echo "OBSERVABILITY_ADAPTER_OK\n";
