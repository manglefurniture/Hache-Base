<?php

declare(strict_types=1);

namespace HacheBase\Security;

final class Auth
{
    public static function startSecureSession(): void
    {
        if (session_status() === PHP_SESSION_ACTIVE) {
            return;
        }

        $secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off');

        session_set_cookie_params([
            'httponly' => true,
            'secure' => $secure,
            'samesite' => 'Lax',
        ]);

        session_start();
    }

    public static function requireUser(): array
    {
        self::startSecureSession();

        $user = $_SESSION['user'] ?? null;

        if (!is_array($user) || empty($user['id'])) {
            http_response_code(401);
            exit('Unauthorized');
        }

        return $user;
    }

    public static function user(): ?array
    {
        self::startSecureSession();
        $user = $_SESSION['user'] ?? null;

        return is_array($user) ? $user : null;
    }

    public static function logout(): void
    {
        self::startSecureSession();
        $_SESSION = [];

        if (ini_get('session.use_cookies')) {
            $params = session_get_cookie_params();
            setcookie(session_name(), '', time() - 42000, $params['path'], $params['domain'], (bool)$params['secure'], (bool)$params['httponly']);
        }

        session_destroy();
    }
}
