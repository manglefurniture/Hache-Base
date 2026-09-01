<?php

declare(strict_types=1);

use HacheBase\Security\Headers;

require_once __DIR__ . '/../../security/headers.php';

$https = [
    'HTTPS' => 'on',
    'REMOTE_ADDR' => '203.0.113.10',
];

// Baseline defensive headers stay available with no project-specific policy guessed.
$headers = Headers::build([], $https);
assert($headers['X-Content-Type-Options'] === 'nosniff');
assert($headers['X-Frame-Options'] === 'SAMEORIGIN');
assert($headers['Referrer-Policy'] === 'strict-origin-when-cross-origin');
assert($headers['Permissions-Policy'] === 'geolocation=(), microphone=(), camera=()');
assert(!array_key_exists('Strict-Transport-Security', $headers));
assert(!array_key_exists('Content-Security-Policy', $headers));
assert(!array_key_exists('Content-Security-Policy-Report-Only', $headers));

// HSTS is explicit because the helper cannot prove that HTTPS is stable for the project.
$hstsDirect = Headers::build([
    'hsts' => ['enabled' => true],
], $https);
assert($hstsDirect['Strict-Transport-Security'] === 'max-age=31536000');
assert(!str_contains($hstsDirect['Strict-Transport-Security'], 'includeSubDomains'));
assert(!str_contains($hstsDirect['Strict-Transport-Security'], 'preload'));

$requestSchemeHttps = Headers::build([
    'hsts' => ['enabled' => true],
], [
    'REQUEST_SCHEME' => 'https',
    'REMOTE_ADDR' => '203.0.113.10',
]);
assert($requestSchemeHttps['Strict-Transport-Security'] === 'max-age=31536000');

$http = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '203.0.113.10',
];
assert(!array_key_exists('Strict-Transport-Security', Headers::build([
    'hsts' => ['enabled' => true],
], $http)));

// Never trust X-Forwarded-Proto from an arbitrary client.
$spoofedProxy = $http + ['HTTP_X_FORWARDED_PROTO' => 'https'];
assert(!array_key_exists('Strict-Transport-Security', Headers::build([
    'hsts' => ['enabled' => true],
], $spoofedProxy)));

// Forwarded HTTPS is accepted only from an explicitly trusted proxy IP and one
// authoritative, normalized proto value.
$trustedProxyConfig = [
    'hsts' => ['enabled' => true],
    'proxy' => [
        'trusted_ips' => ['10.0.0.5'],
    ],
];
$trustedProxyRequest = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '10.0.0.5',
    'HTTP_X_FORWARDED_PROTO' => 'https',
];
assert(
    Headers::build($trustedProxyConfig, $trustedProxyRequest)['Strict-Transport-Security']
        === 'max-age=31536000',
);

$multiHopProto = $trustedProxyRequest;
$multiHopProto['HTTP_X_FORWARDED_PROTO'] = 'https, http';
assert(!array_key_exists('Strict-Transport-Security', Headers::build($trustedProxyConfig, $multiHopProto)));

$untrustedProxyRequest = $trustedProxyRequest;
$untrustedProxyRequest['REMOTE_ADDR'] = '10.0.0.6';
assert(!array_key_exists('Strict-Transport-Security', Headers::build($trustedProxyConfig, $untrustedProxyRequest)));

$customProxyHeader = Headers::build([
    'hsts' => ['enabled' => true],
    'proxy' => [
        'trusted_ips' => ['2001:db8::10'],
        'forwarded_proto_header' => 'HTTP_X_SCHEME',
    ],
], [
    'REMOTE_ADDR' => '2001:db8::10',
    'HTTP_X_SCHEME' => 'https',
]);
assert($customProxyHeader['Strict-Transport-Security'] === 'max-age=31536000');

// includeSubDomains/preload never appear unless they are separately explicit.
$hstsSubdomains = Headers::build([
    'hsts' => [
        'enabled' => true,
        'include_subdomains' => true,
    ],
], $https);
assert($hstsSubdomains['Strict-Transport-Security'] === 'max-age=31536000; includeSubDomains');

$hstsPreload = Headers::build([
    'hsts' => [
        'enabled' => true,
        'include_subdomains' => true,
        'preload' => true,
    ],
], $https);
assert(
    $hstsPreload['Strict-Transport-Security']
        === 'max-age=31536000; includeSubDomains; preload',
);

$hstsClear = Headers::build([
    'hsts' => [
        'enabled' => true,
        'max_age' => 0,
    ],
], $https);
assert($hstsClear['Strict-Transport-Security'] === 'max-age=0');

// CSP is project-specific and starts off. The helper supports a report-only
// observation phase before an explicit enforcement promotion.
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

$denyFrame = Headers::build([
    'x_frame_options' => 'deny',
], $https);
assert($denyFrame['X-Frame-Options'] === 'DENY');

$throws = static function (callable $callback): bool {
    try {
        $callback();
    } catch (InvalidArgumentException) {
        return true;
    }

    return false;
};

assert($throws(static fn () => Headers::build([
    'hsts' => [
        'enabled' => true,
        'preload' => true,
    ],
], $https)));

assert($throws(static fn () => Headers::build([
    'hsts' => [
        'enabled' => true,
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

assert($throws(static fn () => Headers::buildCspPolicy([
    'Script-Src' => ["'self'"],
])));

assert($throws(static fn () => Headers::build([
    'permissions_policy' => "camera=()\r\nX-Injected: yes",
], $https)));

assert($throws(static fn () => Headers::build([
    'proxy' => ['trusted_ips' => ['not-an-ip']],
], $https)));

assert($throws(static fn () => Headers::build([
    'proxy' => ['forwarded_proto_header' => "HTTP_X_PROTO\r\nX_BAD"],
], $https)));

assert($throws(static fn () => Headers::build([
    'unknown_option' => true,
], $https)));

assert($throws(static fn () => Headers::build([
    'x_frame_options' => 'ALLOWALL',
], $https)));

echo "SECURITY_HEADERS_OK\n";
