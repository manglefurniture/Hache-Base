<?php

declare(strict_types=1);

require_once __DIR__ . '/../../integrations/payments/WebhookHmac.php';

use HacheBase\Integrations\Payments\WebhookHmac;

$parts = WebhookHmac::parseKeyValueHeader('ts=12345, v1=abcdef, request-id=abc-123');
assert($parts['ts'] === '12345');
assert($parts['v1'] === 'abcdef');
assert($parts['request-id'] === 'abc-123');

$secret = 'test-secret';
$manifest = 'id:42;request-id:abc;ts:123;';
$signature = hash_hmac('sha256', $manifest, $secret);

assert(WebhookHmac::verifySha256($secret, $manifest, $signature) === true);
assert(WebhookHmac::verifySha256($secret, $manifest . 'tampered', $signature) === false);
assert(WebhookHmac::verifySha256('', $manifest, $signature) === false);
assert(WebhookHmac::verifySha256($secret, $manifest, 'not-a-signature') === false);

$secretWithWhitespace = " test-secret\t";
$whitespaceSignature = hash_hmac('sha256', $manifest, $secretWithWhitespace);
assert(WebhookHmac::verifySha256($secretWithWhitespace, $manifest, $whitespaceSignature) === true);
assert(WebhookHmac::verifySha256(trim($secretWithWhitespace), $manifest, $whitespaceSignature) === false);

echo "WebhookHmacTest OK\n";
