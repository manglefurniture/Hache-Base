<?php

declare(strict_types=1);

namespace HacheBase\Common;

use InvalidArgumentException;

/**
 * Small, transport-neutral contract for a metric or composed read model.
 *
 * It does not calculate business values, persist coverage, or decide whether
 * a project may publish a result. It makes the authority, cutoff, coverage,
 * and evidence limitations explicit at the boundary that presents a value.
 */
final class ReadModelContract
{
    public const AVAILABLE = 'available';
    public const NOT_AVAILABLE = 'not_available';
    public const OUT_OF_COVERAGE = 'out_of_coverage';
    public const NOT_EVALUATED = 'not_evaluated';
    public const NOT_APPLICABLE = 'not_applicable';
    public const INSUFFICIENT_EVIDENCE = 'insufficient_evidence';

    public const COVERAGE_COMPLETE = 'complete';
    public const COVERAGE_FORWARD_ONLY = 'forward_only';
    public const COVERAGE_OUT_OF_COVERAGE = 'out_of_coverage';
    public const COVERAGE_NOT_EVALUATED = 'not_evaluated';

    public const HUMAN_REVIEW_REQUIRED = 'human_review_required';

    /**
     * Declares coverage without inventing a storage model or a historical
     * backfill. A forward-only projection must name its explicit start.
     *
     * @return array{state:string,starts_at:?string,history_reconstructed:bool}
     */
    public static function coverage(
        string $state,
        ?string $startsAt,
        bool $historyReconstructed = false
    ): array {
        if (!in_array($state, self::coverageStates(), true)) {
            throw new InvalidArgumentException('Unknown read-model coverage state.');
        }

        $startsAt = self::optionalText($startsAt);
        if ($state === self::COVERAGE_FORWARD_ONLY && $startsAt === null) {
            throw new InvalidArgumentException('Forward-only coverage requires an explicit start marker.');
        }

        return [
            'state' => $state,
            'starts_at' => $startsAt,
            'history_reconstructed' => $historyReconstructed,
        ];
    }

    /**
     * Normalizes the presentation contract of a numeric metric. Zero is valid
     * only when the metric is available; unavailable evidence must stay null.
     *
     * @param array<string, mixed> $definition
     * @return array<string, mixed>
     */
    public static function metric(array $definition): array
    {
        foreach (['id', 'authority', 'numerator', 'denominator', 'exclusions', 'cutoff_at', 'timezone'] as $field) {
            self::requireText($definition, $field);
        }

        $cutoffAt = self::requireText($definition, 'cutoff_at');

        $availability = self::requireText($definition, 'availability');
        if (!in_array($availability, self::availabilityStates(), true)) {
            throw new InvalidArgumentException('Unknown metric availability state.');
        }

        if (!isset($definition['coverage']) || !is_array($definition['coverage'])) {
            throw new InvalidArgumentException('A metric must declare coverage.');
        }

        $coverage = self::coverage(
            self::requireText($definition['coverage'], 'state'),
            isset($definition['coverage']['starts_at']) ? (string) $definition['coverage']['starts_at'] : null,
            (bool) ($definition['coverage']['history_reconstructed'] ?? false),
        );

        $value = $definition['value'] ?? null;
        if ($availability === self::AVAILABLE) {
            if (!is_int($value) && !is_float($value)) {
                throw new InvalidArgumentException('An available metric requires a numeric value.');
            }

            if (in_array($coverage['state'], [self::COVERAGE_OUT_OF_COVERAGE, self::COVERAGE_NOT_EVALUATED], true)) {
                throw new InvalidArgumentException('An available metric cannot use unavailable coverage.');
            }

            if (
                $coverage['state'] === self::COVERAGE_FORWARD_ONLY
                && self::cutoffPrecedesCoverage($cutoffAt, $coverage['starts_at'])
            ) {
                throw new InvalidArgumentException('An available metric cannot predate forward-only coverage.');
            }
        } elseif ($value !== null) {
            throw new InvalidArgumentException('Unavailable evidence must not be represented as a numeric value.');
        }

        return [
            'id' => self::requireText($definition, 'id'),
            'authority' => self::requireText($definition, 'authority'),
            'numerator' => self::requireText($definition, 'numerator'),
            'denominator' => self::requireText($definition, 'denominator'),
            'exclusions' => self::requireText($definition, 'exclusions'),
            'cutoff_at' => $cutoffAt,
            'timezone' => self::requireText($definition, 'timezone'),
            'coverage' => $coverage,
            'availability' => $availability,
            'value' => $value,
        ];
    }

    /**
     * Declares the safety boundary of an operational evidence collector.
     * A collector may supply evidence, but never declares its own PASS.
     *
     * @param array<string, mixed> $evidence
     * @return array<string, string|bool>
     */
    public static function operationalEvidence(array $evidence): array
    {
        if (($evidence['read_only'] ?? false) !== true) {
            throw new InvalidArgumentException('Operational evidence collectors must be read-only.');
        }

        if (($evidence['pii_minimized'] ?? false) !== true) {
            throw new InvalidArgumentException('Operational evidence collectors must minimize personal data.');
        }

        if (self::requireText($evidence, 'decision') !== self::HUMAN_REVIEW_REQUIRED) {
            throw new InvalidArgumentException('A collector must leave the decision to human review.');
        }

        $transaction = self::requireText($evidence, 'read_only_transaction');
        if (!in_array($transaction, ['completed', 'not_applicable', 'not_supported'], true)) {
            throw new InvalidArgumentException('Unknown read-only transaction status.');
        }

        return [
            'collector' => self::requireText($evidence, 'collector'),
            'observed_at' => self::requireText($evidence, 'observed_at'),
            'read_only' => true,
            'read_only_transaction' => $transaction,
            'pii_minimized' => true,
            'decision' => self::HUMAN_REVIEW_REQUIRED,
        ];
    }

    /** @return list<string> */
    private static function availabilityStates(): array
    {
        return [
            self::AVAILABLE,
            self::NOT_AVAILABLE,
            self::OUT_OF_COVERAGE,
            self::NOT_EVALUATED,
            self::NOT_APPLICABLE,
            self::INSUFFICIENT_EVIDENCE,
        ];
    }

    /** @return list<string> */
    private static function coverageStates(): array
    {
        return [
            self::COVERAGE_COMPLETE,
            self::COVERAGE_FORWARD_ONLY,
            self::COVERAGE_OUT_OF_COVERAGE,
            self::COVERAGE_NOT_EVALUATED,
        ];
    }

    /** @param array<string, mixed> $values */
    private static function requireText(array $values, string $field): string
    {
        $value = self::optionalText(isset($values[$field]) ? (string) $values[$field] : null);
        if ($value === null) {
            throw new InvalidArgumentException(sprintf('Read-model field "%s" is required.', $field));
        }

        return $value;
    }

    private static function optionalText(?string $value): ?string
    {
        $value = trim((string) $value);

        return $value === '' ? null : $value;
    }

    private static function cutoffPrecedesCoverage(string $cutoffAt, ?string $startsAt): bool
    {
        if ($startsAt === null) {
            return false;
        }

        try {
            return new \DateTimeImmutable($cutoffAt) < new \DateTimeImmutable($startsAt);
        } catch (\Throwable) {
            throw new InvalidArgumentException(
                'Forward-only coverage requires parseable cutoff_at and starts_at values.'
            );
        }
    }
}
