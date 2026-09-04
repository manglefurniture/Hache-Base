<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Email;

use InvalidArgumentException;
use JsonException;
use RuntimeException;

final class ResendWebhook
{
    private const EVENT_STATUS = [
        'email.sent' => EmailDeliveryStatus::ACCEPTED,
        'email.delivered' => EmailDeliveryStatus::DELIVERED,
        'email.delivery_delayed' => EmailDeliveryStatus::DELAYED,
        'email.bounced' => EmailDeliveryStatus::BOUNCED,
        'email.failed' => EmailDeliveryStatus::FAILED,
        'email.suppressed' => EmailDeliveryStatus::SUPPRESSED,
    ];

    /**
     * Verifica el formato Svix usado por los webhooks de Resend.
     *
     * El payload debe ser el body RAW exacto recibido por HTTP. Parsearlo y volverlo
     * a serializar antes de verificar cambia los bytes firmados.
     *
     * @param array<string,string> $headers
     */
    public static function verify(
        string $payload,
        array $headers,
        string $signingSecret,
        ?int $now = null,
        int $toleranceSeconds = 300,
    ): bool {
        if ($toleranceSeconds < 0) {
            throw new InvalidArgumentException('La tolerancia de firma no puede ser negativa.');
        }

        $messageId = self::header($headers, 'svix-id');
        $timestampRaw = self::header($headers, 'svix-timestamp');
        $signatureHeader = self::header($headers, 'svix-signature');

        if ($messageId === '' || $timestampRaw === '' || $signatureHeader === '') {
            return false;
        }
        if (!preg_match('/^[0-9]{1,12}$/', $timestampRaw)) {
            return false;
        }

        $timestamp = (int) $timestampRaw;
        if ($timestamp <= 0) {
            return false;
        }
        $now ??= time();
        if (abs($now - $timestamp) > $toleranceSeconds) {
            return false;
        }

        $secret = trim($signingSecret);
        if (!str_starts_with($secret, 'whsec_')) {
            return false;
        }
        $secretBytes = base64_decode(substr($secret, 6), true);
        if ($secretBytes === false || $secretBytes === '') {
            return false;
        }

        $signedContent = $messageId . '.' . $timestampRaw . '.' . $payload;
        $expected = base64_encode(hash_hmac('sha256', $signedContent, $secretBytes, true));

        foreach (preg_split('/\s+/', trim($signatureHeader)) ?: [] as $candidate) {
            $parts = explode(',', $candidate, 2);
            if (count($parts) !== 2 || $parts[0] !== 'v1') {
                continue;
            }
            if (hash_equals($expected, $parts[1])) {
                return true;
            }
        }

        return false;
    }

    /**
     * Verifica y reduce el webhook a metadata mínima apta para inbox/proyección.
     * No devuelve destinatario, asunto, body, tags ni el payload original.
     *
     * @param array<string,string> $headers
     * @return array{
     *   provider:string,
     *   external_event_id:string,
     *   provider_event_type:string,
     *   provider_message_id:?string,
     *   delivery_status:?string,
     *   occurred_at:string,
     *   payload_sha256:string,
     *   supported:bool
     * }
     */
    public static function verifyAndNormalize(
        string $payload,
        array $headers,
        string $signingSecret,
        ?int $now = null,
        int $toleranceSeconds = 300,
    ): array {
        if (!self::verify($payload, $headers, $signingSecret, $now, $toleranceSeconds)) {
            throw new RuntimeException('Firma de webhook de correo inválida o expirada.');
        }

        try {
            $decoded = json_decode($payload, true, 64, JSON_THROW_ON_ERROR);
        } catch (JsonException $e) {
            throw new InvalidArgumentException('El webhook de correo no contiene JSON válido.', 0, $e);
        }
        if (!is_array($decoded)) {
            throw new InvalidArgumentException('El webhook de correo debe ser un objeto JSON.');
        }

        $eventId = self::header($headers, 'svix-id');
        self::assertBoundedIdentifier($eventId, 191, 'external_event_id');

        $eventType = strtolower(trim((string) ($decoded['type'] ?? '')));
        self::assertBoundedIdentifier($eventType, 128, 'event_type');

        $occurredAt = trim((string) ($decoded['created_at'] ?? ''));
        self::assertTimestamp($occurredAt);

        $status = self::EVENT_STATUS[$eventType] ?? null;
        $messageId = null;
        if ($status !== null) {
            $data = $decoded['data'] ?? null;
            if (!is_array($data)) {
                throw new InvalidArgumentException('El evento de correo soportado no contiene data válida.');
            }
            $messageId = trim((string) ($data['email_id'] ?? ''));
            self::assertBoundedIdentifier($messageId, 191, 'provider_message_id');
        }

        return [
            'provider' => 'resend',
            'external_event_id' => $eventId,
            'provider_event_type' => $eventType,
            'provider_message_id' => $messageId,
            'delivery_status' => $status,
            'occurred_at' => $occurredAt,
            'payload_sha256' => hash('sha256', $payload),
            'supported' => $status !== null,
        ];
    }

    /** @param array<string,string> $headers */
    private static function header(array $headers, string $wanted): string
    {
        foreach ($headers as $name => $value) {
            if (strtolower(trim((string) $name)) === $wanted) {
                return trim((string) $value);
            }
        }
        return '';
    }

    private static function assertBoundedIdentifier(string $value, int $maxLength, string $field): void
    {
        if ($value === '' || strlen($value) > $maxLength || preg_match('/[\x00-\x1F\x7F]/', $value)) {
            throw new InvalidArgumentException('Identificador de webhook inválido: ' . $field);
        }
    }

    private static function assertTimestamp(string $value): void
    {
        if (!preg_match(
            '/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/',
            $value,
        )) {
            throw new InvalidArgumentException('created_at del webhook de correo no tiene formato ISO-8601 esperado.');
        }
        try {
            new \DateTimeImmutable($value);
        } catch (\Throwable $e) {
            throw new InvalidArgumentException('created_at del webhook de correo no es válido.', 0, $e);
        }
    }
}
