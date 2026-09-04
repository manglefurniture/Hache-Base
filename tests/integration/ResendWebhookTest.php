<?php

declare(strict_types=1);

require_once __DIR__ . '/../../integrations/email/EmailDeliveryStatus.php';
require_once __DIR__ . '/../../integrations/email/ResendWebhook.php';

use HacheBase\Integrations\Email\EmailDeliveryStatus;
use HacheBase\Integrations\Email\ResendWebhook;

$secretBytes = 'fixture-signing-secret-32-bytes!!';
$signingSecret = 'whsec_' . base64_encode($secretBytes);
$eventId = 'msg_fixture_event_001';
$timestamp = 1788566400;

$payloadFor = static function (string $type, bool $includeMessageId = true, string $createdAt = '2026-09-04T23:00:00.123456Z'): string {
    $data = [
        'to' => ['person@example.test'],
        'subject' => 'Sensitive fixture subject',
        'tags' => ['customer' => 'should-not-leak'],
    ];
    if ($includeMessageId) {
        $data['email_id'] = 'email_provider_123';
    }

    return json_encode([
        'type' => $type,
        'created_at' => $createdAt,
        'data' => $data,
    ], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
};

$headersFor = static function (string $payload) use ($secretBytes, $eventId, $timestamp): array {
    $signed = $eventId . '.' . $timestamp . '.' . $payload;
    $signature = base64_encode(hash_hmac('sha256', $signed, $secretBytes, true));

    return [
        'Svix-Id' => $eventId,
        'Svix-Timestamp' => (string) $timestamp,
        'Svix-Signature' => 'v1,invalid-fixture v1,' . $signature,
    ];
};

$mapping = [
    'email.sent' => EmailDeliveryStatus::ACCEPTED,
    'email.delivered' => EmailDeliveryStatus::DELIVERED,
    'email.delivery_delayed' => EmailDeliveryStatus::DELAYED,
    'email.bounced' => EmailDeliveryStatus::BOUNCED,
    'email.failed' => EmailDeliveryStatus::FAILED,
    'email.suppressed' => EmailDeliveryStatus::SUPPRESSED,
];

foreach ($mapping as $eventType => $expectedStatus) {
    $payload = $payloadFor($eventType);
    $headers = $headersFor($payload);

    assert(ResendWebhook::verify($payload, $headers, $signingSecret, $timestamp) === true);
    $event = ResendWebhook::verifyAndNormalize($payload, $headers, $signingSecret, $timestamp);

    assert($event['provider'] === 'resend');
    assert($event['external_event_id'] === $eventId);
    assert($event['provider_event_type'] === $eventType);
    assert($event['provider_message_id'] === 'email_provider_123');
    assert($event['delivery_status'] === $expectedStatus);
    assert($event['occurred_at'] === '2026-09-04T23:00:00.123456Z');
    assert($event['payload_sha256'] === hash('sha256', $payload));
    assert($event['supported'] === true);
    assert(!array_key_exists('to', $event));
    assert(!array_key_exists('subject', $event));
    assert(!array_key_exists('tags', $event));
    assert(!array_key_exists('payload', $event));
}

$payload = $payloadFor('email.delivered');
$headers = $headersFor($payload);
assert(ResendWebhook::verify($payload . ' ', $headers, $signingSecret, $timestamp) === false);
assert(ResendWebhook::verify($payload, $headers, 'bad-secret', $timestamp) === false);
assert(ResendWebhook::verify($payload, $headers, $signingSecret, $timestamp + 301, 300) === false);
assert(ResendWebhook::verify($payload, ['Svix-Id' => $eventId], $signingSecret, $timestamp) === false);
assert(ResendWebhook::verify($payload, [
    'Svix-Id' => $eventId,
    'Svix-Timestamp' => str_repeat('9', 20),
    'Svix-Signature' => 'v1,anything',
], $signingSecret, $timestamp) === false);

$unsupportedPayload = $payloadFor('email.opened', false);
$unsupported = ResendWebhook::verifyAndNormalize(
    $unsupportedPayload,
    $headersFor($unsupportedPayload),
    $signingSecret,
    $timestamp,
);
assert($unsupported['supported'] === false);
assert($unsupported['delivery_status'] === null);
assert($unsupported['provider_message_id'] === null);

$thrown = false;
try {
    $missingIdPayload = $payloadFor('email.bounced', false);
    ResendWebhook::verifyAndNormalize(
        $missingIdPayload,
        $headersFor($missingIdPayload),
        $signingSecret,
        $timestamp,
    );
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$thrown = false;
try {
    $relativeDatePayload = $payloadFor('email.delivered', true, 'tomorrow');
    ResendWebhook::verifyAndNormalize(
        $relativeDatePayload,
        $headersFor($relativeDatePayload),
        $signingSecret,
        $timestamp,
    );
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$thrown = false;
try {
    ResendWebhook::verifyAndNormalize($payload, $headers, 'whsec_' . base64_encode('wrong'), $timestamp);
} catch (RuntimeException) {
    $thrown = true;
}
assert($thrown === true);

echo "ResendWebhookTest OK\n";
