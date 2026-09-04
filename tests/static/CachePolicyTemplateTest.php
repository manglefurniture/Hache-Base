<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$template = file_get_contents($root . '/templates/CACHE-POLICY.md');
$profile = file_get_contents($root . '/templates/PROJECT-PROFILE.md');
$templatesReadme = file_get_contents($root . '/templates/README.md');

assert(is_string($template));
assert(is_string($profile));
assert(is_string($templatesReadme));

$requireFragment = static function (string $haystack, string $fragment): void {
    assert(str_contains($haystack, $fragment), 'missing P1-06 cache policy fragment: ' . $fragment);
};

$requiredTemplateFragments = [
    'P1-06 / PERF-011',
    '## 2. Matriz obligatoria por tipo',
    'HTML público mutable',
    'Asset con hash de contenido',
    'Asset sin versionar',
    'API pública',
    'HTML/API autenticada o privada',
    '4xx',
    '5xx',
    '`Cache-Control` final esperado',
    'Validator (`ETag` / `Last-Modified`)',
    '`Vary` / cache key',
    'Invalidation / purge',
    '`no-cache` **permite almacenar pero obliga a revalidar**',
    '`immutable` solo aplica cuando el nombre/URL cambia al cambiar los bytes',
    'baseline conservador para respuestas sensibles es `Cache-Control: private, no-store, max-age=0`',
    '## 5. Prueba de invalidación',
    'Recurso mutable en el mismo URL',
    'Asset content-hashed',
    'headers reales del entorno desplegado',
    'No usar `immutable` para URLs cuyo contenido pueda cambiar.',
    'No declarar `PERF-011` aprobado sin headers reales e invalidación probada.',
];

foreach ($requiredTemplateFragments as $fragment) {
    $requireFragment($template, $fragment);
}

$requireFragment($profile, '- Política de caché completada en `CACHE-POLICY.md`: sí / no');
$requireFragment($profile, '- Owner de caché/CDN/proxy:');
$requireFragment($profile, '- Invalidation/revalidation drill de `PERF-011` completado: sí / no / no aplica');
$requireFragment($templatesReadme, '`CACHE-POLICY.md`: adopción P1-06/PERF-011');

assert(!str_contains($template, 'Authorization: Bearer '));
assert(!str_contains($template, 'Set-Cookie: session='));

print "CACHE_POLICY_TEMPLATE_OK\n";
