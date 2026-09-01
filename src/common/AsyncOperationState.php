<?php

declare(strict_types=1);

namespace HacheBase\Common;

use InvalidArgumentException;

/**
 * Neutral lifecycle contract for asynchronous/external operations.
 *
 * It intentionally does not persist data or call providers. Projects may map
 * provider-specific statuses to these states when they adopt the pattern.
 */
final class AsyncOperationState
{
    public const REQUESTED = 'requested';
    public const ACCEPTED = 'accepted';
    public const OUTCOME_UNKNOWN = 'outcome_unknown';
    public const RETRY_PENDING = 'retry_pending';
    public const RECONCILING = 'reconciling';
    public const CONFIRMED = 'confirmed';
    public const FAILED_FINAL = 'failed_final';
    public const CANCELLED = 'cancelled';

    /** @var list<string> */
    private const STATES = [
        self::REQUESTED,
        self::ACCEPTED,
        self::OUTCOME_UNKNOWN,
        self::RETRY_PENDING,
        self::RECONCILING,
        self::CONFIRMED,
        self::FAILED_FINAL,
        self::CANCELLED,
    ];

    /** @var array<string, list<string>> */
    private const TRANSITIONS = [
        self::REQUESTED => [
            self::ACCEPTED,
            self::OUTCOME_UNKNOWN,
            self::RETRY_PENDING,
            self::CONFIRMED,
            self::FAILED_FINAL,
            self::CANCELLED,
        ],
        self::ACCEPTED => [
            self::OUTCOME_UNKNOWN,
            self::RECONCILING,
            self::CONFIRMED,
            self::FAILED_FINAL,
        ],
        self::OUTCOME_UNKNOWN => [
            self::RECONCILING,
            self::CONFIRMED,
            self::FAILED_FINAL,
        ],
        self::RETRY_PENDING => [
            self::REQUESTED,
            self::CANCELLED,
        ],
        self::RECONCILING => [
            self::OUTCOME_UNKNOWN,
            self::RETRY_PENDING,
            self::CONFIRMED,
            self::FAILED_FINAL,
        ],
        self::CONFIRMED => [],
        self::FAILED_FINAL => [],
        self::CANCELLED => [],
    ];

    public static function isKnown(string $state): bool
    {
        return in_array($state, self::STATES, true);
    }

    public static function isTerminal(string $state): bool
    {
        self::assertKnown($state);

        return in_array($state, [self::CONFIRMED, self::FAILED_FINAL, self::CANCELLED], true);
    }

    public static function isAuthoritativeSuccess(string $state): bool
    {
        self::assertKnown($state);

        return $state === self::CONFIRMED;
    }

    public static function requiresFollowUp(string $state): bool
    {
        self::assertKnown($state);

        return !self::isTerminal($state);
    }

    public static function mayRetry(string $state): bool
    {
        self::assertKnown($state);

        return $state === self::RETRY_PENDING;
    }

    public static function canTransition(string $from, string $to): bool
    {
        self::assertKnown($from);
        self::assertKnown($to);

        return in_array($to, self::TRANSITIONS[$from], true);
    }

    public static function assertTransition(string $from, string $to): void
    {
        if (!self::canTransition($from, $to)) {
            throw new InvalidArgumentException(sprintf(
                'Invalid async operation transition: %s -> %s',
                $from,
                $to,
            ));
        }
    }

    private static function assertKnown(string $state): void
    {
        if (!self::isKnown($state)) {
            throw new InvalidArgumentException(sprintf('Unknown async operation state: %s', $state));
        }
    }
}
