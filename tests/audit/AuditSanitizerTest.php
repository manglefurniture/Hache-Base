<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/audit/AuditSanitizer.php';

use HacheBase\Audit\AuditSanitizer;

$input = [
    'name' => 'Example User',
    'password' => 'never-store-me',
    'nested' => [
        'token' => 'secret-token',
        'status' => 'active',
    ],
];

$result = AuditSanitizer::sanitize($input);

assert($result['name'] === 'Example User');
assert($result['password'] === '[REDACTED]');
assert($result['nested']['token'] === '[REDACTED]');
assert($result['nested']['status'] === 'active');

echo "AuditSanitizerTest OK\n";
