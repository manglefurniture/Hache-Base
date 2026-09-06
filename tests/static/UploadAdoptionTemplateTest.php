<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$template = file_get_contents($root . '/templates/UPLOAD-ADOPTION.md');
$readme = file_get_contents($root . '/integrations/upload/README.md');

assert(is_string($template));
assert(is_string($readme));

foreach ([
    'Upload Adoption — P2-04',
    'Caso real y CUF',
    'MIME spoofing',
    'decompression/resource bomb',
    'scanner unavailable',
    'fallo parcial storage↔DB',
    'ruta pública no ejecuta scripts',
    'una revisión humana valida el flujo real',
    'no declara P2-04 PASS',
] as $fragment) {
    assert(str_contains($template, $fragment), 'missing P2-04 adoption fragment: ' . $fragment);
}

foreach ([
    'PhpUploadAdapter',
    'UploadPolicy',
    'UploadService',
    'UploadStorage',
    'LocalUploadStorage',
    'disabled|best_effort|required',
    'La existencia de esta extensión en Hache Base **no** convierte P2-04',
] as $fragment) {
    assert(str_contains($readme, $fragment), 'missing upload extension contract: ' . $fragment);
}

// Business-specific limits belong to the pilot, not to the reusable template.
assert(!str_contains($template, '8 MB'));
assert(!str_contains($template, '6 fotos'));
assert(!str_contains($template, 'Tienda Natación'));
assert(!str_contains($template, 'producto-'));

print "UPLOAD_ADOPTION_TEMPLATE_OK\n";
