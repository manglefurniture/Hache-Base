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

$expectRejectedPreActive = static function (string $path, int $id, int $now) use ($http): void {
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => $path,
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
        Auth::login(['id' => $id, 'role' => 'user'], ['cookie_path' => '/'], $http, $now);
    } catch (LogicException) {
        $blocked = true;
    }

    assert($blocked === true);
    assert(session_id() === $preActiveId);
    assert(!array_key_exists('user', $_SESSION));
    assert(session_destroy());
    session_id('');
};

// Unknown browser-cookie provenance must fail closed even when runtime params expose
// the obviously different /admin scope.
$expectRejectedPreActive('/admin', 21, 7000);

// Regression for the subtle case from review: a framework may set runtime params to
// '/' before session_start() while the browser actually supplied an older /admin
// cookie. session_get_cookie_params() would appear to match, but cannot prove the
// incoming cookie's Path/Domain. Therefore even a runtime-exact pre-active tuple is
// rejected unless Hache Base itself established provenance in this request.
$expectRejectedPreActive('/', 22, 7100);

// Normal Hache-owned session creation remains supported and proves the gate does not
// block legitimate use when Hache Base starts the session itself.
Auth::login(['id' => 23, 'role' => 'user'], ['cookie_path' => '/'], $http, 7200);
assert(session_status() === PHP_SESSION_ACTIVE);
assert(Auth::user([], $http, 7201)['id'] === 23);
Auth::logout(['cookie_path' => '/'], $http, 7202);
assert(session_status() === PHP_SESSION_NONE);
assert($_SESSION === []);
assert(session_id() === '');

$cleanup();

echo "SESSION_PREACTIVE_COOKIE_POLICY_OK\n";
