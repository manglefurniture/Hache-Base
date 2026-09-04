<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$templatePath = $root . '/templates/THIRD-PARTY-INVENTORY.md';
$profilePath = $root . '/templates/PROJECT-PROFILE.md';
$templatesReadmePath = $root . '/templates/README.md';

$template = file_get_contents($templatePath);
$profile = file_get_contents($profilePath);
$templatesReadme = file_get_contents($templatesReadmePath);

assert(is_string($template));
assert(is_string($profile));
assert(is_string($templatesReadme));

function requireFragment(string $haystack, string $fragment): void
{
    assert(str_contains($haystack, $fragment), 'missing P1-05 contract fragment: ' . $fragment);
}

$requiredTemplateFragments = [
    'P1-05 / PERF-010',
    '## 3. Estado cero — no hay terceros',
    'NO_THIRD_PARTIES',
    'Alcance revisado:',
    'Evidencia de revisión',
    'Persona revisora:',
    'Fecha (`YYYY-MM-DD`):',
    '#### Identidad y ownership',
    'Owner técnico/negocio:',
    'Propósito concreto:',
    'CUF/plantillas afectados:',
    '#### Datos compartidos',
    'Dirección: proyecto→tercero / tercero→proyecto / bidireccional',
    'Categorías de datos enviados:',
    'Categorías de datos recibidos:',
    '#### Timeout, retry y fallback',
    'Timeout de conexión, si aplica:',
    'Timeout total/read, si aplica:',
    'Fallback/degradación cuando falla o excede timeout:',
    '#### Coste de performance medido',
    'Comparación **con tercero**:',
    'Comparación **sin tercero** o baseline equivalente:',
    'Delta LCP / INP / CLS / TBT, si aplica:',
    'Latencia backend p50/p95 o tiempo añadido al CUF, si aplica:',
    '#### Retiro y revisión',
    'Criterio de retiro/reemplazo:',
    'sin copiar valores secretos',
    'no debe presentarse como evidencia completa de `PERF-010`',
    'No convertir automáticamente el inventario en `PASS`',
    'Si P1-04 RUM usa un collector/SDK externo, registrarlo aquí como cualquier otro tercero.',
];

foreach ($requiredTemplateFragments as $fragment) {
    requireFragment($template, $fragment);
}

requireFragment(
    $profile,
    '- Inventario de terceros completado en `THIRD-PARTY-INVENTORY.md`: sí / no / no aplica'
);
requireFragment($profile, '- Terceros críticos previstos:');
requireFragment($profile, '- ¿Algún tercero participa en camino crítico de un CUF?: sí / no / por revisar');
requireFragment($templatesReadme, '`THIRD-PARTY-INVENTORY.md`: adopción P1-05/PERF-010');

assert(!str_contains($template, 'api_key='));
assert(!str_contains($template, 'password='));
assert(!str_contains($template, 'token='));

print "THIRD_PARTY_INVENTORY_TEMPLATE_OK\n";
