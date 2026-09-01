<?php

declare(strict_types=1);

namespace HacheBase\Security;

use InvalidArgumentException;
use LogicException;

require_once __DIR__ . '/request-security.php';

/**
 * Reusable server-side session contract for SEC-007.
 *
 * The effective policy is persisted inside the server-side session. This prevents
 * helpers that call Auth::startSecureSession() without arguments from silently
 * refreshing an authenticated session under different timeout/cookie defaults.
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
        $candidatePolicy = self::resolveConfig($config);
        $explicitPolicy = $config !== [];
        $server ??= $_SERVER;
        $now ??= time();

        if (session_status() !== PHP_SESSION_ACTIVE) {
            self::assertHeadersAvailable('start secure session');
            self::configurePhpSessionRuntime();
            session_set_cookie_params(self::buildCookieParamsFromResolved($candidatePolicy, $server));

            if (!session_start()) {
                throw new LogicException('Unable to start session.');
            }
        }

        $storedPolicy = self::readStoredPolicy();

        if ($storedPolicy === null) {
            // Sessions created before P0-08 have no policy metadata. If they already
            // carry authenticated state, invalidate that state instead of guessing a
            // timeout/cookie contract and silently grandfathering the session.
            if (array_key_exists('user', $_SESSION)) {
                self::ensureCookiePolicy($candidatePolicy, $server);
                self::rotateToAnonymous($candidatePolicy, $now);
                return;
            }

            self::ensureCookiePolicy($candidatePolicy, $server);
            self::writeMeta(self::newMeta($now, $candidatePolicy));
            self::refreshOrExpire($candidatePolicy, $now);
            return;
        }

        $effectivePolicy = $storedPolicy;

        if ($explicitPolicy && $candidatePolicy !== $storedPolicy) {
            if (array_key_exists('user', $_SESSION)) {
                // Re-bind the current request to the authoritative stored cookie
                // policy before failing. Most importantly, do not refresh last_seen.
                self::ensureCookiePolicy($storedPolicy, $server);
                throw new LogicException(
                    'Cannot change session policy while authenticated. Configure one policy before session use or log out first.',
                );
            }

            // Anonymous sessions may be upgraded to the explicit project policy
            // before authentication. The stored policy is authoritative evidence of
            // the previous cookie tuple, even when runtime params already equal the
            // candidate policy because they were installed before session_start().
            $effectivePolicy = $candidatePolicy;
            self::ensureCookiePolicy($effectivePolicy, $server, $storedPolicy);
            $meta = self::readMeta();
            self::writeMeta($meta === null
                ? self::newMeta($now, $effectivePolicy)
                : array_replace($meta, ['policy' => $effectivePolicy]));
        } else {
            // A no-argument helper must inherit the stored policy rather than defaults.
            // The pre-session runtime params are only an inference here, not proof of
            // the browser cookie tuple, so never expire that inferred scope.
            self::ensureCookiePolicy($effectivePolicy, $server);
        }

        self::refreshOrExpire($effectivePolicy, $now);
    }

    /**
     * Build the exact cookie params without starting a session.
     *
     * @param array<string, mixed> $config
     * @param array<string, mixed> $server
     * @return array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}
     */
    public static function buildCookieParams(array $config = [], array $server = []): array
    {
        return self::buildCookieParamsFromResolved(self::resolveConfig($config), $server);
    }

    public static function regenerateForAuthentication(?int $now = null): void
    {
        self::requireActiveSession();
        $now ??= time();
        $policy = self::requireStoredPolicy();

        if (!session_regenerate_id(true)) {
            throw new LogicException('Unable to regenerate session ID after authentication.');
        }

        self::writeMeta([
            'created_at' => $now,
            'last_seen_at' => $now,
            'authenticated_at' => $now,
            'policy' => $policy,
        ]);
    }

    public static function regenerateForPrivilegeChange(?int $now = null): void
    {
        self::requireActiveSession();
        $now ??= time();

        $meta = self::readMeta();
        if ($meta === null || !isset($meta['policy']) || !is_array($meta['policy'])) {
            throw new LogicException('Cannot elevate a session with invalid security metadata.');
        }

        if (!session_regenerate_id(true)) {
            throw new LogicException('Unable to regenerate session ID after privilege change.');
        }

        $meta['last_seen_at'] = $now;
        $meta['privilege_changed_at'] = $now;
        self::writeMeta($meta);
    }

    public static function destroy(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            return;
        }

        $_SESSION = [];
        $cookieDeleted = true;

        if ((bool)ini_get('session.use_cookies')) {
            $cookieDeleted = self::expireCookie(self::currentCookieParams());
        }

        $destroyed = session_destroy();
        session_id('');

        if (!$destroyed) {
            throw new LogicException('Unable to destroy server-side session.');
        }
        if (!$cookieDeleted) {
            throw new LogicException('Server-side session was destroyed but the session cookie could not be expired.');
        }
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
            || preg_match('/[\x00-\x20\x7F,;]/', $resolved['cookie_path']) === 1) {
            throw new InvalidArgumentException('cookie_path must be an absolute safe cookie path.');
        }

        $resolved['cookie_domain'] = self::normalizeCookieDomain($resolved['cookie_domain']);

        /** @var array<string, mixed> $proxy */
        $proxy = $resolved['proxy'];
        $resolved['proxy'] = RequestSecurity::resolveProxyConfig($proxy);

        /** @var array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $resolved */
        return $resolved;
    }

    /**
     * @param mixed $domain
     */
    private static function normalizeCookieDomain(mixed $domain): ?string
    {
        if ($domain === null) {
            return null;
        }

        if (!is_string($domain)) {
            throw new InvalidArgumentException('cookie_domain must be null or a valid ASCII hostname.');
        }

        $normalized = strtolower($domain);
        if ($normalized === ''
            || $normalized !== trim($normalized)
            || str_starts_with($normalized, '.')
            || str_ends_with($normalized, '.')
            || filter_var($normalized, FILTER_VALIDATE_DOMAIN, FILTER_FLAG_HOSTNAME) === false
            || filter_var($normalized, FILTER_VALIDATE_IP) !== false
            || self::endsInWhatwgIpv4Number($normalized)) {
            throw new InvalidArgumentException('cookie_domain must be null or a valid ASCII hostname; use punycode for IDN domains.');
        }

        return $normalized;
    }

    private static function endsInWhatwgIpv4Number(string $hostname): bool
    {
        $labels = explode('.', $hostname);
        $last = $labels[count($labels) - 1] ?? '';

        return preg_match('/^[0-9]+$/D', $last) === 1
            || preg_match('/^0x[0-9a-f]+$/D', $last) === 1;
    }

    /**
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $config
     * @param array<string, mixed> $server
     * @return array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}
     */
    private static function buildCookieParamsFromResolved(array $config, array $server): array
    {
        $secure = RequestSecurity::isHttps($server, $config['proxy']);

        if ($config['same_site'] === 'None' && !$secure) {
            throw new InvalidArgumentException('SameSite=None requires an HTTPS request so the cookie can be Secure.');
        }

        return [
            'lifetime' => 0,
            'path' => $config['cookie_path'],
            // Empty domain explicitly requests a host-only cookie and avoids inheriting
            // a broader php.ini session.cookie_domain by accident.
            'domain' => $config['cookie_domain'] ?? '',
            'secure' => $secure,
            'httponly' => true,
            'samesite' => $config['same_site'],
        ];
    }

    /**
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $policy
     * @param array<string, mixed> $server
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}}|null $previousPolicy
     */
    private static function ensureCookiePolicy(array $policy, array $server, ?array $previousPolicy = null): void
    {
        self::requireActiveSession();
        $desired = self::buildCookieParamsFromResolved($policy, $server);
        $current = self::currentCookieParams();
        $previous = $previousPolicy === null
            ? null
            : self::buildCookieParamsFromResolved($previousPolicy, $server);

        $needsRebind = $current !== $desired;
        $needsPreviousScopeExpiry = $previous !== null
            && ($previous['path'] !== $desired['path'] || $previous['domain'] !== $desired['domain']);

        if (!$needsRebind && !$needsPreviousScopeExpiry) {
            return;
        }

        self::assertHeadersAvailable('re-bind session cookie policy');

        $sessionId = session_id();
        if ($sessionId === '') {
            throw new LogicException('Cannot re-bind cookie policy without a session ID.');
        }

        if ($needsRebind) {
            if (!session_write_close()) {
                throw new LogicException('Unable to persist session before re-binding cookie policy.');
            }

            session_set_cookie_params($desired);
            session_id($sessionId);

            if (!session_start()) {
                throw new LogicException('Unable to reopen session with the effective cookie policy.');
            }
        }

        // Only a supplied stored policy is authoritative evidence of an old cookie
        // tuple. Runtime params on a new request may already be the candidate policy
        // and must never substitute for the stored tuple during migration.
        if ($needsPreviousScopeExpiry && !self::expireCookie($previous)) {
            throw new LogicException('Unable to expire the previous session cookie scope.');
        }

        if (!self::setSessionCookie(session_id(), $desired)) {
            throw new LogicException('Unable to apply the effective session cookie policy.');
        }
    }

    /**
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $policy
     */
    private static function refreshOrExpire(array $policy, int $now): void
    {
        $meta = self::readMeta();

        if ($meta === null) {
            if (array_key_exists('user', $_SESSION)) {
                self::rotateToAnonymous($policy, $now);
                return;
            }

            self::writeMeta(self::newMeta($now, $policy));
            return;
        }

        $createdAt = $meta['created_at'];
        $lastSeenAt = $meta['last_seen_at'];

        $expired = $now < $createdAt
            || $now < $lastSeenAt
            || ($now - $createdAt) >= $policy['absolute_timeout']
            || ($now - $lastSeenAt) >= $policy['idle_timeout'];

        if ($expired) {
            self::rotateToAnonymous($policy, $now);
            return;
        }

        $meta['last_seen_at'] = $now;
        $meta['policy'] = $policy;
        self::writeMeta($meta);
    }

    /**
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $policy
     */
    private static function rotateToAnonymous(array $policy, int $now): void
    {
        $_SESSION = [];
        if (!session_regenerate_id(true)) {
            throw new LogicException('Unable to rotate expired or legacy session.');
        }

        self::writeMeta(self::newMeta($now, $policy));
    }

    /**
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}} $policy
     * @return array{created_at:int,last_seen_at:int,policy:array<string,mixed>}
     */
    private static function newMeta(int $now, array $policy): array
    {
        return [
            'created_at' => $now,
            'last_seen_at' => $now,
            'policy' => $policy,
        ];
    }

    /**
     * @return array{created_at:int,last_seen_at:int,authenticated_at?:int,privilege_changed_at?:int,policy?:array<string,mixed>}|null
     */
    private static function readMeta(): ?array
    {
        $meta = $_SESSION[self::META_KEY] ?? null;
        if (!is_array($meta)
            || !isset($meta['created_at'], $meta['last_seen_at'])
            || !is_int($meta['created_at'])
            || !is_int($meta['last_seen_at'])) {
            return null;
        }

        /** @var array{created_at:int,last_seen_at:int,authenticated_at?:int,privilege_changed_at?:int,policy?:array<string,mixed>} $meta */
        return $meta;
    }

    /**
     * @return array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}}|null
     */
    private static function readStoredPolicy(): ?array
    {
        $meta = $_SESSION[self::META_KEY] ?? null;
        if (!is_array($meta) || !array_key_exists('policy', $meta)) {
            return null;
        }

        if (!is_array($meta['policy'])) {
            throw new LogicException('Stored session security policy is invalid.');
        }

        try {
            return self::resolveConfig($meta['policy']);
        } catch (InvalidArgumentException $exception) {
            throw new LogicException('Stored session security policy is invalid.', 0, $exception);
        }
    }

    /**
     * @return array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}}
     */
    private static function requireStoredPolicy(): array
    {
        $policy = self::readStoredPolicy();
        if ($policy === null) {
            throw new LogicException('Session security policy metadata is missing.');
        }

        return $policy;
    }

    /**
     * @param array<string, mixed> $meta
     */
    private static function writeMeta(array $meta): void
    {
        $_SESSION[self::META_KEY] = $meta;
    }

    private static function configurePhpSessionRuntime(): void
    {
        if (ini_set('session.use_strict_mode', '1') === false) {
            throw new LogicException('Unable to enable session.use_strict_mode.');
        }
        if (ini_set('session.use_cookies', '1') === false) {
            throw new LogicException('Unable to enable session.use_cookies.');
        }
        if (ini_set('session.use_only_cookies', '1') === false) {
            throw new LogicException('Unable to enable session.use_only_cookies.');
        }
        if (ini_set('session.use_trans_sid', '0') === false) {
            throw new LogicException('Unable to disable session.use_trans_sid.');
        }
    }

    /**
     * @return array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}
     */
    private static function currentCookieParams(): array
    {
        $params = session_get_cookie_params();

        return [
            'lifetime' => (int)$params['lifetime'],
            'path' => (string)$params['path'],
            'domain' => (string)$params['domain'],
            'secure' => (bool)$params['secure'],
            'httponly' => (bool)$params['httponly'],
            'samesite' => (string)($params['samesite'] ?? ''),
        ];
    }

    /**
     * @param array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string} $params
     */
    private static function setSessionCookie(string $value, array $params): bool
    {
        $options = [
            'expires' => 0,
            'path' => $params['path'],
            'secure' => $params['secure'],
            'httponly' => $params['httponly'],
            'samesite' => $params['samesite'],
        ];

        if ($params['domain'] !== '') {
            $options['domain'] = $params['domain'];
        }

        return setcookie(session_name(), $value, $options);
    }

    /**
     * @param array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string} $params
     */
    private static function expireCookie(array $params): bool
    {
        $options = [
            'expires' => time() - 42000,
            'path' => $params['path'],
            'secure' => $params['secure'],
            'httponly' => $params['httponly'],
            'samesite' => $params['samesite'] !== '' ? $params['samesite'] : 'Lax',
        ];

        if ($params['domain'] !== '') {
            $options['domain'] = $params['domain'];
        }

        return setcookie(session_name(), '', $options);
    }

    private static function requireActiveSession(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            throw new LogicException('An active session is required.');
        }
    }

    private static function assertHeadersAvailable(string $action): void
    {
        if (headers_sent($file, $line)) {
            throw new LogicException(sprintf('Cannot %s after headers were sent at %s:%d.', $action, $file, $line));
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
