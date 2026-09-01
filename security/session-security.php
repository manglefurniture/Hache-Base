<?php

declare(strict_types=1);

namespace HacheBase\Security;

use InvalidArgumentException;
use LogicException;

require_once __DIR__ . '/request-security.php';

/**
 * Reusable server-side session contract for SEC-007.
 *
 * It provides secure cookie defaults, trusted-proxy HTTPS detection, explicit
 * idle/absolute expiration, session ID rotation, and effective destruction.
 * Authentication, authorization, password policy and MFA remain project concerns.
 */
final class SessionSecurity
{
    private const META_KEY = '__hache_session';

    private const DEFAULT_CONFIG = [
        'idle_timeout' => 1800,
        'absolute_timeout' => 43200,
        'same_site' => 'Lax',
        'cookie_path' => '/',
        'cookie_domain' => null,
        'proxy' => [
            'trusted_ips' => [],
            'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
        ],
    ];

    private const TOP_LEVEL_KEYS = [
        'idle_timeout',
        'absolute_timeout',
        'same_site',
        'cookie_path',
        'cookie_domain',
        'proxy',
    ];

    /**
     * @param array<string, mixed> $config
     * @param array<string, mixed>|null $server
     */
    public static function start(array $config = [], ?array $server = null, ?int $now = null): void
    {
        $resolved = self::resolveConfig($config);
        $now ??= time();

        if (session_status() === PHP_SESSION_ACTIVE) {
            self::refreshOrExpire($resolved, $now);
            return;
        }

        if (headers_sent($file, $line)) {
            throw new LogicException(sprintf('Cannot start secure session after headers were sent at %s:%d.', $file, $line));
        }

        if (ini_set('session.use_strict_mode', '1') === false) {
            throw new LogicException('Unable to enable session.use_strict_mode.');
        }
        if (ini_set('session.use_only_cookies', '1') === false) {
            throw new LogicException('Unable to enable session.use_only_cookies.');
        }
        if (ini_set('session.use_trans_sid', '0') === false) {
            throw new LogicException('Unable to disable session.use_trans_sid.');
        }

        $cookieParams = self::buildCookieParams($resolved, $server ?? $_SERVER);
        session_set_cookie_params($cookieParams);

        if (!session_start()) {
            throw new LogicException('Unable to start session.');
        }

        self::refreshOrExpire($resolved, $now);
    }

    /**
     * Build the exact cookie params without starting a session.
     *
     * @param array<string, mixed> $config
     * @param array<string, mixed> $server
     * @return array{lifetime:int,path:string,secure:bool,httponly:bool,samesite:string,domain?:string}
     */
    public static function buildCookieParams(array $config = [], array $server = []): array
    {
        $resolved = self::resolveConfig($config);
        $secure = RequestSecurity::isHttps($server, $resolved['proxy']);

        if ($resolved['same_site'] === 'None' && !$secure) {
            throw new InvalidArgumentException('SameSite=None requires an HTTPS request so the cookie can be Secure.');
        }

        $params = [
            'lifetime' => 0,
            'path' => $resolved['cookie_path'],
            'secure' => $secure,
            'httponly' => true,
            'samesite' => $resolved['same_site'],
        ];

        if ($resolved['cookie_domain'] !== null) {
            $params['domain'] = $resolved['cookie_domain'];
        }

        return $params;
    }

    public static function regenerateForAuthentication(?int $now = null): void
    {
        self::requireActiveSession();
        $now ??= time();

        if (!session_regenerate_id(true)) {
            throw new LogicException('Unable to regenerate session ID after authentication.');
        }

        $_SESSION[self::META_KEY] = [
            'created_at' => $now,
            'last_seen_at' => $now,
            'authenticated_at' => $now,
        ];
    }

    public static function regenerateForPrivilegeChange(?int $now = null): void
    {
        self::requireActiveSession();
        $now ??= time();

        $meta = self::readMeta($now);

        if (!session_regenerate_id(true)) {
            throw new LogicException('Unable to regenerate session ID after privilege change.');
        }

        $meta['last_seen_at'] = $now;
        $meta['privilege_changed_at'] = $now;
        $_SESSION[self::META_KEY] = $meta;
    }

    public static function destroy(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            return;
        }

        $_SESSION = [];

        if ((bool)ini_get('session.use_cookies')) {
            $params = session_get_cookie_params();
            $options = [
                'expires' => time() - 42000,
                'path' => (string)$params['path'],
                'secure' => (bool)$params['secure'],
                'httponly' => (bool)$params['httponly'],
                'samesite' => (string)($params['samesite'] ?? 'Lax'),
            ];

            if ((string)$params['domain'] !== '') {
                $options['domain'] = (string)$params['domain'];
            }

            setcookie(session_name(), '', $options);
        }

        session_destroy();
        session_id('');
    }

    /**
     * @param array<string, mixed> $config
     * @return array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}}
     */
    public static function resolveConfig(array $config = []): array
    {
        self::assertKnownKeys($config, self::TOP_LEVEL_KEYS);

        if (array_key_exists('proxy', $config) && !is_array($config['proxy'])) {
            throw new InvalidArgumentException('Session proxy configuration must be an array.');
        }

        $resolved = array_replace_recursive(self::DEFAULT_CONFIG, $config);

        if (!is_int($resolved['idle_timeout']) || $resolved['idle_timeout'] <= 0) {
            throw new InvalidArgumentException('idle_timeout must be a positive integer in seconds.');
        }
        if (!is_int($resolved['absolute_timeout']) || $resolved['absolute_timeout'] <= 0) {
            throw new InvalidArgumentException('absolute_timeout must be a positive integer in seconds.');
        }
        if ($resolved['absolute_timeout'] < $resolved['idle_timeout']) {
            throw new InvalidArgumentException('absolute_timeout must be greater than or equal to idle_timeout.');
        }

        if (!is_string($resolved['same_site'])) {
            throw new InvalidArgumentException('same_site must be Lax, Strict, or None.');
        }
        $sameSite = ucfirst(strtolower(trim($resolved['same_site'])));
        if (!in_array($sameSite, ['Lax', 'Strict', 'None'], true)) {
            throw new InvalidArgumentException('same_site must be Lax, Strict, or None.');
        }
        $resolved['same_site'] = $sameSite;

        if (!is_string($resolved['cookie_path'])
            || !str_starts_with($resolved['cookie_path'], '/')
            || preg_match('/[;\r\n\x00]/', $resolved['cookie_path']) === 1) {
            throw new InvalidArgumentException('cookie_path must be an absolute safe cookie path.');
        }

        if ($resolved['cookie_domain'] !== null) {
            if (!is_string($resolved['cookie_domain'])
                || trim($resolved['cookie_domain']) === ''
                || preg_match('/[;\s\r\n\x00]/', $resolved['cookie_domain']) === 1) {
                throw new InvalidArgumentException('cookie_domain must be null or a safe explicit domain.');
            }
        }

        /** @var array<string, mixed> $proxy */
        $proxy = $resolved['proxy'];
        $resolved['proxy'] = RequestSecurity::resolveProxyConfig($proxy);

        /** @var array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $resolved */
        return $resolved;
    }

    /**
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $config
     */
    private static function refreshOrExpire(array $config, int $now): void
    {
        $meta = self::readMeta($now);
        $createdAt = $meta['created_at'];
        $lastSeenAt = $meta['last_seen_at'];

        $expired = $now < $createdAt
            || $now < $lastSeenAt
            || ($now - $createdAt) >= $config['absolute_timeout']
            || ($now - $lastSeenAt) >= $config['idle_timeout'];

        if ($expired) {
            $_SESSION = [];
            if (!session_regenerate_id(true)) {
                throw new LogicException('Unable to rotate expired session.');
            }

            $_SESSION[self::META_KEY] = [
                'created_at' => $now,
                'last_seen_at' => $now,
            ];
            return;
        }

        $meta['last_seen_at'] = $now;
        $_SESSION[self::META_KEY] = $meta;
    }

    /**
     * @return array{created_at:int,last_seen_at:int,authenticated_at?:int,privilege_changed_at?:int}
     */
    private static function readMeta(int $now): array
    {
        $meta = $_SESSION[self::META_KEY] ?? null;
        if (!is_array($meta)
            || !isset($meta['created_at'], $meta['last_seen_at'])
            || !is_int($meta['created_at'])
            || !is_int($meta['last_seen_at'])) {
            return [
                'created_at' => $now,
                'last_seen_at' => $now,
            ];
        }

        /** @var array{created_at:int,last_seen_at:int,authenticated_at?:int,privilege_changed_at?:int} $meta */
        return $meta;
    }

    private static function requireActiveSession(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            throw new LogicException('An active session is required.');
        }
    }

    /**
     * @param array<string, mixed> $config
     * @param list<string> $allowed
     */
    private static function assertKnownKeys(array $config, array $allowed): void
    {
        foreach (array_keys($config) as $key) {
            if (!is_string($key) || !in_array($key, $allowed, true)) {
                throw new InvalidArgumentException(sprintf('Unknown session configuration key: %s', (string)$key));
            }
        }
    }
}
