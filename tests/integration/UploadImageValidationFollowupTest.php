<?php

declare(strict_types=1);

use HacheBase\Integrations\Upload\LocalUploadStorage;
use HacheBase\Integrations\Upload\UploadPolicy;
use HacheBase\Integrations\Upload\UploadRejected;
use HacheBase\Integrations\Upload\UploadScanner;
use HacheBase\Integrations\Upload\UploadService;

$root = dirname(__DIR__, 2);
require_once $root . '/integrations/upload/UploadRejected.php';
require_once $root . '/integrations/upload/UploadPolicy.php';
require_once $root . '/integrations/upload/UploadScanner.php';
require_once $root . '/integrations/upload/UploadStorage.php';
require_once $root . '/integrations/upload/LocalUploadStorage.php';
require_once $root . '/integrations/upload/UploadService.php';

/** @return never */
function failUploadFollowup(string $message): void
{
    fwrite(STDERR, "UPLOAD_IMAGE_FOLLOWUP_FAIL {$message}\n");
    exit(1);
}

function followupCheck(bool $condition, string $message): void
{
    if (!$condition) {
        failUploadFollowup($message);
    }
}

/** @param list<string> $reasons */
function followupExpectRejected(array $reasons, callable $callback): void
{
    try {
        $callback();
    } catch (UploadRejected $e) {
        followupCheck(in_array($e->reason, $reasons, true), 'unexpected rejection=' . $e->reason);
        return;
    }
    failUploadFollowup('expected rejection=' . implode('|', $reasons));
}

function followupPngChunk(string $type, string $data): string
{
    $crc = crc32($type . $data);
    return pack('N', strlen($data)) . $type . $data . pack('N', $crc & 0xffffffff);
}

function followupInflationPng(): string
{
    followupCheck(function_exists('gzcompress'), 'zlib unavailable');
    $compressed = gzcompress(str_repeat("\x00", 1024 * 1024), 9);
    followupCheck(is_string($compressed) && $compressed !== '', 'cannot build inflation fixture');

    return "\x89PNG\r\n\x1a\n"
        . followupPngChunk('IHDR', pack('NNCCCCC', 1, 1, 8, 6, 0, 0, 0))
        . followupPngChunk('IDAT', $compressed)
        . followupPngChunk('IEND', '');
}

function followupValidWebp(): string
{
    $bytes = base64_decode('UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==', true);
    followupCheck(is_string($bytes) && $bytes !== '', 'cannot build WebP fixture');
    return $bytes;
}

function followupHeaderOnlyWebp(): string
{
    // VP8X container that advertises a 1x1 canvas but contains no VP8/VP8L
    // image bitstream. finfo/getimagesize may identify it as WebP, but it is
    // not a decodable image.
    $vp8xPayload = "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00";
    $chunk = 'VP8X' . pack('V', strlen($vp8xPayload)) . $vp8xPayload;
    return 'RIFF' . pack('V', 4 + strlen($chunk)) . 'WEBP' . $chunk;
}

$source = file_get_contents($root . '/integrations/upload/UploadService.php');
followupCheck(is_string($source), 'cannot read UploadService source');
followupCheck(!str_contains($source, 'imagecreatefromstring'), 'generic GD decoder must not gate allowlisted formats');
followupCheck(str_contains($source, "zlib_decode(\$idat, \$expectedInflated)"), 'PNG inflation must be bounded by expected scanline bytes');
followupCheck(str_contains($source, "image_decoder_unavailable"), 'non-PNG formats must fail closed without a real decoder');

$policy = new UploadPolicy(
    allowedMimeExtensions: [
        'image/png' => 'png',
        'image/webp' => 'webp',
    ],
    maxBytes: 2 * 1024 * 1024,
    maxFiles: 2,
    maxImageWidth: 64,
    maxImageHeight: 64,
    maxImagePixels: 4096,
    scannerMode: 'disabled',
);

$tmp = sys_get_temp_dir() . '/hache-upload-followup-' . bin2hex(random_bytes(6));
$sourceDir = $tmp . '/source';
$storageDir = $tmp . '/storage';
mkdir($sourceDir, 0700, true);

try {
    $bomb = $sourceDir . '/tiny-header-large-inflate.png';
    file_put_contents($bomb, followupInflationPng());
    $bombSize = filesize($bomb);
    followupCheck(is_int($bombSize), 'inflation fixture size unavailable');
    $bombInfo = @getimagesize($bomb);
    followupCheck(is_array($bombInfo) && (int) $bombInfo[0] === 1 && (int) $bombInfo[1] === 1, 'inflation fixture must advertise 1x1 dimensions');
    followupExpectRejected(['invalid_image_content'], static function () use ($policy, $storageDir, $bomb, $bombSize): void {
        (new UploadService($policy, new LocalUploadStorage($storageDir)))->store([
            'path' => $bomb,
            'declared_size' => $bombSize,
        ]);
    });

    $fakeWebp = $sourceDir . '/header-only.webp';
    file_put_contents($fakeWebp, followupHeaderOnlyWebp());
    $fakeWebpSize = filesize($fakeWebp);
    followupCheck(is_int($fakeWebpSize), 'header-only WebP size unavailable');
    $fakeWebpInfo = @getimagesize($fakeWebp);
    followupCheck(is_array($fakeWebpInfo) && ($fakeWebpInfo['mime'] ?? null) === 'image/webp', 'header-only fixture must demonstrate WebP metadata gap');
    followupExpectRejected(['invalid_image_content', 'image_decoder_unavailable'], static function () use ($policy, $storageDir, $fakeWebp, $fakeWebpSize): void {
        (new UploadService($policy, new LocalUploadStorage($storageDir)))->store([
            'path' => $fakeWebp,
            'declared_size' => $fakeWebpSize,
        ]);
    });

    $webp = $sourceDir . '/valid.webp';
    file_put_contents($webp, followupValidWebp());
    $webpSize = filesize($webp);
    followupCheck(is_int($webpSize), 'webp fixture size unavailable');
    $webpInfo = @getimagesize($webp);
    followupCheck(is_array($webpInfo) && ($webpInfo['mime'] ?? null) === 'image/webp', 'WebP fixture not recognized');

    $service = new UploadService($policy, new LocalUploadStorage($storageDir));
    if (function_exists('imagecreatefromwebp')) {
        $receipt = $service->store(['path' => $webp, 'declared_size' => $webpSize]);
        followupCheck($receipt['mime'] === 'image/webp', 'valid allowlisted WebP rejected with codec available');
        followupCheck($receipt['extension'] === 'webp', 'WebP extension drift');
        $service->delete($receipt);
    } else {
        followupExpectRejected(['image_decoder_unavailable'], static function () use ($service, $webp, $webpSize): void {
            $service->store(['path' => $webp, 'declared_size' => $webpSize]);
        });
    }

    echo "UPLOAD_IMAGE_FOLLOWUP_OK\n";
} finally {
    if (is_dir($tmp)) {
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($tmp, FilesystemIterator::SKIP_DOTS),
            RecursiveIteratorIterator::CHILD_FIRST
        );
        foreach ($iterator as $entry) {
            if ($entry->isLink() || $entry->isFile()) {
                @unlink($entry->getPathname());
            } elseif ($entry->isDir()) {
                @rmdir($entry->getPathname());
            }
        }
        @rmdir($tmp);
    }
}
