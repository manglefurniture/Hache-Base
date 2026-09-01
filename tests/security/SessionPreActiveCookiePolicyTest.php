<?php

declare(strict_types=1);

use HacheBase\Security\Auth;

require_once __DIR__ . '/../../security/auth.php';

$tmp = sys_get_temp_dir() . '/hache-base-session-preactive-' . bin2hex(random_bytes(6));
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
assert(ini_set('session.use_strict_mode', '1') !== false);
assert(ini_set('session.use_cookies', '1') !== false);
assert(ini_set('session.use_only_cookies', '1') !== false);
assert(ini_set('session.use_trans_sid', '0') !== false);
session_name('HACHEBASEPREACTIVE');

$http = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '203.0.113.20',
];

// Framework opens a standards-compliant anonymous session before Hache Base, but
// scopes its cookie to /admin. The SEC-007 candidate later requests the root scope.
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/admin',
    'domain' => '',
    'secure' => false,
    'httponly' => true,
    'samesite' => 'Lax',
]);
assert(session_start());
$preActiveId = session_id();
assert($preActiveId !== '');

$blocked = false;
try {
    Auth::login(['id' => 21, 'role' => 'user'], ['cookie_path' => '/'], $http, 7000);
} catch (LogicException) {
    $blocked = true;
}

assert($blocked === true);
assert(session_id() === $preActiveId);
assert(!array_key_exists('user', $_SESSION));
assert(session_destroy());
session_id('');

// An externally pre-active session whose tuple already exactly matches the requested
// policy is adoptable; this guards against turning the fail-closed check into a ban on
// every compliant framework-owned session.
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'domain' => '',
    'secure' => false,
    'httponly' => true,
    'samesite' => 'Lax',
]);
assert(session_start());
$matchingId = session_id();
assert($matchingId !== '');

Auth::login(['id' => 22, 'role' => 'user'], ['cookie_path' => '/'], $http, 7100);
assert(session_id() !== '' && session_id() !== $matchingId);
assert(Auth::user([], $http, 7101)['id'] === 22);

Auth::logout(['cookie_path' => '/'], $http, 7102);
assert(session_status() === PHP_SESSION_NONE);
assert($_SESSION === []);
assert(session_id() === '');

$cleanup();

echo "SESSION_PREACTIVE_COOKIE_POLICY_OK\n";
