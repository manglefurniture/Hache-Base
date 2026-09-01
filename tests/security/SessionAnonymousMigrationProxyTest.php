<?php

declare(strict_types=1);

use HacheBase\Security\Auth;
use HacheBase\Security\RequestSecurity;

require_once __DIR__ . '/../../security/auth.php';

$tmp = sys_get_temp_dir() . '/hache-base-session-anon-migration-' . bin2hex(random_bytes(6));
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) {
    throw new RuntimeException('Unable to create session fixture directory.');
}

$cleanup = static function () use ($tmp): void {
    if (session_status() === PHP_SESSION_ACTIVE) {
        @session_destroy();
    }
    session_id('');
    foreach (glob($tmp . '/*') ?: [] as $file) {
        @unlink($file);
    }
    @rmdir($tmp);
};
register_shutdown_function($cleanup);

assert(ini_set('session.save_path', $tmp) !== false);
session_name('HACHEBASEANONMIGRATION');

$oldProxy = [
    'trusted_ips' => ['10.0.0.5'],
    'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
];
$oldRequest = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '10.0.0.5',
    'HTTP_X_FORWARDED_PROTO' => 'https',
];
$oldConfig = [
    'idle_timeout' => 60,
    'absolute_timeout' => 180,
    'same_site' => 'None',
    'cookie_path' => '/legacy-secure',
    'proxy' => $oldProxy,
];

assert(RequestSecurity::isHttps($oldRequest, $oldProxy) === true);
Auth::startSecureSession($oldConfig, $oldRequest, 6000);
assert(session_status() === PHP_SESSION_ACTIVE);
assert(!array_key_exists('user', $_SESSION));
$anonymousId = session_id();
assert($anonymousId !== '');
$oldParams = session_get_cookie_params();
assert($oldParams['secure'] === true);
assert($oldParams['samesite'] === 'None');
assert($oldParams['path'] === '/legacy-secure');
assert(session_write_close());
session_id('');

// Emulate a fresh worker/request after deploy. The browser supplies the real old
// cookie; runtime params no longer prove which tuple produced it. The persisted
// session metadata is the only authoritative source for reopening provenance.
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'domain' => '',
    'secure' => false,
    'httponly' => true,
    'samesite' => 'Lax',
]);
$_COOKIE[session_name()] = $anonymousId;

$newProxy = [
    'trusted_ips' => ['10.0.0.6'],
    'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
];
$newRequest = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '10.0.0.6',
    'HTTP_X_FORWARDED_PROTO' => 'https',
];
$newConfig = [
    'idle_timeout' => 60,
    'absolute_timeout' => 180,
    'same_site' => 'None',
    'cookie_path' => '/secure',
    'proxy' => $newProxy,
];

assert(RequestSecurity::isHttps($newRequest, $newProxy) === true);

// Regression: an incoming SameSite=None cookie created behind the old proxy must be
// reopened from its persisted cookie tuple, not by re-evaluating the old proxy policy
// against the new topology. The anonymous migration may then adopt the new policy.
Auth::login(['id' => 12, 'role' => 'user'], $newConfig, $newRequest, 6001);
$authenticatedId = session_id();
assert($authenticatedId !== '' && $authenticatedId !== $anonymousId);
$newParams = session_get_cookie_params();
assert($newParams['secure'] === true);
assert($newParams['samesite'] === 'None');
assert($newParams['path'] === '/secure');
assert(Auth::user([], $newRequest, 6002)['id'] === 12);

Auth::logout($newConfig, $newRequest, 6003);
assert(session_status() === PHP_SESSION_NONE);
assert($_SESSION === []);
assert(session_id() === '');

unset($_COOKIE[session_name()]);
$cleanup();

echo "SESSION_ANONYMOUS_MIGRATION_PROXY_OK\n";
