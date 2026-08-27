<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Email;

use InvalidArgumentException;
use RuntimeException;
use Throwable;

final class ResendMailer implements TransactionalMailer
{
    private const DEFAULT_ENDPOINT = 'https://api.resend.com/emails';

    public function __construct(
        private string $apiKey,
        private string $from,
        private string $fromName = '',
        private string $endpoint = self::DEFAULT_ENDPOINT,
    ) {
        $this->apiKey = trim($this->apiKey);
        $this->from = trim($this->from);
        $this->fromName = trim($this->fromName);
        $this->endpoint = trim($this->endpoint);

        if ($this->apiKey === '') {
            throw new InvalidArgumentException('Falta la API key del proveedor de correo.');
        }
        if (filter_var($this->from, FILTER_VALIDATE_EMAIL) === false) {
            throw new InvalidArgumentException('El remitente de correo no es válido.');
        }
        if ($this->endpoint === '') {
            throw new InvalidArgumentException('El endpoint de correo no puede estar vacío.');
        }
    }

    public function sendText(string $to, string $subject, string $text): string
    {
        $to = trim($to);
        $subject = trim($subject);

        if (filter_var($to, FILTER_VALIDATE_EMAIL) === false) {
            throw new InvalidArgumentException('El destinatario de correo no es válido.');
        }
        if ($subject === '') {
            throw new InvalidArgumentException('El asunto de correo no puede estar vacío.');
        }
        if (!function_exists('curl_init')) {
            throw new RuntimeException('La extensión cURL es necesaria para enviar por API HTTPS.');
        }

        $payload = json_encode([
            'from' => $this->fromName !== '' ? $this->fromName . ' <' . $this->from . '>' : $this->from,
            'to' => [$to],
            'subject' => $subject,
            'text' => $text,
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);

        $ch = curl_init($this->endpoint);
        if ($ch === false) {
            throw new RuntimeException('No se pudo iniciar la conexión de correo.');
        }

        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_HTTPHEADER => [
                'Authorization: Bearer ' . $this->apiKey,
                'Content-Type: application/json',
                'Accept: application/json',
            ],
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_CONNECTTIMEOUT => 8,
            CURLOPT_TIMEOUT => 20,
        ]);

        try {
            $response = curl_exec($ch);
            $httpCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $curlError = curl_error($ch);
        } catch (Throwable $e) {
            throw new RuntimeException('Falló la llamada al proveedor de correo.', 0, $e);
        } finally {
            curl_close($ch);
        }

        if ($response === false) {
            throw new RuntimeException('El proveedor de correo no respondió: ' . $curlError);
        }

        $decoded = json_decode((string) $response, true);
        if ($httpCode < 200 || $httpCode >= 300) {
            $message = is_array($decoded)
                ? (string) ($decoded['message'] ?? $decoded['name'] ?? 'Error desconocido')
                : 'Respuesta HTTP ' . $httpCode;
            throw new RuntimeException('Proveedor de correo: ' . $message);
        }

        $id = is_array($decoded) ? trim((string) ($decoded['id'] ?? '')) : '';
        if ($id === '') {
            throw new RuntimeException('El proveedor de correo no devolvió un identificador.');
        }

        return $id;
    }
}
