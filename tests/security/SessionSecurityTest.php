<?php

declare(strict_types=1);

use HacheBase\Security\Auth;
use HacheBase\Security\RequestSecurity;
use HacheBase\Security\SessionSecurity;

require_once __DIR__ . '/../../security/auth.php';

$https = [
    'HTTPS' => 'on',
    'SERVER_PORT' => '443',
    'REMOTE_ADDR' => '203.0.113.10',
];
$http = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '203.0.113.10',
];

$cookie = SessionSecurity::buildCookieParams([], $https);
assert($cookie['secure'] === true);
assert($cookie['httponly'] === true);
assert($cookie['samesite'] === 'Lax');
assert($cookie['path'] === '/');
assert(!array_key_exists('domain', $cookie));

$httpCookie = SessionSecurity::buildCookieParams([], $http);
assert($httpCookie['secure'] === false);

$spoofed = $http + ['HTTP_X_FORWARDED_PROTO' => 'https'];
assert(RequestSecurity::isHttps($spoofed) === false);
assert(SessionSecurity::buildCookieParams([], $spoofed)['secure'] === false);

$proxyConfig = [
    'trusted_ips' => ['10.0.0.5'],
    'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
];
$trustedProxyRequest = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '10.0.0.5',
    'HTTP_X_FORWARDED_PROTO' => 'https',
];
assert(RequestSecurity::isHttps($trustedProxyRequest, $proxyConfig) === true);
assert(SessionSecurity::buildCookieParams(['proxy' => $proxyConfig], $trustedProxyRequest)['secure'] === true);

$multiHop = $trustedProxyRequest;
$multiHop['HTTP_X_FORWARDED_PROTO'] = 'https, http';
assert(RequestSecurity::isHttps($multiHop, $proxyConfig) === false);
assert(SessionSecurity::buildCookieParams(['proxy' => $proxyConfig], $multiHop)['secure'] === false);

$untrusted = $trustedProxyRequest;
$untrusted['REMOTE_ADDR'] = '10.0.0.6';
assert(RequestSecurity::isHttps($untrusted, $proxyConfig) === false);

$strictCookie = SessionSecurity::buildCookieParams([
    'same_site' => 'strict',
    'cookie_path' => '/admin',
    'cookie_domain' => 'example.test',
], $https);
assert($strictCookie['samesite'] === 'Strict');
assert($strictCookie['path'] === '/admin');
assert($strictCookie['domain'] === 'example.test');

$throwsInvalid = static function (callable $callback): bool {
    try {
        $callback();
    } catch (InvalidArgumentException) {
        return true;
    }

    return false;
};

$throwsLogic = static function (callable $callback): bool {
    try {
        $callback();
    } catch (LogicException) {
        return true;
    }

    return false;
};

assert($throwsInvalid(static fn () => SessionSecurity::buildCookieParams(['same_site' => 'None'], $http)));
assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig(['idle_timeout' => 0])));
assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig([
    'idle_timeout' => 120,
    'absolute_timeout' => 60,
])));
assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig(['cookie_path' => 'relative'])));
assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig(['cookie_domain' => "bad\r\nSet-Cookie:x"])));
assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig([
    'proxy' => ['trusted_ips' => ['not-an-ip']],
])));
assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig(['unknown' => true])));

$tmp = sys_get_temp_dir() . '/hache-base-session-' . bin2hex(random_bytes(6));
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) {
    throw new RuntimeException('Unable to create session fixture directory.');
}

$cleanup = static function () use ($tmp): void {
    foreach (glob($tmp . '/*') ?: [] as $file) {
        @unlink($file);
    }
    @rmdir($tmp);
};
register_shutdown_function($cleanup);

assert(ini_set('session.save_path', $tmp) !== false);
session_name('HACHEBASETEST');

$config = [
    'idle_timeout' => 60,
    'absolute_timeout' => 180,
];

Auth::startSecureSession($config, $https, 1000);
assert(session_status() === PHP_SESSION_ACTIVE);
$anonymousId = session_id();
assert($anonymousId !== '');
$params = session_get_cookie_params();
assert($params['secure'] === true);
assert($params['httponly'] === true);
assert($params['samesite'] === 'Lax');
assert((string)ini_get('session.use_strict_mode') === '1');
assert((string)ini_get('session.use_only_cookies') === '1');
assert((string)ini_get('session.use_trans_sid') === '0');

assert($throwsLogic(static fn () => Auth::elevate(['id' => 7, 'role' => 'admin'], $config, $https, 1000)));

Auth::login(['id' => 7, 'role' => 'user'], $config, $https, 1000);
$loginId = session_id();
assert($loginId !== '' && $loginId !== $anonymousId);
assert(Auth::user($config, $https, 1001)['role'] === 'user');

$beforeWrongPrincipal = session_id();
assert($throwsInvalid(static fn () => Auth::elevate(['id' => 8, 'role' => 'admin'], $config, $https, 1002)));
assert(session_id() === $beforeWrongPrincipal);
assert(Auth::user($config, $https, 1003)['id'] === 7);

$beforeElevation = session_id();
Auth::elevate(['id' => 7, 'role' => 'admin'], $config, $https, 1010);
$elevatedId = session_id();
assert($elevatedId !== '' && $elevatedId !== $beforeElevation);
assert(Auth::user($config, $https, 1011)['role'] === 'admin');

// Do not refresh again before the boundary: idle timeout is exact and clears auth.
$sessionBeforeIdleExpiry = session_id();
assert(Auth::user($config, $https, 1071) === null);
assert(session_id() !== '' && session_id() !== $sessionBeforeIdleExpiry);

$absoluteConfig = [
    'idle_timeout' => 120,
    'absolute_timeout' => 180,
];
Auth::login(['id' => 8, 'role' => 'user'], $absoluteConfig, $https, 2000);
$sessionBeforeAbsoluteExpiry = session_id();
assert(Auth::user($absoluteConfig, $https, 2119)['id'] === 8);
assert(Auth::user($absoluteConfig, $https, 2179)['id'] === 8);
assert(Auth::user($absoluteConfig, $https, 2180) === null);
assert(session_id() !== '' && session_id() !== $sessionBeforeAbsoluteExpiry);

Auth::login(['id' => 9, 'role' => 'user'], $config, $https, 3000);
assert(Auth::user($config, $https, 3001)['id'] === 9);
Auth::logout($config, $https, 3002);
assert(session_status() === PHP_SESSION_NONE);
assert($_SESSION === []);
assert(session_id() === '');

$cleanup();

echo "SESSION_SECURITY_OK\n";
