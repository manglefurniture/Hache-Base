<?php

declare(strict_types=1);

namespace HacheBase\Security;

use HacheBase\Common\RequestContext;
use InvalidArgumentException;

require_once __DIR__ . '/../src/common/RequestContext.php';

final class ApiResponse
{
    public const ERROR_BAD_REQUEST = 'BAD_REQUEST';
    public const ERROR_UNAUTHORIZED = 'UNAUTHORIZED';
    public const ERROR_FORBIDDEN = 'FORBIDDEN';
    public const ERROR_NOT_FOUND = 'NOT_FOUND';
    public const ERROR_CONFLICT = 'CONFLICT';
    public const ERROR_VALIDATION_FAILED = 'VALIDATION_FAILED';
    public const ERROR_RATE_LIMITED = 'RATE_LIMITED';
    public const ERROR_INTERNAL = 'INTERNAL_ERROR';
    public const ERROR_SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE';

    /** @var array<int, array{code: string, message: string}> */
    private const HTTP_ERRORS = [
        400 => ['code' => self::ERROR_BAD_REQUEST, 'message' => 'Bad request.'],
        401 => ['code' => self::ERROR_UNAUTHORIZED, 'message' => 'Authentication required.'],
        403 => ['code' => self::ERROR_FORBIDDEN, 'message' => 'Access denied.'],
        404 => ['code' => self::ERROR_NOT_FOUND, 'message' => 'Resource not found.'],
        409 => ['code' => self::ERROR_CONFLICT, 'message' => 'Resource state conflict.'],
        422 => ['code' => self::ERROR_VALIDATION_FAILED, 'message' => 'Validation failed.'],
        429 => ['code' => self::ERROR_RATE_LIMITED, 'message' => 'Too many requests.'],
        500 => ['code' => self::ERROR_INTERNAL, 'message' => 'Internal server error.'],
        503 => ['code' => self::ERROR_SERVICE_UNAVAILABLE, 'message' => 'Service temporarily unavailable.'],
    ];

    public static function json(array $payload, int $status = 200, ?RequestContext $context = null): never
    {
        $context ??= RequestContext::fromServer();
        $payload['request_id'] ??= $context->requestId();

        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');
        header('X-Content-Type-Options: nosniff');
        header('X-Request-Id: ' . $context->requestId());
        header('X-Correlation-Id: ' . $context->correlationId());

        echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    public static function success(array $data = [], int $status = 200, ?RequestContext $context = null): never
    {
        $context ??= RequestContext::fromServer();
        self::json(self::successPayload($data, $context), $status, $context);
    }

    /**
     * Backward-compatible custom/domain error entry point.
     * Projects should keep custom codes stable once exposed to clients.
     */
    public static function error(
        string $code,
        string $message,
        int $status = 400,
        ?RequestContext $context = null,
    ): never {
        $context ??= RequestContext::fromServer();
        self::json(self::errorPayload($code, $message, $context), $status, $context);
    }

    /**
     * Canonical HTTP error contract for common platform errors.
     */
    public static function errorForStatus(
        int $status,
        ?string $message = null,
        ?RequestContext $context = null,
    ): never {
        $definition = self::errorDefinition($status);
        $context ??= RequestContext::fromServer();

        self::json(
            self::errorPayload($definition['code'], $message ?? $definition['message'], $context),
            $status,
            $context,
        );
    }

    /** @return array{ok: true, data: array, request_id: string} */
    public static function successPayload(array $data, RequestContext $context): array
    {
        return [
            'ok' => true,
            'data' => $data,
            'request_id' => $context->requestId(),
        ];
    }

    /** @return array{ok: false, error: array{code: string, message: string}, request_id: string} */
    public static function errorPayload(string $code, string $message, RequestContext $context): array
    {
        return [
            'ok' => false,
            'error' => [
                'code' => $code,
                'message' => $message,
            ],
            'request_id' => $context->requestId(),
        ];
    }

    /** @return array{code: string, message: string} */
    public static function errorDefinition(int $status): array
    {
        if (!isset(self::HTTP_ERRORS[$status])) {
            throw new InvalidArgumentException('Unsupported canonical HTTP error status.');
        }

        return self::HTTP_ERRORS[$status];
    }
}
