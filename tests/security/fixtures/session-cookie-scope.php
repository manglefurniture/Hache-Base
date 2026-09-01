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

// Simulate a framework or historical bootstrap that starts PHP sessions before
// Hache Base while the process-level runtime still has session.use_cookies=0.
if ($path === '/preactive/login') {
    if (!session_start()) {
        http_response_code(500);
        echo "PREACTIVE_START_FAILED\n";
        return;
    }

    $_SESSION['framework_marker'] = 'preserve-me';
    Auth::login(
        ['id' => 44, 'role' => 'user'],
        ['cookie_path' => '/preactive'],
        $_SERVER,
        3000,
    );

    if (($_SESSION['framework_marker'] ?? null) !== 'preserve-me') {
        http_response_code(500);
        echo "PREACTIVE_SNAPSHOT_LOST\n";
        return;
    }

    echo "PREACTIVE_LOGIN_OK\n";
    return;
}

if ($path === '/preactive/check') {
    if (!session_start()) {
        http_response_code(500);
        echo "PREACTIVE_START_FAILED\n";
        return;
    }

    $user = Auth::user([], $_SERVER, 3001);
    if (!is_array($user) || ($user['id'] ?? null) !== 44) {
        http_response_code(401);
        echo "PREACTIVE_AUTH_MISSING\n";
        return;
    }

    echo "PREACTIVE_AUTH_OK\n";
    return;
}

http_response_code(404);
echo "NOT_FOUND\n";
