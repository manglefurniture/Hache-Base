<?php

declare(strict_types=1);

namespace HacheBase\Common;

final class Input
{
    public static function email(mixed $value): ?string
    {
        if (!is_string($value)) {
            return null;
        }

        $value = trim($value);
        return filter_var($value, FILTER_VALIDATE_EMAIL) !== false ? $value : null;
    }

    public static function positiveId(mixed $value): ?int
    {
        if (is_int($value)) {
            return $value > 0 ? $value : null;
        }

        if (!is_string($value) || !preg_match('/^[1-9]\d*$/', $value)) {
            return null;
        }

        $id = filter_var($value, FILTER_VALIDATE_INT);
        return is_int($id) && $id > 0 ? $id : null;
    }

    public static function text(mixed $value, int $maxLength = 255): ?string
    {
        if (!is_string($value) || $maxLength < 1) {
            return null;
        }

        $value = trim($value);
        if ($value === '' || mb_strlen($value) > $maxLength) {
            return null;
        }

        return $value;
    }
}
