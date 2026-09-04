<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$templatePath = $root . '/templates/DATA-PRIVACY-INVENTORY.md';
$profilePath = $root . '/templates/PROJECT-PROFILE.md';
$templatesReadmePath = $root . '/templates/README.md';

$template = file_get_contents($templatePath);
$profile = file_get_contents($profilePath);
$templatesReadme = file_get_contents($templatesReadmePath);

assert(is_string($template));
assert(is_string($profile));
assert(is_string($templatesReadme));

function requirePrivacyFragment(string $haystack, string $fragment): void
{
    assert(str_contains($haystack, $fragment), 'missing P1-09 privacy contract fragment: ' . $fragment);
}

$requiredTemplateFragments = [
    'P1-09 / PRIV-001…PRIV-003',
    'no** determina por sí sola una base legal',
    'Jurisdicción(es) y mercados evaluados:',
    'NO_PERSONAL_DATA',
    '`NO_PERSONAL_DATA` no vuelve automáticamente N/A a `PRIV-003`',
    '## 2. Inventario de datos — PRIV-001',
    'Decisión/base/justificación por jurisdicción',
    'Tercero(s) receptores por ID de `THIRD-PARTY-INVENTORY.md`',
    'Roles/personas/sistemas con acceso:',
    'Regla de retención (duración **y evento de inicio**):',
    'Mecanismo de eliminación/anonimización:',
    'Tratamiento en backups/snapshots:',
    '## 3. Minimización y acceso — PRIV-002',
    'Los entornos no productivos usan datos ficticios/sanitizados',
    '## 4. Matriz de retención y eliminación',
    'duración + evento de inicio',
    'restaurar un backup no debe reintroducir silenciosamente datos',
    '## 5. Canal y proceso de derechos — PRIV-001',
    'no asumir desde Core un catálogo legal universal',
    '## 6. Analytics, cookies y trackers — PRIV-003',
    'Estado **antes de una decisión de consentimiento**',
    'Estado tras rechazar, cuando aplica:',
    'Comportamiento al retirar/cambiar la decisión, cuando aplica:',
    'No codificar en Core reglas como “todo analytics exige consentimiento”',
    '## 7. Consistencia con terceros',
    'No duplicar listas divergentes: los IDs estables enlazan ambos inventarios.',
    'No convertir automáticamente este inventario en `PASS`',
    'No usar P1-09 para imponer una CMP',
];

foreach ($requiredTemplateFragments as $fragment) {
    requirePrivacyFragment($template, $fragment);
}

requirePrivacyFragment(
    $profile,
    '- Inventario completado en `DATA-PRIVACY-INVENTORY.md`: sí / no / no aplica'
);
requirePrivacyFragment($profile, '- ¿El proyecto trata datos personales?: sí / no / por revisar');
requirePrivacyFragment($profile, '- Jurisdicción(es)/mercados evaluados:');
requirePrivacyFragment($profile, '- ¿Existen analytics/cookies/trackers?: sí / no / por revisar');
requirePrivacyFragment(
    $templatesReadme,
    '`DATA-PRIVACY-INVENTORY.md`: adopción P1-09/PRIV-001…003'
);

assert(!str_contains($template, 'api_key='));
assert(!str_contains($template, 'password='));
assert(!str_contains($template, 'token='));
assert(!str_contains($template, 'todos los proyectos deben usar una CMP'));

print "DATA_PRIVACY_INVENTORY_TEMPLATE_OK\n";
