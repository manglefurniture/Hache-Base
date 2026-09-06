<?php

declare(strict_types=1);

use HacheBase\Integrations\Upload\LocalUploadStorage;
use HacheBase\Integrations\Upload\PhpUploadAdapter;
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
require_once $root . '/integrations/upload/PhpUploadAdapter.php';
require_once $root . '/integrations/upload/UploadService.php';

final class FixtureScanner implements UploadScanner
{
    public int $calls = 0;

    public function __construct(private readonly string $status)
    {
    }

    public function scan(string $path, string $mime): string
    {
        $this->calls++;
        return $this->status;
    }
}

/** @return never */
function failUploadTest(string $message): void
{
    fwrite(STDERR, "UPLOAD_EXTENSION_TEST_FAIL {$message}\n");
    exit(1);
}

function expectRejected(string $reason, callable $callback): void
{
    try {
        $callback();
    } catch (UploadRejected $e) {
        if ($e->reason !== $reason) {
            failUploadTest("expected={$reason} actual={$e->reason}");
        }
        return;
    }
    failUploadTest("expected rejection={$reason}");
}

function pngChunk(string $type, string $data): string
{
    $crc = crc32($type . $data);
    return pack('N', strlen($data)) . $type . $data . pack('N', $crc & 0xffffffff);
}

function pngFixture(int $width, int $height): string
{
    if (!function_exists('gzcompress')) {
        failUploadTest('zlib is required for PNG fixtures');
    }

    $scanline = "\x00" . str_repeat("\x00", $width * 4);
    $raw = str_repeat($scanline, $height);
    $compressed = gzcompress($raw, 9);
    if (!is_string($compressed) || $compressed === '') {
        failUploadTest('could not create PNG fixture payload');
    }

    return "\x89PNG\r\n\x1a\n"
        . pngChunk('IHDR', pack('NNCCCCC', $width, $height, 8, 6, 0, 0, 0))
        . pngChunk('IDAT', $compressed)
        . pngChunk('IEND', '');
}

function pngHeaderOnlyFixture(int $width, int $height): string
{
    return "\x89PNG\r\n\x1a\n"
        . pngChunk('IHDR', pack('NNCCCCC', $width, $height, 8, 6, 0, 0, 0))
        . pngChunk('IEND', '');
}

function policy(
    int $maxBytes = 1048576,
    int $maxFiles = 2,
    int $maxWidth = 2000,
    int $maxHeight = 2000,
    int $maxPixels = 2000000,
    string $scannerMode = 'disabled',
): UploadPolicy {
    return new UploadPolicy(
        allowedMimeExtensions: ['image/png' => 'png'],
        maxBytes: $maxBytes,
        maxFiles: $maxFiles,
        maxImageWidth: $maxWidth,
        maxImageHeight: $maxHeight,
        maxImagePixels: $maxPixels,
        scannerMode: $scannerMode,
    );
}

$tmp = sys_get_temp_dir() . '/hache-upload-extension-' . bin2hex(random_bytes(6));
$sourceDir = $tmp . '/source';
$storageDir = $tmp . '/storage';
mkdir($sourceDir, 0700, true);

try {
    $valid = $sourceDir . '/client-controlled-name.php.png';
    file_put_contents($valid, pngFixture(32, 24));
    $size = filesize($valid);
    assert(is_int($size));

    $uploadField = [
        'name' => ['../../evil.php'],
        'type' => ['application/x-php'],
        'tmp_name' => [$valid],
        'error' => [UPLOAD_ERR_OK],
        'size' => [$size],
    ];
    $candidates = PhpUploadAdapter::candidates($uploadField, policy(), static fn (string $path): bool => $path === $valid);
    assert(count($candidates) === 1);
    assert(array_keys($candidates[0]) === ['path', 'declared_size']);

    $disabledScanner = new FixtureScanner(UploadScanner::INFECTED);
    $storage = new LocalUploadStorage($storageDir);
    $service = new UploadService(policy(scannerMode: 'disabled'), $storage, $disabledScanner);
    $receipt = $service->store($candidates[0]);
    assert($disabledScanner->calls === 0);
    assert($receipt['mime'] === 'image/png');
    assert($receipt['extension'] === 'png');
    assert($receipt['width'] === 32 && $receipt['height'] === 24);
    assert($receipt['scanner_status'] === 'disabled');
    assert(is_file($receipt['stored']['path']));
    assert(dirname($receipt['stored']['path']) === realpath($storageDir));
    assert(!str_contains(basename($receipt['stored']['path']), 'evil'));
    assert(!str_contains(basename($receipt['stored']['path']), 'client-controlled'));
    assert(preg_match('/^[0-9a-f]{32}\.png$/', basename($receipt['stored']['path'])) === 1);
    assert(hash_file('sha256', $receipt['stored']['path']) === $receipt['stored']['sha256']);

    $second = $service->store($candidates[0]);
    assert($second['stored']['id'] !== $receipt['stored']['id']);
    assert($second['stored']['path'] !== $receipt['stored']['path']);

    $service->delete($receipt);
    assert(!file_exists($receipt['stored']['path']));
    $service->delete($second);
    assert(!file_exists($second['stored']['path']));

    $truncated = $sourceDir . '/header-only.png';
    file_put_contents($truncated, pngHeaderOnlyFixture(32, 24));
    $truncatedSize = filesize($truncated);
    assert(is_int($truncatedSize));
    assert(is_array(@getimagesize($truncated)));
    expectRejected('invalid_image_content', static function () use ($truncated, $truncatedSize, $storageDir): void {
        (new UploadService(policy(), new LocalUploadStorage($storageDir)))->store([
            'path' => $truncated,
            'declared_size' => $truncatedSize,
        ]);
    });

    $text = $sourceDir . '/fake.png';
    file_put_contents($text, "<?php echo 'not an image';\n");
    $textSize = filesize($text);
    assert(is_int($textSize));
    expectRejected('mime_not_allowed', static function () use ($text, $textSize, $storageDir): void {
        (new UploadService(policy(), new LocalUploadStorage($storageDir)))->store([
            'path' => $text,
            'declared_size' => $textSize,
        ]);
    });

    expectRejected('size_mismatch', static function () use ($valid, $size, $storageDir): void {
        (new UploadService(policy(), new LocalUploadStorage($storageDir)))->store([
            'path' => $valid,
            'declared_size' => $size + 1,
        ]);
    });

    expectRejected('too_large', static function () use ($valid, $size, $storageDir): void {
        (new UploadService(policy(maxBytes: 10), new LocalUploadStorage($storageDir)))->store([
            'path' => $valid,
            'declared_size' => $size,
        ]);
    });

    $wide = $sourceDir . '/wide.png';
    file_put_contents($wide, pngFixture(5000, 1));
    $wideSize = filesize($wide);
    assert(is_int($wideSize));
    expectRejected('image_dimensions_exceeded', static function () use ($wide, $wideSize, $storageDir): void {
        (new UploadService(policy(maxWidth: 2000, maxHeight: 2000, maxPixels: 10000000), new LocalUploadStorage($storageDir)))->store([
            'path' => $wide,
            'declared_size' => $wideSize,
        ]);
    });

    $pixelBomb = $sourceDir . '/pixels.png';
    file_put_contents($pixelBomb, pngFixture(1800, 1800));
    $pixelSize = filesize($pixelBomb);
    assert(is_int($pixelSize));
    expectRejected('image_pixels_exceeded', static function () use ($pixelBomb, $pixelSize, $storageDir): void {
        (new UploadService(policy(maxWidth: 2000, maxHeight: 2000, maxPixels: 1000000), new LocalUploadStorage($storageDir)))->store([
            'path' => $pixelBomb,
            'declared_size' => $pixelSize,
        ]);
    });

    $infected = new FixtureScanner(UploadScanner::INFECTED);
    expectRejected('scanner_rejected', static function () use ($valid, $size, $storageDir, $infected): void {
        (new UploadService(policy(scannerMode: 'required'), new LocalUploadStorage($storageDir), $infected))->store([
            'path' => $valid,
            'declared_size' => $size,
        ]);
    });
    assert($infected->calls === 1);

    $unavailable = new FixtureScanner(UploadScanner::UNAVAILABLE);
    expectRejected('scanner_unavailable', static function () use ($valid, $size, $storageDir, $unavailable): void {
        (new UploadService(policy(scannerMode: 'required'), new LocalUploadStorage($storageDir), $unavailable))->store([
            'path' => $valid,
            'declared_size' => $size,
        ]);
    });

    expectRejected('scanner_required', static function () use ($valid, $size, $storageDir): void {
        (new UploadService(policy(scannerMode: 'required'), new LocalUploadStorage($storageDir)))->store([
            'path' => $valid,
            'declared_size' => $size,
        ]);
    });

    $bestEffortScanner = new FixtureScanner(UploadScanner::UNAVAILABLE);
    $bestEffortService = new UploadService(policy(scannerMode: 'best_effort'), new LocalUploadStorage($storageDir), $bestEffortScanner);
    $bestEffort = $bestEffortService->store(['path' => $valid, 'declared_size' => $size]);
    assert($bestEffort['scanner_status'] === UploadScanner::UNAVAILABLE);
    $bestEffortService->delete($bestEffort);

    $bestEffortNoScanner = new UploadService(policy(scannerMode: 'best_effort'), new LocalUploadStorage($storageDir));
    $notConfigured = $bestEffortNoScanner->store(['path' => $valid, 'declared_size' => $size]);
    assert($notConfigured['scanner_status'] === 'not_configured');
    $bestEffortNoScanner->delete($notConfigured);

    expectRejected('too_many_files', static function () use ($valid, $size): void {
        PhpUploadAdapter::candidates([
            'tmp_name' => [$valid, $valid, $valid],
            'error' => [UPLOAD_ERR_OK, UPLOAD_ERR_OK, UPLOAD_ERR_OK],
            'size' => [$size, $size, $size],
        ], policy(maxFiles: 2), static fn (): bool => true);
    });

    expectRejected('invalid_transport_origin', static function () use ($valid, $size): void {
        PhpUploadAdapter::candidates([
            'tmp_name' => [$valid],
            'error' => [UPLOAD_ERR_OK],
            'size' => [$size],
        ], policy(), static fn (): bool => false);
    });

    try {
        new UploadPolicy(
            allowedMimeExtensions: ['image/png' => 'png'],
            maxBytes: 1024,
            maxFiles: 1,
        );
        failUploadTest('image policy accepted without dimension/pixel limits');
    } catch (InvalidArgumentException) {
    }

    $symlinkRoot = $tmp . '/storage-link';
    if (function_exists('symlink') && @symlink($storageDir, $symlinkRoot)) {
        try {
            new LocalUploadStorage($symlinkRoot);
            failUploadTest('symlink storage root accepted');
        } catch (InvalidArgumentException) {
        }
    }

    echo "UPLOAD_EXTENSION_OK\n";
} finally {
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
