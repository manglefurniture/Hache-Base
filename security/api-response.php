<?php

declare(strict_types=1);

namespace HacheBase\Security;

final class ApiResponse
{
    public static function json(array $payload, int $status = 200): never
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');
        header('X-Content-Type-Options: nosniff');

        echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    public static function success(array $data = [], int $status = 200): never
    {
        self::json([
            'ok' => true,
            'data' => $data,
        ], $status);
    }

    public static function error(string $code, string $message, int $status = 400): never
    {
        self::json([
            'ok' => false,
            'error' => [
                'code' => $code,
                'message' => $message,
            ],
        ], $status);
    }
}
