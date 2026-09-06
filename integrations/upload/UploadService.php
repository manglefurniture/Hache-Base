<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Upload;

final class UploadService
{
    public function __construct(
        private readonly UploadPolicy $policy,
        private readonly UploadStorage $storage,
        private readonly ?UploadScanner $scanner = null,
    ) {
    }

    /**
     * @param array{path:string,declared_size:int} $candidate
     * @return array{
     *   mime:string,extension:string,size:int,width:?int,height:?int,
     *   scanner_status:string,stored:array{id:string,path:string,size:int,sha256:string}
     * }
     */
    public function store(array $candidate): array
    {
        $path = $candidate['path'] ?? null;
        $declaredSize = $candidate['declared_size'] ?? null;
        if (!is_string($path) || $path === '' || !is_int($declaredSize) || $declaredSize < 0) {
            throw new UploadRejected('malformed_candidate');
        }
        if (!is_file($path) || is_link($path) || !is_readable($path)) {
            throw new UploadRejected('invalid_source');
        }

        $actualSize = filesize($path);
        if ($actualSize === false) {
            throw new UploadRejected('size_unavailable');
        }
        if ($actualSize !== $declaredSize) {
            throw new UploadRejected('size_mismatch');
        }
        if ($actualSize < 1) {
            throw new UploadRejected('empty_file');
        }
        if ($actualSize > $this->policy->maxBytes) {
            throw new UploadRejected('too_large');
        }

        $finfo = new \finfo(FILEINFO_MIME_TYPE);
        $mime = strtolower(trim((string) $finfo->file($path)));
        $extension = $this->policy->extensionForMime($mime);
        if ($extension === null) {
            throw new UploadRejected('mime_not_allowed');
        }

        $width = null;
        $height = null;
        if (str_starts_with($mime, 'image/')) {
            $image = @getimagesize($path);
            if (!is_array($image) || !isset($image[0], $image[1]) || (int) $image[0] < 1 || (int) $image[1] < 1) {
                throw new UploadRejected('invalid_image_content');
            }
            $imageMime = strtolower(trim((string) ($image['mime'] ?? '')));
            if ($imageMime !== $mime) {
                throw new UploadRejected('image_mime_mismatch');
            }
            $width = (int) $image[0];
            $height = (int) $image[1];

            if ($width > (int) $this->policy->maxImageWidth || $height > (int) $this->policy->maxImageHeight) {
                throw new UploadRejected('image_dimensions_exceeded');
            }
            $pixelLimit = (int) $this->policy->maxImagePixels;
            if ($height > 0 && $width > intdiv($pixelLimit, $height)) {
                throw new UploadRejected('image_pixels_exceeded');
            }
        }

        $scannerStatus = $this->scan($path, $mime);
        $stored = $this->storage->store($path, $extension);
        if (($stored['size'] ?? null) !== $actualSize) {
            try {
                $this->storage->delete($stored);
            } catch (\Throwable) {
            }
            throw new \RuntimeException('stored upload size drift');
        }

        return [
            'mime' => $mime,
            'extension' => $extension,
            'size' => $actualSize,
            'width' => $width,
            'height' => $height,
            'scanner_status' => $scannerStatus,
            'stored' => $stored,
        ];
    }

    /** @param array{stored:array{id:string,path:string,size:int,sha256:string}} $receipt */
    public function delete(array $receipt): void
    {
        if (!isset($receipt['stored']) || !is_array($receipt['stored'])) {
            throw new \InvalidArgumentException('upload receipt missing stored record');
        }
        $this->storage->delete($receipt['stored']);
    }

    private function scan(string $path, string $mime): string
    {
        if ($this->policy->scannerMode === 'disabled') {
            return 'disabled';
        }
        if ($this->scanner === null) {
            if ($this->policy->scannerMode === 'required') {
                throw new UploadRejected('scanner_required');
            }
            return 'not_configured';
        }

        try {
            $status = $this->scanner->scan($path, $mime);
        } catch (\Throwable) {
            $status = UploadScanner::UNAVAILABLE;
        }

        if ($status === UploadScanner::INFECTED) {
            throw new UploadRejected('scanner_rejected');
        }
        if ($status === UploadScanner::UNAVAILABLE) {
            if ($this->policy->scannerMode === 'required') {
                throw new UploadRejected('scanner_unavailable');
            }
            return UploadScanner::UNAVAILABLE;
        }
        if ($status !== UploadScanner::CLEAN) {
            throw new UploadRejected('scanner_invalid_result');
        }

        return UploadScanner::CLEAN;
    }
}
