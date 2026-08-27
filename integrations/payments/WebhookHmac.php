<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Payments;

final class WebhookHmac
{
    /** @return array<string,string> */
    public static function parseKeyValueHeader(string $header): array
    {
        $result = [];
        foreach (explode(',', $header) as $part) {
            [$key, $value] = array_pad(explode('=', trim($part), 2), 2, '');
            $key = trim($key);
            if ($key !== '') {
                $result[$key] = trim($value);
            }
        }
        return $result;
    }

    public static function verifySha256(string $secret, string $manifest, string $providedHex): bool
    {
        $secret = trim($secret);
        $providedHex = strtolower(trim($providedHex));

        if ($secret === '' || !preg_match('/^[a-f0-9]{64}$/', $providedHex)) {
            return false;
        }

        $expected = hash_hmac('sha256', $manifest, $secret);
        return hash_equals($expected, $providedHex);
    }
}
