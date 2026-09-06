<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Upload;

final class UploadPolicy
{
    /**
     * @param array<string, string> $allowedMimeExtensions MIME => server extension.
     */
    public function __construct(
        public readonly array $allowedMimeExtensions,
        public readonly int $maxBytes,
        public readonly int $maxFiles,
        public readonly ?int $maxImageWidth = null,
        public readonly ?int $maxImageHeight = null,
        public readonly ?int $maxImagePixels = null,
        public readonly string $scannerMode = 'disabled',
    ) {
        if ($allowedMimeExtensions === []) {
            throw new \InvalidArgumentException('allowedMimeExtensions cannot be empty');
        }
        if ($maxBytes < 1 || $maxFiles < 1) {
            throw new \InvalidArgumentException('upload limits must be positive');
        }
        if (!in_array($scannerMode, ['disabled', 'best_effort', 'required'], true)) {
            throw new \InvalidArgumentException('invalid scannerMode');
        }

        $hasImage = false;
        foreach ($allowedMimeExtensions as $mime => $extension) {
            $mime = strtolower(trim((string) $mime));
            $extension = strtolower(trim((string) $extension));
            if (!preg_match('#^[a-z0-9.+-]+/[a-z0-9.+-]+$#', $mime)) {
                throw new \InvalidArgumentException('invalid MIME allowlist entry');
            }
            if (!preg_match('/^[a-z0-9]{1,10}$/', $extension)) {
                throw new \InvalidArgumentException('invalid server extension');
            }
            if (str_starts_with($mime, 'image/')) {
                $hasImage = true;
            }
        }

        if ($hasImage) {
            foreach ([$maxImageWidth, $maxImageHeight, $maxImagePixels] as $limit) {
                if (!is_int($limit) || $limit < 1) {
                    throw new \InvalidArgumentException('image uploads require positive width, height and pixel limits');
                }
            }
        }
    }

    public function extensionForMime(string $mime): ?string
    {
        $mime = strtolower(trim($mime));
        $extension = $this->allowedMimeExtensions[$mime] ?? null;
        return is_string($extension) ? strtolower($extension) : null;
    }
}
