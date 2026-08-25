<?php

declare(strict_types=1);

namespace HacheBase\Common;

use InvalidArgumentException;

final class Money
{
    /** Convert a decimal string such as 1200 or 1200.50 to integer cents. */
    public static function toCents(string $amount): int
    {
        $amount = trim($amount);
        if (!preg_match('/^\d+(?:\.\d{1,2})?$/', $amount)) {
            throw new InvalidArgumentException('Invalid monetary amount.');
        }

        [$whole, $decimal] = array_pad(explode('.', $amount, 2), 2, '');
        $decimal = str_pad($decimal, 2, '0');

        return ((int)$whole * 100) + (int)$decimal;
    }

    public static function decimal(int $cents): string
    {
        $sign = $cents < 0 ? '-' : '';
        $absolute = abs($cents);

        return $sign . intdiv($absolute, 100) . '.' . str_pad((string)($absolute % 100), 2, '0', STR_PAD_LEFT);
    }
}
