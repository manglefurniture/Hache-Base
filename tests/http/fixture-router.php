<?php

declare(strict_types=1);

use HacheBase\Security\Headers;
use HacheBase\Security\SessionSecurity;

require_once dirname(__DIR__, 2) . '/security/headers.php';
require_once dirname(__DIR__, 2) . '/security/session-security.php';

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if (!is_string($path)) {
    $path = '/';
}

$plain = static function (string $body, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: text/plain; charset=utf-8');
    echo $body;
};

$json = static function (array $payload, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n";
};

switch ($path) {
    case '/health':
        header('Cache-Control: no-store');
        $plain("ok\n");
        return true;

    case '/headers':
        Headers::apply([
            'csp' => [
                'mode' => 'report-only',
                'directives' => [
                    'default-src' => ["'self'"],
                    'object-src' => ["'none'"],
                    'base-uri' => ["'self'"],
                ],
            ],
        ], $_SERVER);
        header('Cache-Control: no-store');
        $plain("headers fixture\n");
        return true;

    case '/cookie':
        $cookie = SessionSecurity::buildCookieParams([], $_SERVER);
        setcookie('HB_HTTP_FIXTURE', '1', [
            'expires' => 0,
            'path' => $cookie['path'],
            'domain' => $cookie['domain'],
            'secure' => $cookie['secure'],
            'httponly' => $cookie['httponly'],
            'samesite' => $cookie['samesite'],
        ]);
        header('Cache-Control: no-store');
        $plain("cookie fixture\n");
        return true;

    case '/cache/public':
        header('Cache-Control: public, max-age=60');
        $plain("public cache fixture\n");
        return true;

    case '/cache/private':
        header('Cache-Control: private, no-store, max-age=0');
        header('Pragma: no-cache');
        $plain("private cache fixture\n");
        return true;

    case '/cache/html':
        $version = 'v1';
        $versionFile = getenv('HB_CACHE_VERSION_FILE');
        if (is_string($versionFile) && $versionFile !== '') {
            $rawVersion = @file_get_contents($versionFile);
            if (!is_string($rawVersion)) {
                header('Cache-Control: no-store');
                $plain("Internal Server Error\n", 500);
                return true;
            }
            $candidate = trim($rawVersion);
            if (preg_match('/^[A-Za-z0-9._-]{1,32}$/', $candidate) !== 1) {
                header('Cache-Control: no-store');
                $plain("Internal Server Error\n", 500);
                return true;
            }
            $version = $candidate;
        }

        $etag = '"hb-' . $version . '"';
        header('Content-Type: text/html; charset=utf-8');
        header('Cache-Control: no-cache');
        header('ETag: ' . $etag);
        $ifNoneMatch = $_SERVER['HTTP_IF_NONE_MATCH'] ?? '';
        if (is_string($ifNoneMatch) && trim($ifNoneMatch) === $etag) {
            http_response_code(304);
            return true;
        }
        echo "<!doctype html><html lang=\"en\"><body>html cache fixture {$version}</body></html>\n";
        return true;

    case '/assets/app.abc123.js':
        header('Content-Type: application/javascript; charset=utf-8');
        header('Cache-Control: public, max-age=31536000, immutable');
        echo "console.log('hashed-cache-fixture');\n";
        return true;

    case '/assets/app.js':
        header('Content-Type: application/javascript; charset=utf-8');
        header('Cache-Control: no-cache');
        echo "console.log('mutable-cache-fixture');\n";
        return true;

    case '/api/public':
        header('Cache-Control: public, max-age=60');
        $json(['scope' => 'public', 'value' => 'cacheable']);
        return true;

    case '/api/private':
        header('Cache-Control: private, no-store, max-age=0');
        header('Pragma: no-cache');
        $json(['scope' => 'private', 'value' => 'sensitive-fixture']);
        return true;

    case '/account':
        header('Content-Type: text/html; charset=utf-8');
        header('Cache-Control: private, no-store, max-age=0');
        header('Pragma: no-cache');
        echo "<!doctype html><html lang=\"en\"><body>private html fixture</body></html>\n";
        return true;

    case '/compressed':
        $body = "compressed fixture\n";
        header('Content-Type: text/plain; charset=utf-8');
        header('Vary: Accept-Encoding');
        $acceptEncoding = $_SERVER['HTTP_ACCEPT_ENCODING'] ?? '';
        if (is_string($acceptEncoding) && preg_match('/(?:^|,)\s*gzip(?:\s*;[^,]*)?(?:,|$)/i', $acceptEncoding) === 1) {
            $encoded = gzencode($body, 6);
            if (!is_string($encoded)) {
                http_response_code(500);
                header('Cache-Control: no-store');
                echo "Internal Server Error\n";
                return true;
            }
            header('Content-Encoding: gzip');
            header('Content-Length: ' . strlen($encoded));
            echo $encoded;
            return true;
        }
        echo $body;
        return true;

    case '/redirect':
        header('Cache-Control: no-store');
        header('Location: /target', true, 302);
        return true;

    case '/target':
        $plain("redirect target\n");
        return true;

    case '/status/204':
        http_response_code(204);
        header('Cache-Control: no-store');
        return true;

    case '/error':
        header('Cache-Control: no-store');
        $plain("Internal Server Error\n", 500);
        return true;

    default:
        header('Cache-Control: no-store');
        $plain("Not Found\n", 404);
        return true;
}
