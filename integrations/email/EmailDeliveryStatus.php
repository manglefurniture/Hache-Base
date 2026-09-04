<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Email;

use InvalidArgumentException;
use RuntimeException;

final class EmailDeliveryStatus
{
    public const REQUESTED = 'requested';
    public const ACCEPTED = 'accepted';
    public const DELAYED = 'delayed';
    public const DELIVERED = 'delivered';
    public const BOUNCED = 'bounced';
    public const FAILED = 'failed';
    public const SUPPRESSED = 'suppressed';

    private const ALLOWED = [
        self::REQUESTED,
        self::ACCEPTED,
        self::DELAYED,
        self::DELIVERED,
        self::BOUNCED,
        self::FAILED,
        self::SUPPRESSED,
    ];

    private const TERMINAL = [
        self::DELIVERED,
        self::BOUNCED,
        self::FAILED,
        self::SUPPRESSED,
    ];

    private const PROGRESS_RANK = [
        self::REQUESTED => 0,
        self::ACCEPTED => 1,
        self::DELAYED => 2,
        self::DELIVERED => 3,
        self::BOUNCED => 3,
        self::FAILED => 3,
        self::SUPPRESSED => 3,
    ];

    public static function assertValid(string $status): void
    {
        if (!in_array($status, self::ALLOWED, true)) {
            throw new InvalidArgumentException('Estado de entrega de correo no soportado: ' . $status);
        }
    }

    public static function isTerminal(string $status): bool
    {
        self::assertValid($status);
        return in_array($status, self::TERMINAL, true);
    }

    /**
     * Decide si un evento debe reemplazar la proyección actual.
     *
     * La fecha usada es la fecha del evento declarada por el proveedor, no la hora
     * local de recepción. Los DATETIME(6) persistidos por la Extension se interpretan
     * explícitamente como UTC; timestamps con offset conservan su offset real.
     * Un evento anterior no degrada la proyección. Estados terminales distintos nunca
     * se pisan automáticamente: requieren reconciliación. Tampoco se permite volver
     * de delayed a accepted/requested por entrega fuera de orden.
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
            return self::unchanged($currentStatus, $currentOccurredAt, 'stale_event');
        }

        if ($incomingStatus === $currentStatus) {
            return self::unchanged($currentStatus, $currentOccurredAt, 'duplicate_state');
        }

        if ($incomingTs === $currentTs) {
            return self::unchanged($currentStatus, $currentOccurredAt, 'same_timestamp_conflict');
        }

        if (self::isTerminal($currentStatus)) {
            return self::unchanged($currentStatus, $currentOccurredAt, 'terminal_conflict');
        }

        if (self::PROGRESS_RANK[$incomingStatus] < self::PROGRESS_RANK[$currentStatus]) {
            return self::unchanged($currentStatus, $currentOccurredAt, 'state_regression');
        }

        return [
            'status' => $incomingStatus,
            'occurred_at' => $incomingOccurredAt,
            'applied' => true,
            'reason' => 'newer_event',
        ];
    }

    /** @return array{status:string,occurred_at:string,applied:bool,reason:string} */
    private static function unchanged(string $status, string $occurredAt, string $reason): array
    {
        return [
            'status' => $status,
            'occurred_at' => $occurredAt,
            'applied' => false,
            'reason' => $reason,
        ];
    }

    private static function parseTimestamp(string $value): float
    {
        $value = trim($value);
        if ($value === '') {
            throw new InvalidArgumentException('La fecha del evento de correo no puede estar vacía.');
        }

        $date = null;
        if (preg_match('/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?$/', $value, $parts)) {
            $micros = str_pad($parts[3] ?? '', 6, '0');
            $normalized = $parts[1] . ' ' . $parts[2] . '.' . $micros;
            $date = \DateTimeImmutable::createFromFormat(
                '!Y-m-d H:i:s.u',
                $normalized,
                new \DateTimeZone('UTC'),
            );
            self::assertNoDateParseErrors($date);
        } else {
            try {
                $date = new \DateTimeImmutable($value);
            } catch (\Throwable $e) {
                throw new InvalidArgumentException('La fecha del evento de correo no es válida.', 0, $e);
            }
            self::assertNoDateParseErrors($date);
        }

        $seconds = (float) $date->format('U.u');
        if (!is_finite($seconds)) {
            throw new RuntimeException('No se pudo normalizar la fecha del evento de correo.');
        }

        return $seconds;
    }

    private static function assertNoDateParseErrors(\DateTimeImmutable|false $date): void
    {
        $errors = \DateTimeImmutable::getLastErrors();
        if ($date === false
            || ($errors !== false && ($errors['warning_count'] > 0 || $errors['error_count'] > 0))) {
            throw new InvalidArgumentException('La fecha del evento de correo no es válida.');
        }
    }
}
