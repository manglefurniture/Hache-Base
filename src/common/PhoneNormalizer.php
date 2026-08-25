<?php

declare(strict_types=1);

namespace HacheBase\Common;

use InvalidArgumentException;

final class PhoneNormalizer
{
    /**
     * Normalize a phone number to E.164 digits with a leading +.
     * The project must provide/confirm the country calling code when the
     * incoming number is local. Mexico (+52) also accepts historical +521.
     */
    public static function toE164(string $raw, string $defaultCountryCode = '52'): string
    {
        $raw = trim($raw);
        if ($raw === '') {
            throw new InvalidArgumentException('Phone number is required.');
        }

        $digits = preg_replace('/\D+/', '', $raw) ?? '';
        if (str_starts_with($digits, '00')) {
            $digits = substr($digits, 2);
        }

        $country = preg_replace('/\D+/', '', $defaultCountryCode) ?? '';
        if ($country === '') {
            throw new InvalidArgumentException('Default country code is required.');
        }

        // Historical Mexican WhatsApp/mobile format: +521 + 10 digits.
        if (str_starts_with($digits, '521') && strlen($digits) === 13) {
            $digits = '52' . substr($digits, 3);
        }

        $explicitInternational = str_starts_with($raw, '+') || str_starts_with($raw, '00');
        if (!$explicitInternational && !str_starts_with($digits, $country)) {
            $digits = $country . $digits;
        }

        if (strlen($digits) < 8 || strlen($digits) > 15) {
            throw new InvalidArgumentException('Phone number is not valid for E.164.');
        }

        return '+' . $digits;
    }

    public static function digits(string $raw, string $defaultCountryCode = '52'): string
    {
        return ltrim(self::toE164($raw, $defaultCountryCode), '+');
    }
}
