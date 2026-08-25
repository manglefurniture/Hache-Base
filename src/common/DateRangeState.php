<?php

declare(strict_types=1);

namespace HacheBase\Common;

use DateTimeImmutable;
use DateTimeZone;
use InvalidArgumentException;
use Throwable;

final class DateRangeState
{
    public const FUTURE = 'FUTURE';
    public const ACTIVE = 'ACTIVE';
    public const ENDED = 'ENDED';

    public static function classify(
        string $startDate,
        string $endDate,
        ?DateTimeImmutable $reference = null,
        ?string $timezone = null
    ): string {
        $tz = self::timezone($timezone);
        $start = self::date($startDate, $tz);
        $end = self::date($endDate, $tz);

        if ($start > $end) {
            throw new InvalidArgumentException('Start date must not be after end date.');
        }

        $today = $reference === null
            ? self::operationalToday($timezone)
            : $reference->setTimezone($tz)->setTime(0, 0, 0);

        if ($today < $start) {
            return self::FUTURE;
        }

        if ($today <= $end) {
            return self::ACTIVE;
        }

        return self::ENDED;
    }

    public static function operationalToday(
        ?string $timezone = null,
        ?DateTimeImmutable $now = null
    ): DateTimeImmutable {
        $tz = self::timezone($timezone);
        $current = $now === null
            ? new DateTimeImmutable('now', $tz)
            : $now->setTimezone($tz);

        return $current->setTime(0, 0, 0);
    }

    private static function timezone(?string $timezone): DateTimeZone
    {
        $name = trim((string)($timezone ?? getenv('APP_TIMEZONE') ?: 'UTC'));
        if ($name === '') {
            $name = 'UTC';
        }

        try {
            return new DateTimeZone($name);
        } catch (Throwable $e) {
            throw new InvalidArgumentException('Invalid application timezone: ' . $name, 0, $e);
        }
    }

    private static function date(string $value, DateTimeZone $timezone): DateTimeImmutable
    {
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value, $timezone);
        $errors = DateTimeImmutable::getLastErrors();

        if (
            $date === false
            || $date->format('Y-m-d') !== $value
            || (is_array($errors) && ($errors['warning_count'] > 0 || $errors['error_count'] > 0))
        ) {
            throw new InvalidArgumentException('Invalid date. Expected YYYY-MM-DD.');
        }

        return $date;
    }
}
