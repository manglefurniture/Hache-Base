<?php

declare(strict_types=1);

namespace HacheBase\Security;

final class Bearer
{
    public static function extractToken(): ?string
    {
        $header = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? null;

        if (!is_string($header) || !preg_match('/^Bearer\s+(.+)$/i', trim($header), $matches)) {
            return null;
        }

        $token = trim($matches[1]);
        return $token !== '' ? $token : null;
    }

    public static function validate(string $expectedToken): bool
    {
        $provided = self::extractToken();

        return $provided !== null
            && $expectedToken !== ''
            && hash_equals($expectedToken, $provided);
    }

    public static function requireValid(string $expectedToken): void
    {
        if (!self::validate($expectedToken)) {
            http_response_code(401);
            header('WWW-Authenticate: Bearer');
            exit('Unauthorized');
        }
    }
}
