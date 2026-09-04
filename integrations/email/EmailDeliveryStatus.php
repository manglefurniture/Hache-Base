<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Email;

use InvalidArgumentException;
use RuntimeException;

final class EmailDeliveryStatus
{
    public const ACCEPTED = 'accepted';
    public const DELIVERED = 'delivered';
    public const DELAYED = 'delayed';
    public const BOUNCED = 'bounced';
    public const FAILED = 'failed';

    private const ALLOWED = [
        self::ACCEPTED,
        self::DELIVERED,
        self::DELAYED,
        self::BOUNCED,
        self::FAILED,
    ];

    public static function assertValid(string $status): void
    {
        if (!in_array($status, self::ALLOWED, true)) {
            throw new InvalidArgumentException('Estado de entrega de correo no soportado: ' . $status);
        }
    }

    /**
     * Decide si un evento debe reemplazar la proyección actual.
     *
     * La fecha usada es la fecha del evento declarada por el proveedor, no la hora
     * local de recepción. Un evento anterior no degrada la proyección. Dos estados
     * distintos con exactamente la misma marca temporal se consideran ambiguos y
     * requieren reconciliación en lugar de elegir una prioridad inventada.
     *
     * @return array{status:string,occurred_at:string,applied:bool,reason:string}
     */
    public static function apply(
        string $currentStatus,
        string $currentOccurredAt,
        string $incomingStatus,
        string $incomingOccurredAt,
    ): array {
        self::assertValid($currentStatus);
        self::assertValid($incomingStatus);

        $currentTs = self::parseTimestamp($currentOccurredAt);
        $incomingTs = self::parseTimestamp($incomingOccurredAt);

        if ($incomingTs < $currentTs) {
            return [
                'status' => $currentStatus,
                'occurred_at' => $currentOccurredAt,
                'applied' => false,
                'reason' => 'stale_event',
            ];
        }

        if ($incomingTs === $currentTs) {
            if ($incomingStatus === $currentStatus) {
                return [
                    'status' => $currentStatus,
                    'occurred_at' => $currentOccurredAt,
                    'applied' => false,
                    'reason' => 'duplicate_state',
                ];
            }

            return [
                'status' => $currentStatus,
                'occurred_at' => $currentOccurredAt,
                'applied' => false,
                'reason' => 'same_timestamp_conflict',
            ];
        }

        return [
            'status' => $incomingStatus,
            'occurred_at' => $incomingOccurredAt,
            'applied' => true,
            'reason' => 'newer_event',
        ];
    }

    private static function parseTimestamp(string $value): float
    {
        $value = trim($value);
        if ($value === '') {
            throw new InvalidArgumentException('La fecha del evento de correo no puede estar vacía.');
        }

        try {
            $date = new \DateTimeImmutable($value);
        } catch (\Throwable $e) {
            throw new InvalidArgumentException('La fecha del evento de correo no es válida.', 0, $e);
        }

        $seconds = (float) $date->format('U.u');
        if (!is_finite($seconds)) {
            throw new RuntimeException('No se pudo normalizar la fecha del evento de correo.');
        }

        return $seconds;
    }
}
