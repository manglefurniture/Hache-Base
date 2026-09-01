<?php

declare(strict_types=1);

namespace HacheBase\Security;

use InvalidArgumentException;

require_once __DIR__ . '/session-security.php';

final class Auth
{
    /**
     * Source-compatible wrapper around the SEC-007 session contract.
     *
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     */
    public static function startSecureSession(
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): void {
        SessionSecurity::start($sessionConfig, $server, $now);
    }

    /**
     * Establish an authenticated user after credentials have already been verified.
     * Regenerates the session ID before attaching authenticated state.
     *
     * @param array<string, mixed> $user
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     */
    public static function login(
        array $user,
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): void {
        self::assertUserIdentity($user);
        self::startSecureSession($sessionConfig, $server, $now);
        SessionSecurity::regenerateForAuthentication($now);
        $_SESSION['user'] = $user;
    }

    /**
     * Replace authenticated state after an already-authorized privilege change.
     * This method does not decide whether the elevation is allowed; it only rotates
     * the session ID so old identifiers cannot retain the previous trust boundary.
     *
     * @param array<string, mixed> $user
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     */
    public static function elevate(
        array $user,
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): void {
        self::assertUserIdentity($user);
        self::startSecureSession($sessionConfig, $server, $now);
        SessionSecurity::regenerateForPrivilegeChange($now);
        $_SESSION['user'] = $user;
    }

    /**
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     * @return array<string, mixed>
     */
    public static function requireUser(
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): array {
        self::startSecureSession($sessionConfig, $server, $now);

        $user = $_SESSION['user'] ?? null;

        if (!is_array($user) || empty($user['id'])) {
            http_response_code(401);
            exit('Unauthorized');
        }

        return $user;
    }

    /**
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     * @return array<string, mixed>|null
     */
    public static function user(
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): ?array {
        self::startSecureSession($sessionConfig, $server, $now);
        $user = $_SESSION['user'] ?? null;

        return is_array($user) ? $user : null;
    }

    /**
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     */
    public static function logout(
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): void {
        self::startSecureSession($sessionConfig, $server, $now);
        SessionSecurity::destroy();
    }

    /**
     * @param array<string, mixed> $user
     */
    private static function assertUserIdentity(array $user): void
    {
        if (!array_key_exists('id', $user) || $user['id'] === null || $user['id'] === '') {
            throw new InvalidArgumentException('Authenticated user must contain a non-empty id.');
        }
    }
}
