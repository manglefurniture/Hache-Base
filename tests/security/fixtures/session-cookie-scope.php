<?php

declare(strict_types=1);

use HacheBase\Security\Auth;

require_once __DIR__ . '/../../../security/auth.php';

session_name('HACHEBASESCOPE');

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
header('Content-Type: text/plain; charset=utf-8');

if ($path === '/health') {
    echo "OK\n";
    return;
}

if ($path === '/admin/login') {
    Auth::login(
        ['id' => 42, 'role' => 'user'],
        ['cookie_path' => '/admin'],
        $_SERVER,
        1000,
    );
    echo "LOGIN_OK\n";
    return;
}

if ($path === '/admin/touch') {
    Auth::startSecureSession([], $_SERVER, 1001);
    if (!isset($_SESSION['user']['id']) || $_SESSION['user']['id'] !== 42) {
        http_response_code(401);
        echo "MISSING_AUTH\n";
        return;
    }

    echo "TOUCH_OK\n";
    return;
}

if ($path === '/admin/anonymous') {
    Auth::startSecureSession(['cookie_path' => '/admin'], $_SERVER, 2000);
    echo "ANON_OK\n";
    return;
}

if ($path === '/admin/migrate-root') {
    Auth::login(
        ['id' => 43, 'role' => 'user'],
        ['cookie_path' => '/'],
        $_SERVER,
        2001,
    );
    echo "MIGRATE_OK\n";
    return;
}

if ($path === '/admin/check-root') {
    $user = Auth::user([], $_SERVER, 2002);
    if (!is_array($user) || ($user['id'] ?? null) !== 43) {
        http_response_code(401);
        echo "MIGRATED_AUTH_MISSING\n";
        return;
    }

    echo "MIGRATED_AUTH_OK\n";
    return;
}

// Seed a historical anonymous session outside Hache Base. Its browser cookie is
// scoped to /admin and its server-side data deliberately contains no SEC-007 metadata.
if ($path === '/admin/legacy-anonymous') {
    ini_set('session.use_strict_mode', '1');
    ini_set('session.use_cookies', '1');
    ini_set('session.use_only_cookies', '1');
    ini_set('session.use_trans_sid', '0');
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => '/admin',
        'domain' => '',
        'secure' => false,
        'httponly' => true,
        'samesite' => 'Lax',
    ]);

    if (!session_start()) {
        http_response_code(500);
        echo "LEGACY_ANON_START_FAILED\n";
        return;
    }

    $_SESSION['legacy_marker'] = 'anonymous-no-hache-meta';
    echo "LEGACY_ANON_OK\n";
    return;
}

// Hache Base owns session_start() here, but the browser already supplied a legacy
// /admin cookie. Without stored Hache metadata its original scope is unverifiable,
// so login must fail closed instead of creating an authenticated root cookie.
if ($path === '/admin/legacy-login-root') {
    try {
        Auth::login(
            ['id' => 45, 'role' => 'user'],
            ['cookie_path' => '/'],
            $_SERVER,
            4000,
        );
    } catch (LogicException) {
        if (array_key_exists('user', $_SESSION)) {
            http_response_code(500);
            echo "LEGACY_INCOMING_AUTH_ATTACHED\n";
            return;
        }

        if (($_SESSION['legacy_marker'] ?? null) !== 'anonymous-no-hache-meta') {
            http_response_code(500);
            echo "LEGACY_INCOMING_SESSION_REPLACED\n";
            return;
        }

        echo "LEGACY_INCOMING_REJECTED\n";
        return;
    }

    http_response_code(500);
    echo "LEGACY_INCOMING_NOT_REJECTED\n";
    return;
}

// Simulate a framework or historical bootstrap that starts PHP sessions before
// Hache Base while the process-level runtime still has session.use_cookies=0.
// This state is ambiguous when same-name cookies exist at multiple paths, so SEC-007
// deliberately rejects it instead of guessing which browser tuple is authoritative.
if ($path === '/preactive/login') {
    if (!session_start()) {
        http_response_code(500);
        echo "PREACTIVE_START_FAILED\n";
        return;
    }

    $_SESSION['framework_marker'] = 'must-not-authenticate';

    try {
        Auth::login(
            ['id' => 44, 'role' => 'user'],
            ['cookie_path' => '/preactive'],
            $_SERVER,
            3000,
        );
    } catch (LogicException) {
        if (array_key_exists('user', $_SESSION)) {
            http_response_code(500);
            echo "PREACTIVE_AUTH_ATTACHED\n";
            return;
        }

        echo "PREACTIVE_REJECTED\n";
        return;
    }

    http_response_code(500);
    echo "PREACTIVE_NOT_REJECTED\n";
    return;
}

http_response_code(404);
echo "NOT_FOUND\n";
