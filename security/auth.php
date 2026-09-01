<?php

declare(strict_types=1);

namespace HacheBase\Security;

use InvalidArgumentException;
use LogicException;

require_once __DIR__ . '/session-security.php';

final class Auth
{
    /**
     * Request-local provenance marker. A session first opened through Hache Base may
     * later perform the controlled anonymous-policy migration in the same request.
     * A session that was already active before Hache Base touched it has unknown
     * browser-cookie provenance and must match the requested tuple exactly.
     */
    private static bool $sessionManagedInRequest = false;

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
        $effectiveServer = $server ?? $_SERVER;

        if (session_status() === PHP_SESSION_ACTIVE && !self::$sessionManagedInRequest) {
            self::assertPreActiveCookieTupleMatches($sessionConfig, $effectiveServer);
        }

        SessionSecurity::start($sessionConfig, $effectiveServer, $now);
        self::$sessionManagedInRequest = true;
    }

    /**
     * Establish an authenticated user after credentials have already been verified.
     * Regenerates the session ID before attaching authenticated state.
     *
     * User IDs are deliberately limited to int|string. Composite IDs must be
     * canonicalized by the project before crossing this security boundary.
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
     * Principal identity must remain exactly equal in both type and value. A project
     * that uses composite identifiers must canonicalize them to int|string first.
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

        $current = $_SESSION['user'] ?? null;
        if (!is_array($current) || !self::hasValidUserIdentity($current)) {
            throw new LogicException('Privilege elevation requires an authenticated session with a canonical id.');
        }

        if ($current['id'] !== $user['id']) {
            throw new InvalidArgumentException('Privilege elevation cannot switch the authenticated principal.');
        }

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

        if (!is_array($user) || !self::hasValidUserIdentity($user)) {
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

        return is_array($user) && self::hasValidUserIdentity($user) ? $user : null;
    }

    /**
     * Logout must remain available even if deployment configuration changed after
     * the session was created. SessionSecurity therefore prefers the stored policy
     * for the exact cookie tuple and uses this argument only as a legacy fallback.
     *
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed>|null $server
     */
    public static function logout(
        array $sessionConfig = [],
        ?array $server = null,
        ?int $now = null,
    ): void {
        SessionSecurity::startForDestruction($sessionConfig, $server);
        SessionSecurity::destroy();
        self::$sessionManagedInRequest = false;
    }

    /**
     * A pre-active session was opened outside Hache Base, so there is no trustworthy
     * evidence that its browser cookie used the candidate scope. PHP exposes the
     * runtime tuple, but cannot recover Path/Domain from the incoming Cookie header.
     * Accept only an exact match; otherwise fail before attaching authentication.
     *
     * @param array<string, mixed> $sessionConfig
     * @param array<string, mixed> $server
     */
    private static function assertPreActiveCookieTupleMatches(array $sessionConfig, array $server): void
    {
        $expected = SessionSecurity::buildCookieParams($sessionConfig, $server);
        $params = session_get_cookie_params();
        $current = [
            'lifetime' => (int)$params['lifetime'],
            'path' => (string)$params['path'],
            'domain' => (string)$params['domain'],
            'secure' => (bool)$params['secure'],
            'httponly' => (bool)$params['httponly'],
            'samesite' => (string)($params['samesite'] ?? ''),
        ];

        if ($current !== $expected) {
            throw new LogicException(
                'A pre-active PHP session has a cookie tuple that does not match the requested SEC-007 policy. Start Hache Base before session_start() or align the cookie scope first.',
            );
        }
    }

    /**
     * @param array<string, mixed> $user
     */
    private static function assertUserIdentity(array $user): void
    {
        if (!self::hasValidUserIdentity($user)) {
            throw new InvalidArgumentException('Authenticated user id must be a non-empty string or an integer.');
        }
    }

    /**
     * @param array<string, mixed> $user
     */
    private static function hasValidUserIdentity(array $user): bool
    {
        if (!array_key_exists('id', $user)) {
            return false;
        }

        $id = $user['id'];

        if (is_int($id)) {
            return true;
        }

        return is_string($id) && $id !== '';
    }
}
