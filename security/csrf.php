<?php

declare(strict_types=1);

namespace HacheBase\Security;

final class Csrf
{
    private const SESSION_KEY = '_csrf_token';

    public static function token(): string
    {
        Auth::startSecureSession();

        if (empty($_SESSION[self::SESSION_KEY])) {
            $_SESSION[self::SESSION_KEY] = bin2hex(random_bytes(32));
        }

        return (string)$_SESSION[self::SESSION_KEY];
    }

    public static function validate(?string $token): bool
    {
        Auth::startSecureSession();
        $expected = $_SESSION[self::SESSION_KEY] ?? '';

        return is_string($token)
            && is_string($expected)
            && $expected !== ''
            && hash_equals($expected, $token);
    }

    public static function requireValid(?string $token): void
    {
        if (!self::validate($token)) {
            http_response_code(419);
            exit('Invalid CSRF token');
        }
    }
}
