<?php

declare(strict_types=1);

use HacheBase\Security\SessionSecurity;

require_once __DIR__ . '/../../security/session-security.php';

$throwsInvalid = static function (callable $callback): bool {
    try {
        $callback();
    } catch (InvalidArgumentException) {
        return true;
    }

    return false;
};

$normalized = SessionSecurity::resolveConfig(['cookie_domain' => 'EXAMPLE.TEST']);
assert($normalized['cookie_domain'] === 'example.test');

$punycode = SessionSecurity::resolveConfig(['cookie_domain' => 'xn--bcher-kva.example']);
assert($punycode['cookie_domain'] === 'xn--bcher-kva.example');

foreach ([
    'example.com/path',
    'foo=bar',
    '.example.com',
    'example.com.',
    'bad,example.com',
    "bad\r\nexample.com",
    'foo_bar.example',
    '-bad.example',
    'bad-.example',
    'bücher.example',
    '127.0.0.1',
    '2130706433',
    '127.1',
    '0177.0.0.1',
    '0x7f000001',
] as $invalidDomain) {
    assert($throwsInvalid(static fn () => SessionSecurity::resolveConfig([
        'cookie_domain' => $invalidDomain,
    ])));
}

echo "SESSION_COOKIE_DOMAIN_VALIDATION_OK\n";
