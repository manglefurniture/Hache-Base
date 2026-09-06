<?php

declare(strict_types=1);

namespace HacheBase\Tests\Fixtures\Failures;

use InvalidArgumentException;
use RuntimeException;

/**
 * Deterministic, test-only failure metadata.
 *
 * The fixture describes what failed; it deliberately does not decide whether a
 * project may retry, reconcile or fail permanently. Those decisions depend on
 * the CUF, idempotency contract and authoritative provider/storage semantics.
 */
final class FailureFixtureException extends RuntimeException
{
    public const TIMEOUT = 'timeout';
    public const HTTP_429 = 'http_429';
    public const HTTP_5XX = 'http_5xx';
    public const DNS = 'dns';
    public const STORAGE = 'storage';

    public const PHASE_CONNECT = 'connect';
    public const PHASE_OPERATION = 'operation';
    public const PHASE_RESPONSE = 'response';
    public const PHASE_STORAGE = 'storage';

    private function __construct(
        private readonly string $category,
        private readonly string $phase,
        private readonly ?int $httpStatus = null,
        private readonly ?int $retryAfterSeconds = null,
    ) {
        parent::__construct(sprintf('fixture failure: %s (%s)', $category, $phase));
    }

    public static function timeout(): self
    {
        return new self(self::TIMEOUT, self::PHASE_OPERATION);
    }

    public static function http429(int $retryAfterSeconds): self
    {
        if ($retryAfterSeconds < 0) {
            throw new InvalidArgumentException('retryAfterSeconds must be non-negative.');
        }

        return new self(
            self::HTTP_429,
            self::PHASE_RESPONSE,
            429,
            $retryAfterSeconds,
        );
    }

    public static function http5xx(int $status = 503): self
    {
        if ($status < 500 || $status > 599) {
            throw new InvalidArgumentException('HTTP 5xx fixture status must be between 500 and 599.');
        }

        return new self(self::HTTP_5XX, self::PHASE_RESPONSE, $status);
    }

    public static function dns(): self
    {
        return new self(self::DNS, self::PHASE_CONNECT);
    }

    public static function storage(): self
    {
        return new self(self::STORAGE, self::PHASE_STORAGE);
    }

    public function category(): string
    {
        return $this->category;
    }

    public function phase(): string
    {
        return $this->phase;
    }

    public function httpStatus(): ?int
    {
        return $this->httpStatus;
    }

    public function retryAfterSeconds(): ?int
    {
        return $this->retryAfterSeconds;
    }

    /** @return array{category: string, phase: string, http_status: ?int, retry_after_seconds: ?int} */
    public function metadata(): array
    {
        return [
            'category' => $this->category,
            'phase' => $this->phase,
            'http_status' => $this->httpStatus,
            'retry_after_seconds' => $this->retryAfterSeconds,
        ];
    }
}

/**
 * Scripted failure harness with no network, DNS, storage or sleep side effects.
 *
 * Each script step is either a FailureFixtureException (throw it) or null
 * (allow the supplied operation to run). Once the script is exhausted, the
 * operation runs normally. This makes retry/reconciliation tests fast and
 * reproducible without fault injection in production.
 */
final class FailureFixture
{
    /** @var list<FailureFixtureException|null> */
    private array $steps;
    private int $attempts = 0;

    /** @param list<FailureFixtureException|null> $steps */
    public function __construct(array $steps)
    {
        foreach ($steps as $index => $step) {
            if ($step !== null && !$step instanceof FailureFixtureException) {
                throw new InvalidArgumentException(sprintf(
                    'Failure fixture step %d must be FailureFixtureException or null.',
                    $index,
                ));
            }
        }

        $this->steps = array_values($steps);
    }

    public static function failOnce(FailureFixtureException $failure): self
    {
        return new self([$failure, null]);
    }

    public static function failRepeatedly(FailureFixtureException $failure, int $count): self
    {
        if ($count < 1) {
            throw new InvalidArgumentException('Failure repeat count must be at least 1.');
        }

        $steps = [];
        for ($i = 0; $i < $count; $i++) {
            // Each attempt gets an independent throwable with identical metadata.
            $steps[] = self::copyFailure($failure);
        }
        $steps[] = null;

        return new self($steps);
    }

    public function invoke(callable $operation): mixed
    {
        $stepIndex = $this->attempts;
        $this->attempts++;

        if (array_key_exists($stepIndex, $this->steps)) {
            $step = $this->steps[$stepIndex];
            if ($step instanceof FailureFixtureException) {
                throw $step;
            }
        }

        return $operation();
    }

    public function attempts(): int
    {
        return $this->attempts;
    }

    public function remainingScriptedSteps(): int
    {
        return max(0, count($this->steps) - $this->attempts);
    }

    private static function copyFailure(FailureFixtureException $failure): FailureFixtureException
    {
        return match ($failure->category()) {
            FailureFixtureException::TIMEOUT => FailureFixtureException::timeout(),
            FailureFixtureException::HTTP_429 => FailureFixtureException::http429(
                $failure->retryAfterSeconds() ?? 0,
            ),
            FailureFixtureException::HTTP_5XX => FailureFixtureException::http5xx(
                $failure->httpStatus() ?? 503,
            ),
            FailureFixtureException::DNS => FailureFixtureException::dns(),
            FailureFixtureException::STORAGE => FailureFixtureException::storage(),
            default => throw new InvalidArgumentException('Unknown fixture failure category.'),
        };
    }
}
