<?php

declare(strict_types=1);

namespace HacheBase\Audit;

final class AuditSanitizer
{
    private const SENSITIVE_KEYS = [
        'password', 'password_hash', 'token', 'access_token', 'refresh_token',
        'authorization', 'cookie', 'secret', 'api_key', 'card_number', 'cvv',
    ];

    public static function sanitize(array $data): array
    {
        $clean = [];

        foreach ($data as $key => $value) {
            $normalizedKey = strtolower((string) $key);

            if (in_array($normalizedKey, self::SENSITIVE_KEYS, true)) {
                $clean[$key] = '[REDACTED]';
                continue;
            }

            $clean[$key] = is_array($value) ? self::sanitize($value) : $value;
        }

        return $clean;
    }
}
