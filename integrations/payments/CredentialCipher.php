<?php
declare(strict_types=1);

/**
 * Cifrado reutilizable para secretos de pasarelas de pago.
 *
 * La clave maestra debe vivir fuera de la base de datos y permanecer estable
 * durante toda la vida de las versiones cifradas.
 */
final class CredentialCipher
{
    private const CIPHER = 'aes-256-gcm';

    public function __construct(private readonly string $masterSecret)
    {
        if (trim($masterSecret) === '') {
            throw new InvalidArgumentException('La clave maestra de credenciales no puede estar vacía.');
        }
        if (!function_exists('openssl_encrypt') || !function_exists('openssl_decrypt')) {
            throw new RuntimeException('OpenSSL es obligatorio para cifrar credenciales de pago.');
        }
    }

    public function encrypt(string $plainText): string
    {
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
            $tag
        );

        if ($cipherText === false) {
            throw new RuntimeException('No se pudo cifrar la credencial.');
        }

        return base64_encode(json_encode([
            'v' => 1,
            'iv' => base64_encode($iv),
            'tag' => base64_encode($tag),
            'data' => base64_encode($cipherText),
        ], JSON_THROW_ON_ERROR));
    }

    public function decrypt(string $payload): string
    {
        if (trim($payload) === '') {
            return '';
        }

        try {
            $json = base64_decode($payload, true);
            if ($json === false) {
                throw new RuntimeException('Sobre cifrado inválido.');
            }

            $decoded = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
            if (!is_array($decoded) || (int) ($decoded['v'] ?? 0) !== 1) {
                throw new RuntimeException('Versión de sobre cifrado no soportada.');
            }

            $iv = base64_decode((string) ($decoded['iv'] ?? ''), true);
            $tag = base64_decode((string) ($decoded['tag'] ?? ''), true);
            $data = base64_decode((string) ($decoded['data'] ?? ''), true);
            if ($iv === false || $tag === false || $data === false) {
                throw new RuntimeException('Credencial cifrada dañada.');
            }

            $plainText = openssl_decrypt(
                $data,
                self::CIPHER,
                $this->key(),
                OPENSSL_RAW_DATA,
                $iv,
                $tag
            );

            if ($plainText === false) {
                throw new RuntimeException('No se pudo autenticar o descifrar la credencial.');
            }

            return $plainText;
        } catch (Throwable $e) {
            throw new RuntimeException('No se pudo leer la credencial cifrada.', 0, $e);
        }
    }

    private function key(): string
    {
        return hash('sha256', $this->masterSecret, true);
    }
}
