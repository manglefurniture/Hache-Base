<?php

declare(strict_types=1);

use HacheBase\Security\Headers;

require_once __DIR__ . '/../../security/headers.php';

$https = [
    'HTTPS' => 'on',
    'REMOTE_ADDR' => '203.0.113.10',
];

$headers = Headers::build([], $https);
assert($headers['X-Content-Type-Options'] === 'nosniff');
assert($headers['X-Frame-Options'] === 'SAMEORIGIN');
assert($headers['Referrer-Policy'] === 'strict-origin-when-cross-origin');
assert($headers['Permissions-Policy'] === 'geolocation=(), microphone=(), camera=()');
assert($headers['Strict-Transport-Security'] === 'max-age=31536000');
assert(!str_contains($headers['Strict-Transport-Security'], 'includeSubDomains'));
assert(!str_contains($headers['Strict-Transport-Security'], 'preload'));
assert(!array_key_exists('Content-Security-Policy', $headers));
assert(!array_key_exists('Content-Security-Policy-Report-Only', $headers));

$http = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '203.0.113.10',
];
assert(!array_key_exists('Strict-Transport-Security', Headers::build([], $http)));

// Never trust X-Forwarded-Proto from an arbitrary client.
$spoofedProxy = $http + ['HTTP_X_FORWARDED_PROTO' => 'https'];
assert(!array_key_exists('Strict-Transport-Security', Headers::build([], $spoofedProxy)));

// A forwarded scheme is accepted only from an explicitly trusted proxy IP.
$trustedProxyConfig = [
    'proxy' => [
        'trusted_ips' => ['10.0.0.5'],
    ],
];
$trustedProxyRequest = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '10.0.0.5',
    'HTTP_X_FORWARDED_PROTO' => 'https, http',
];
assert(
    Headers::build($trustedProxyConfig, $trustedProxyRequest)['Strict-Transport-Security']
        === 'max-age=31536000',
);

$untrustedProxyRequest = $trustedProxyRequest;
$untrustedProxyRequest['REMOTE_ADDR'] = '10.0.0.6';
assert(!array_key_exists('Strict-Transport-Security', Headers::build($trustedProxyConfig, $untrustedProxyRequest)));

$hstsOptIn = Headers::build([
    'hsts' => [
        'include_subdomains' => true,
        'preload' => true,
    ],
], $https);
assert(
    $hstsOptIn['Strict-Transport-Security']
        === 'max-age=31536000; includeSubDomains; preload',
);

$hstsDisabled = Headers::build([
    'hsts' => ['enabled' => false],
], $https);
assert(!array_key_exists('Strict-Transport-Security', $hstsDisabled));

$reportOnly = Headers::build([
    'csp' => [
        'mode' => 'report-only',
        'directives' => [
            'default-src' => ["'self'"],
            'img-src' => ["'self'", 'https://images.example.test'],
            'frame-ancestors' => ["'self'"],
            'report-uri' => ['/csp-report'],
        ],
    ],
], $https);
assert(!array_key_exists('Content-Security-Policy', $reportOnly));
assert(
    $reportOnly['Content-Security-Policy-Report-Only']
        === "default-src 'self'; img-src 'self' https://images.example.test; frame-ancestors 'self'; report-uri /csp-report",
);

$enforced = Headers::build([
    'csp' => [
        'mode' => 'enforce',
        'directives' => [
            'default-src' => ["'self'"],
            'object-src' => ["'none'"],
        ],
    ],
], $https);
assert(
    $enforced['Content-Security-Policy']
        === "default-src 'self'; object-src 'none'",
);
assert(!array_key_exists('Content-Security-Policy-Report-Only', $enforced));

assert(
    Headers::buildCspPolicy([
        'default-src' => ["'self'"],
        'upgrade-insecure-requests' => null,
    ]) === "default-src 'self'; upgrade-insecure-requests",
);

$throws = static function (callable $callback): bool {
    try {
        $callback();
    } catch (InvalidArgumentException) {
        return true;
    }

    return false;
};

assert($throws(static fn () => Headers::build([
    'hsts' => ['preload' => true],
], $https)));

assert($throws(static fn () => Headers::build([
    'hsts' => [
        'include_subdomains' => true,
        'preload' => true,
        'max_age' => 86400,
    ],
], $https)));

assert($throws(static fn () => Headers::build([
    'csp' => [
        'mode' => 'report-only',
        'directives' => [],
    ],
], $https)));

assert($throws(static fn () => Headers::build([
    'csp' => [
        'mode' => 'enforce',
        'directives' => [
            'script-src' => ["'self'", "https://cdn.example.test; script-src 'unsafe-inline'"],
        ],
    ],
], $https)));

assert($throws(static fn () => Headers::build([
    'permissions_policy' => "camera=()\r\nX-Injected: yes",
], $https)));

assert($throws(static fn () => Headers::build([
    'proxy' => ['trusted_ips' => ['not-an-ip']],
], $https)));

assert($throws(static fn () => Headers::build([
    'unknown_option' => true,
], $https)));

assert($throws(static fn () => Headers::build([
    'x_frame_options' => 'ALLOWALL',
], $https)));

echo "SECURITY_HEADERS_OK\n";
