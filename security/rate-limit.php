<?php

declare(strict_types=1);

namespace HacheBase\Security;

final class RateLimit
{
    public static function requireWithin(string $key, int $maxAttempts, int $windowSeconds): void
    {
        Auth::startSecureSession();

        $bucketKey = '_rate_limit_' . hash('sha256', $key);
        $now = time();
        $bucket = $_SESSION[$bucketKey] ?? [
            'count' => 0,
            'reset_at' => $now + $windowSeconds,
        ];

        if (($bucket['reset_at'] ?? 0) <= $now) {
            $bucket = [
                'count' => 0,
                'reset_at' => $now + $windowSeconds,
            ];
        }

        $bucket['count'] = (int)($bucket['count'] ?? 0) + 1;
        $_SESSION[$bucketKey] = $bucket;

        if ($bucket['count'] > $maxAttempts) {
            $retryAfter = max(1, (int)$bucket['reset_at'] - $now);
            http_response_code(429);
            header('Retry-After: ' . $retryAfter);
            exit('Too Many Requests');
        }
    }
}
