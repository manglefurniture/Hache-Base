<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Observability;

interface TelemetryExporter
{
    /**
     * Export one normalized telemetry record.
     *
     * This is the only provider-facing boundary. A project may implement it
     * with OpenTelemetry/APM, stdout, a local file or another owned sink.
     *
     * @param array<string, mixed> $record
     */
    public function export(array $record): void;
}
