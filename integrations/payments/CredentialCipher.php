<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Payments;

use InvalidArgumentException;
use RuntimeException;
use Throwable;

/**
 * Cifrado reutilizable para secretos de pasarelas de pago.
 *
 * La clave maestra debe vivir fuera de la base de datos y permanecer estable
 * durante toda la vida de las versiones cifradas.
 *
 * Cada sobre queda autenticado también contra su contexto inmutable:
 * proveedor + referencia de versión + propósito del campo.
 */
final class CredentialCipher
{
    private const CIPHER = 'aes-256-gcm';
    private const GCM_TAG_LENGTH = 16;
    private const ENVELOPE_VERSION = 2;

    public function __construct(private readonly string $masterSecret)
    {
        if (trim($masterSecret) === '') {
            throw new InvalidArgumentException('La clave maestra de credenciales no puede estar vacía.');
        }
        if (!function_exists('openssl_encrypt') || !function_exists('openssl_decrypt')) {
            throw new RuntimeException('OpenSSL es obligatorio para cifrar credenciales de pago.');
        }
    }

    public function encrypt(
        string $plainText,
        string $provider,
        string $credentialRef,
        string $purpose
    ): string {
        $aad = $this->aad($provider, $credentialRef, $purpose);
        $ivLength = openssl_cipher_iv_length(self::CIPHER);
        if (!is_int($ivLength) || $ivLength <= 0) {
            throw new RuntimeException('No se pudo inicializar AES-256-GCM.');
        }

        $iv = random_bytes($ivLength);
        $tag = '';
        $cipherText = openssl_encrypt(
            $plainText,
            self::CIPHER,
            $this->key(),
            OPENSSL_RAW_DATA,
            $iv,
            $tag,
            $aad,
            self::GCM_TAG_LENGTH
        );

        if ($cipherText === false || strlen($tag) !== self::GCM_TAG_LENGTH) {
            throw new RuntimeException('No se pudo cifrar la credencial con un tag GCM completo.');
        }

        return base64_encode(json_encode([
            'v' => self::ENVELOPE_VERSION,
            'iv' => base64_encode($iv),
            'tag' => base64_encode($tag),
            'data' => base64_encode($cipherText),
        ], JSON_THROW_ON_ERROR));
    }

    public function decrypt(
        string $payload,
        string $provider,
        string $credentialRef,
        string $purpose
    ): string {
        $aad = $this->aad($provider, $credentialRef, $purpose);

        try {
            if (trim($payload) === '') {
                throw new RuntimeException('Sobre cifrado vacío.');
            }

            $json = base64_decode($payload, true);
            if ($json === false) {
                throw new RuntimeException('Sobre cifrado inválido.');
            }

            $decoded = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
            if (!is_array($decoded) || (int) ($decoded['v'] ?? 0) !== self::ENVELOPE_VERSION) {
                throw new RuntimeException('Versión de sobre cifrado no soportada.');
            }

            $iv = base64_decode((string) ($decoded['iv'] ?? ''), true);
            $tag = base64_decode((string) ($decoded['tag'] ?? ''), true);
            $data = base64_decode((string) ($decoded['data'] ?? ''), true);
            if ($iv === false || $tag === false || $data === false) {
                throw new RuntimeException('Credencial cifrada dañada.');
            }
            if (strlen($tag) !== self::GCM_TAG_LENGTH) {
                throw new RuntimeException('El tag de autenticación GCM debe tener exactamente 16 bytes.');
            }

            $plainText = openssl_decrypt(
                $data,
                self::CIPHER,
                $this->key(),
                OPENSSL_RAW_DATA,
                $iv,
                $tag,
                $aad
            );

            if ($plainText === false) {
                throw new RuntimeException('No se pudo autenticar o descifrar la credencial.');
            }

            return $plainText;
        } catch (Throwable $e) {
            throw new RuntimeException('No se pudo leer la credencial cifrada.', 0, $e);
        }
    }

    private function aad(string $provider, string $credentialRef, string $purpose): string
    {
        $provider = trim($provider);
        $credentialRef = trim($credentialRef);
        $purpose = trim($purpose);

        if ($provider === '' || $credentialRef === '' || $purpose === '') {
            throw new InvalidArgumentException(
                'Proveedor, referencia inmutable y propósito son obligatorios para autenticar la credencial.'
            );
        }

        return json_encode([
            'schema' => 'hache-payment-credential-aad-v1',
            'provider' => $provider,
            'credential_ref' => $credentialRef,
            'purpose' => $purpose,
        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
    }

    private function key(): string
    {
        return hash('sha256', $this->masterSecret, true);
    }
}
