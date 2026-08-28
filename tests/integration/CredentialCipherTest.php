<?php

declare(strict_types=1);

require_once __DIR__ . '/../../integrations/payments/CredentialCipher.php';

use HacheBase\Integrations\Payments\CredentialCipher;

$key = 'ci-payment-master-key-2026-long-and-stable';
$cipher = new CredentialCipher($key);
$plain = 'secret-' . bin2hex(random_bytes(8));
$encrypted = $cipher->encrypt($plain);

assert($encrypted !== '');
assert(!str_contains($encrypted, $plain));
assert($cipher->decrypt($encrypted) === $plain);

$wrongKeyRejected = false;
try {
    (new CredentialCipher('another-master-key'))->decrypt($encrypted);
} catch (RuntimeException) {
    $wrongKeyRejected = true;
}
assert($wrongKeyRejected === true);

$envelope = json_decode((string) base64_decode($encrypted, true), true, 512, JSON_THROW_ON_ERROR);
assert(is_array($envelope));
assert(isset($envelope['data'], $envelope['tag']));

$tag = base64_decode((string) $envelope['tag'], true);
assert(is_string($tag) && strlen($tag) === 16);
$truncatedEnvelope = $envelope;
$truncatedEnvelope['tag'] = base64_encode(substr($tag, 0, 1));
$truncatedTagPayload = base64_encode(json_encode($truncatedEnvelope, JSON_THROW_ON_ERROR));

$truncatedTagRejected = false;
try {
    $cipher->decrypt($truncatedTagPayload);
} catch (RuntimeException) {
    $truncatedTagRejected = true;
}
assert($truncatedTagRejected === true);

$data = base64_decode((string) $envelope['data'], true);
assert(is_string($data) && $data !== '');
$data[0] = chr(ord($data[0]) ^ 1);
$envelope['data'] = base64_encode($data);
$tampered = base64_encode(json_encode($envelope, JSON_THROW_ON_ERROR));

$tamperRejected = false;
try {
    $cipher->decrypt($tampered);
} catch (RuntimeException) {
    $tamperRejected = true;
}
assert($tamperRejected === true);

$emptyKeyRejected = false;
try {
    new CredentialCipher('   ');
} catch (InvalidArgumentException) {
    $emptyKeyRejected = true;
}
assert($emptyKeyRejected === true);

$sql = file_get_contents(__DIR__ . '/../../database/modules/payment-gateway-credentials.sql');
assert(is_string($sql));
assert(str_contains($sql, 'CREATE TABLE IF NOT EXISTS payment_gateway_credentials'));
assert(str_contains($sql, 'webhook_secret_enc TEXT NULL'));
assert(str_contains($sql, 'current_credential_id BIGINT UNSIGNED NULL'));
assert(str_contains($sql, 'ON UPDATE CASCADE ON DELETE RESTRICT'));
assert(str_contains($sql, 'payment_credential_id'));

$doc = file_get_contents(__DIR__ . '/../../integrations/payments/CREDENTIAL-VERSIONING.md');
assert(is_string($doc));
assert(str_contains($doc, 'Versiones token-only solo para legado'));
assert(str_contains($doc, 'Rotación serializada'));
assert(str_contains($doc, 'Retorno por versión'));
assert(str_contains($doc, 'Webhook histórico'));

echo "CredentialCipherTest OK\n";
