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

        if (!self::isAllowedTimezone($name)) {
            throw new InvalidArgumentException(
                'Invalid application timezone. Use UTC or an IANA region identifier such as America/Cancun.'
            );
        }

        try {
            return new DateTimeZone($name);
        } catch (Throwable $e) {
            throw new InvalidArgumentException('Invalid application timezone: ' . $name, 0, $e);
        }
    }

    private static function isAllowedTimezone(string $name): bool
    {
        if ($name === 'UTC') {
            return true;
        }

        // Reject ambiguous abbreviations (EST/CST) and fixed offsets (+05:00).
        // Business timezones must be region-based IANA identifiers such as America/Cancun.
        if (!str_contains($name, '/')) {
            return false;
        }

        static $identifiers = null;
        if ($identifiers === null) {
            $identifiers = array_fill_keys(DateTimeZone::listIdentifiers(DateTimeZone::ALL_WITH_BC), true);
        }

        return isset($identifiers[$name]);
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
