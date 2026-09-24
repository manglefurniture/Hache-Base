<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$template = file_get_contents($root . '/templates/RESTORE-HISTORY.md');
$templatesReadme = file_get_contents($root . '/templates/README.md');

assert(is_string($template));
assert(is_string($templatesReadme));

$require = static function (string $haystack, string $fragment): void {
    assert(str_contains($haystack, $fragment), 'missing P2-07 restore history fragment: ' . $fragment);
};

foreach ([
    'Restore History — P2-07',
    'La cadencia, RPO y RTO son **project-owned**',
    '`trigger`: `schedule`',
    'depender explícitamente de su finalización exitosa',
    'Dos cron independientes con una separación horaria no constituyen una dependencia',
    'guard fail-closed equivalente que evita consumir un backup stale',
    '`run_id` y, si aplica, `run_attempt` únicos',
    'Una ejecución fallida se conserva como fallo',
    'Un rerun debe tener identidad distinguible',
    'Configurar un cron **no** equivale a P2-07 cerrado',
    'al menos una ejecución programada real revisada humanamente',
    'Una evidencia bootstrap manual anterior',
    'fallos y reruns quedan históricamente distinguibles',
    'la retención conserva suficiente historia',
    'una revisión humana confirma',
    'no** convierte automáticamente P2-07, DB-006 ni DB-007 en PASS',
] as $fragment) {
    $require($template, $fragment);
}

$require($templatesReadme, '`RESTORE-HISTORY.md`: adopción P2-07');

assert(!str_contains($template, 'RPO aprobado: `86400`'));
assert(!str_contains($template, 'RTO aprobado: `3600`'));
assert(!str_contains($template, "cron: '17 10 1 * *'"));
assert(!str_contains($template, 'password='));
assert(!str_contains($template, 'Authorization: Bearer'));

print "RESTORE_HISTORY_TEMPLATE_OK\n";
