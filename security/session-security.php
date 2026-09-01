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

    /**
     * Exact old cookie tuple that must survive any session-module Set-Cookie replacement
     * later in the same request (for example session_regenerate_id() during login), or
     * the exact persisted tuple that logout must expire without re-evaluating proxy state.
     *
     * @var array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}|null
     */
    private static ?array $pendingCookieExpiry = null;

    /**
     * Incoming sessions are provenance-validated with session.use_cookies=0 so PHP
     * cannot emit a replacement cookie before SEC-007 verifies the exact ID/metadata.
     * While that validated session remains active, this request-local tuple is the
     * authoritative cookie identity and all cookie emission is performed manually.
     *
     * @var array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}|null
     */
    private static ?array $manualCookieParams = null;

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
        $incomingSessionCookie = self::hasIncomingSessionCookie();
        $initialPolicy = $candidatePolicy;

        if ($incomingSessionCookie && session_status() !== PHP_SESSION_ACTIVE) {
            // Validate provenance without cookie output. The second validation uses the
            // exact persisted cookie tuple and leaves that session active, so there is
            // no cookie-emitting reopen window after provenance is established.
            $initialPolicy = self::preflightIncomingSessionCookie($server);
        }

        self::openOrAdoptSession($initialPolicy, $server);

        $storedPolicy = self::readStoredPolicy();

        if ($storedPolicy === null && $incomingSessionCookie) {
            throw new LogicException(
                'An incoming PHP session cookie has no verifiable Hache Base SEC-007 metadata. Its original cookie scope cannot be safely inferred; clear or destroy the legacy session before authentication.',
            );
        }

        if ($storedPolicy === null) {
            // A metadata-less session is adoptable only when no session cookie arrived
            // in this request, so Hache Base knows it is establishing a new cookie tuple.
            // Historical authenticated state without metadata is still invalidated.
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
            // before authentication. Prefer the exact cookie tuple persisted when
            // that anonymous session was emitted; rebuilding it from an old proxy
            // policy under today's topology can make SameSite=None appear insecure.
            // Legacy sessions without a cookie snapshot fall back to stored policy.
            $effectivePolicy = $candidatePolicy;
            $storedCookie = self::readStoredCookieParams();
            self::ensureCookiePolicy($effectivePolicy, $server, $storedPolicy, $storedCookie);
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
     * Open a session only for destruction/logout.
     *
     * A persisted effective cookie tuple wins over any policy reconstruction so a
     * deployment-time timeout, cookie, or trusted-proxy change can never make logout
     * impossible. Invalid or missing legacy metadata also must not prevent server-side
     * session destruction.
     *
     * @param array<string, mixed> $fallbackConfig
     * @param array<string, mixed>|null $server
     */
    public static function startForDestruction(
        array $fallbackConfig = [],
        ?array $server = null,
    ): void {
        $server ??= $_SERVER;
        self::openOrAdoptSession(null, $server);

        try {
            $storedCookie = self::readStoredCookieParams();
        } catch (LogicException) {
            $storedCookie = null;
        }

        if ($storedCookie !== null) {
            // Cookie identity is the tuple that was actually emitted, not a fresh
            // interpretation of the old proxy policy under today's infrastructure.
            self::$pendingCookieExpiry = $storedCookie;
            return;
        }

        try {
            $storedPolicy = self::readStoredPolicy();
        } catch (LogicException) {
            // Corrupt legacy metadata must never make logout unavailable. destroy()
            // will still invalidate the server-side session and expire current scope.
            return;
        }

        if ($storedPolicy !== null) {
            try {
                self::ensureCookiePolicy($storedPolicy, $server);
            } catch (InvalidArgumentException) {
                // Legacy P0-08 metadata may predate persisted cookie tuples. If its
                // proxy interpretation no longer permits reconstructing the cookie,
                // destruction still takes precedence over exact browser cleanup.
            }
            return;
        }

        if ($fallbackConfig === []) {
            return;
        }

        try {
            self::ensureCookiePolicy(self::resolveConfig($fallbackConfig), $server);
        } catch (InvalidArgumentException) {
            // The fallback is advisory only for metadata-less legacy sessions.
            // Destruction takes precedence over rejecting a newly changed config.
        }
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

        self::regenerateIdOrFail('Unable to regenerate session ID after authentication.');

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

        self::regenerateIdOrFail('Unable to regenerate session ID after privilege change.');

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
        $cookiesToExpire = [];

        if (self::$manualCookieParams !== null) {
            $cookiesToExpire[] = self::$manualCookieParams;
        } elseif ((bool)ini_get('session.use_cookies')) {
            $cookiesToExpire[] = self::currentCookieParams();
        }

        if (self::$pendingCookieExpiry !== null
            && !in_array(self::$pendingCookieExpiry, $cookiesToExpire, true)) {
            $cookiesToExpire[] = self::$pendingCookieExpiry;
        }

        foreach ($cookiesToExpire as $cookieParams) {
            $cookieDeleted = self::expireCookie($cookieParams) && $cookieDeleted;
        }

        $destroyed = session_destroy();
        session_id('');
        self::$pendingCookieExpiry = null;
        self::$manualCookieParams = null;

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
     * @param array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}}|null $initialPolicy
     * @param array<string, mixed> $server
     */
    private static function openOrAdoptSession(?array $initialPolicy, array $server): void
    {
        if (session_status() === PHP_SESSION_ACTIVE) {
            if (self::$manualCookieParams !== null) {
                return;
            }

            self::assertPreActiveSessionRuntimeCompliant();
            return;
        }

        self::assertHeadersAvailable('start secure session');
        self::configurePhpSessionRuntime();

        if ($initialPolicy !== null) {
            session_set_cookie_params(self::buildCookieParamsFromResolved($initialPolicy, $server));
        }

        if (!session_start()) {
            throw new LogicException('Unable to start session.');
        }
    }

    private static function assertPreActiveSessionRuntimeCompliant(): void
    {
        if (self::phpSessionRuntimeCompliant()) {
            return;
        }

        throw new LogicException(
            'A pre-active PHP session does not satisfy SEC-007. Start Hache Base before session_start() or configure strict, cookie-backed, cookie-only sessions first.',
        );
    }

    private static function phpSessionRuntimeCompliant(): bool
    {
        return (bool)ini_get('session.use_strict_mode')
            && (bool)ini_get('session.use_cookies')
            && (bool)ini_get('session.use_only_cookies')
            && !(bool)ini_get('session.use_trans_sid');
    }

    private static function hasIncomingSessionCookie(): bool
    {
        $name = session_name();

        return $name !== '' && array_key_exists($name, $_COOKIE);
    }

    /**
     * Validate an incoming browser session twice without allowing PHP to emit a
     * candidate cookie. The first read establishes provenance and obtains the exact
     * persisted cookie tuple. The second read reopens the same ID under that tuple
     * while cookie output remains disabled; if the session disappeared between reads,
     * strict mode may replace the ID but no Set-Cookie can escape. On success the
     * second session remains active in request-local manual-cookie mode.
     *
     * @param array<string, mixed> $server
     * @return array{idle_timeout:int,absolute_timeout:int,same_site:string,cookie_path:string,cookie_domain:?string,proxy:array{trusted_ips:list<string>,forwarded_proto_header:string}}
     */
    private static function preflightIncomingSessionCookie(array $server): array
    {
        $name = session_name();
        $incomingId = $name === '' ? null : ($_COOKIE[$name] ?? null);

        if (!is_string($incomingId) || $incomingId === '') {
            throw new LogicException('An incoming PHP session cookie does not contain a usable session ID.');
        }

        self::assertHeadersAvailable('validate incoming session cookie');
        self::configurePhpSessionRuntime();

        // In strict mode an expired/unknown ID may be replaced during session_start().
        // Keep cookie output off through both provenance reads so no replacement can
        // be committed to the browser before the exact ID and metadata are revalidated.
        if (ini_set('session.use_cookies', '0') === false) {
            throw new LogicException('Unable to disable session cookies for incoming-session provenance validation.');
        }

        session_id($incomingId);
        $resolvedId = '';
        $storedPolicy = null;
        $storedCookie = null;
        $storedCookieWasPersisted = false;

        try {
            if (!session_start()) {
                throw new LogicException('Unable to validate incoming session cookie.');
            }

            $resolvedId = session_id();
            if ($resolvedId === $incomingId) {
                $storedPolicy = self::readStoredPolicy();
                $storedCookie = self::readStoredCookieParams();
                $storedCookieWasPersisted = $storedCookie !== null;

                if ($storedPolicy !== null && $storedCookie === null) {
                    // Legacy SEC-007 metadata from before cookie snapshots may still be
                    // adopted when its old policy can be reconstructed safely.
                    $storedCookie = self::buildCookieParamsFromResolved($storedPolicy, $server);
                }
            }
        } catch (\Throwable $exception) {
            try {
                self::closeIncomingSessionPreflight($incomingId, $resolvedId);
            } finally {
                self::restoreCookieRuntimeAfterPreflight();
            }
            throw $exception;
        }

        try {
            self::closeIncomingSessionPreflight($incomingId, $resolvedId);
        } catch (\Throwable $exception) {
            try {
                self::restoreCookieRuntimeAfterPreflight();
            } finally {
                throw $exception;
            }
        }

        if ($resolvedId !== $incomingId || $storedPolicy === null || $storedCookie === null) {
            self::restoreCookieRuntimeAfterPreflight();
            throw new LogicException(
                'An incoming PHP session cookie has no verifiable Hache Base SEC-007 metadata. Its original cookie scope cannot be safely inferred; clear or destroy the legacy session before authentication.',
            );
        }

        // Reopen with the exact tuple that produced the validated browser cookie.
        // Cookie output is intentionally still disabled during this second read.
        session_set_cookie_params($storedCookie);
        session_id($incomingId);
        $reopenedId = '';
        $reopenedPolicy = null;
        $reopenedCookie = null;

        try {
            if (!session_start()) {
                throw new LogicException('Unable to revalidate incoming session cookie.');
            }

            $reopenedId = session_id();
            if ($reopenedId === $incomingId) {
                $reopenedPolicy = self::readStoredPolicy();
                $reopenedCookie = self::readStoredCookieParams();
            }
        } catch (\Throwable $exception) {
            try {
                self::closeIncomingSessionPreflight($incomingId, $reopenedId);
            } finally {
                self::restoreCookieRuntimeAfterPreflight();
            }
            throw $exception;
        }

        $samePolicy = $reopenedPolicy !== null && $reopenedPolicy === $storedPolicy;
        $sameCookie = $storedCookieWasPersisted
            ? $reopenedCookie !== null && $reopenedCookie === $storedCookie
            : $reopenedCookie === null || $reopenedCookie === $storedCookie;

        if ($reopenedId !== $incomingId || !$samePolicy || !$sameCookie) {
            try {
                self::closeIncomingSessionPreflight($incomingId, $reopenedId);
            } finally {
                self::restoreCookieRuntimeAfterPreflight();
            }

            throw new LogicException(
                'The incoming PHP session changed during SEC-007 provenance validation. Authentication was rejected before any replacement cookie could be emitted.',
            );
        }

        // Keep the validated second session open and keep automatic session-cookie
        // output disabled for this request. All later rebinds and ID rotations emit
        // only after their state transition has succeeded.
        self::$manualCookieParams = $storedCookie;

        return $storedPolicy;
    }

    private static function closeIncomingSessionPreflight(string $incomingId, string $resolvedId): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_id('');
            return;
        }

        $closed = true;
        if ($resolvedId !== '' && $resolvedId !== $incomingId) {
            // Strict mode may have generated a fresh replacement for an expired ID.
            // It is preflight-only state: remove it so rejection leaves no orphan.
            $_SESSION = [];
            $closed = session_destroy();
        } else {
            $closed = session_abort();
        }

        session_id('');

        if (!$closed) {
            throw new LogicException('Unable to close incoming-session provenance validation safely.');
        }
    }

    private static function restoreCookieRuntimeAfterPreflight(): void
    {
        if (ini_set('session.use_cookies', '1') === false) {
            throw new LogicException('Unable to restore session.use_cookies after provenance validation.');
        }
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
     * @param array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}|null $previousCookie
     */
    private static function ensureCookiePolicy(
        array $policy,
        array $server,
        ?array $previousPolicy = null,
        ?array $previousCookie = null,
    ): void {
        self::requireActiveSession();
        $manualMode = self::$manualCookieParams !== null;
        $desired = $manualMode && $previousPolicy === null
            ? self::$manualCookieParams
            : self::buildCookieParamsFromResolved($policy, $server);
        $current = self::currentCookieParams();
        $previous = $previousCookie ?? ($previousPolicy === null
            ? null
            : self::buildCookieParamsFromResolved($previousPolicy, $server));

        $needsRebind = $current !== $desired;
        $needsPreviousScopeExpiry = $previous !== null
            && ($previous['path'] !== $desired['path'] || $previous['domain'] !== $desired['domain']);

        if (!$needsRebind && !$needsPreviousScopeExpiry) {
            if ($manualMode && !self::setSessionCookie(session_id(), $desired)) {
                throw new LogicException('Unable to re-emit the validated session cookie.');
            }
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

            if ($manualMode) {
                // Automatic cookie output remains disabled in manual mode. If the
                // session vanished during the controlled rebind, strict mode may
                // replace the ID but no cookie has escaped; reject before mutation.
                if (session_id() !== $sessionId || self::readStoredPolicy() === null) {
                    $resolvedId = session_id();
                    self::closeIncomingSessionPreflight($sessionId, $resolvedId);
                    throw new LogicException('Session changed while re-binding cookie policy.');
                }
                self::$manualCookieParams = $desired;
            }
        }

        // A persisted previous cookie tuple is authoritative when available. Only
        // legacy sessions fall back to rebuilding from the stored policy. Runtime
        // params on a new request must never substitute for the old tuple. Keep the
        // tuple request-locally as well because the PHP session module can replace
        // same-name Set-Cookie headers during a subsequent ID regeneration.
        if ($needsPreviousScopeExpiry) {
            if (!self::expireCookie($previous)) {
                throw new LogicException('Unable to expire the previous session cookie scope.');
            }
            self::$pendingCookieExpiry = $previous;
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
        self::regenerateIdOrFail('Unable to rotate expired or legacy session.');

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
     * @return array{created_at:int,last_seen_at:int,authenticated_at?:int,privilege_changed_at?:int,policy?:array<string,mixed>,cookie?:array<string,mixed>}|null
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

        /** @var array{created_at:int,last_seen_at:int,authenticated_at?:int,privilege_changed_at?:int,policy?:array<string,mixed>,cookie?:array<string,mixed>} $meta */
        return $meta;
    }

    /**
     * @return array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string}|null
     */
    private static function readStoredCookieParams(): ?array
    {
        $meta = $_SESSION[self::META_KEY] ?? null;
        if (!is_array($meta) || !array_key_exists('cookie', $meta)) {
            return null;
        }

        $cookie = $meta['cookie'];
        if (!is_array($cookie)
            || !array_key_exists('lifetime', $cookie)
            || !array_key_exists('path', $cookie)
            || !array_key_exists('domain', $cookie)
            || !array_key_exists('secure', $cookie)
            || !array_key_exists('httponly', $cookie)
            || !array_key_exists('samesite', $cookie)
            || $cookie['lifetime'] !== 0
            || !is_string($cookie['path'])
            || !str_starts_with($cookie['path'], '/')
            || preg_match('/[\x00-\x20\x7F,;]/', $cookie['path']) === 1
            || !is_string($cookie['domain'])
            || !is_bool($cookie['secure'])
            || $cookie['httponly'] !== true
            || !is_string($cookie['samesite'])
            || !in_array($cookie['samesite'], ['Lax', 'Strict', 'None'], true)) {
            throw new LogicException('Stored session cookie tuple is invalid.');
        }

        if ($cookie['domain'] !== '') {
            try {
                if (self::normalizeCookieDomain($cookie['domain']) !== $cookie['domain']) {
                    throw new LogicException('Stored session cookie tuple is invalid.');
                }
            } catch (InvalidArgumentException $exception) {
                throw new LogicException('Stored session cookie tuple is invalid.', 0, $exception);
            }
        }

        /** @var array{lifetime:int,path:string,domain:string,secure:bool,httponly:bool,samesite:string} $cookie */
        return $cookie;
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
        if (session_status() === PHP_SESSION_ACTIVE) {
            // Persist what PHP is actually configured to emit. Logout and migrations
            // must not need to re-run trusted-proxy detection after infrastructure changes.
            $meta['cookie'] = self::currentCookieParams();
        }

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

    private static function regenerateIdOrFail(string $errorMessage): void
    {
        if (!session_regenerate_id(true)) {
            throw new LogicException($errorMessage);
        }

        if (self::$manualCookieParams !== null) {
            if (!self::setSessionCookie(session_id(), self::$manualCookieParams)) {
                throw new LogicException('Unable to emit the rotated validated session cookie.');
            }
        }

        // session_regenerate_id() may replace prior Set-Cookie headers for the same
        // session name. Re-emit the authoritative old-scope deletion afterwards so a
        // migrated cookie cannot shadow the newly authenticated cookie.
        if (self::$pendingCookieExpiry !== null) {
            if (!self::expireCookie(self::$pendingCookieExpiry)) {
                throw new LogicException('Unable to expire the previous session cookie scope after session ID rotation.');
            }
            self::$pendingCookieExpiry = null;
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
