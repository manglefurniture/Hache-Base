<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$template = file_get_contents($root . '/templates/READ-MODEL-CONTRACT.md');
$runtime = file_get_contents($root . '/src/common/ReadModelContract.php');

assert(is_string($template));
assert(is_string($runtime));

foreach ([
    'Autoridad única',
    'Numerador',
    'Denominador',
    'Exclusiones',
    'Corte (`cutoff_at`)',
    'Zona horaria',
    '`0` solo significa cero',
    '`value=null`',
    '`forward_only` exige un marcador de inicio durable',
    '`history_reconstructed`',
    'Viva/reconciliable',
    'Snapshot histórico',
    'consultas read-only',
    'Nunca resuelve, paga, cancela, inscribe, bloquea',
    'PII por defecto',
    '`HUMAN_REVIEW_REQUIRED`',
] as $fragment) {
    assert(str_contains($template, $fragment), 'missing read-model contract fragment: ' . $fragment);
}

foreach (['natacion', 'alumno', 'profesor', 'sharky', 'p1/p15', 'proa'] as $forbidden) {
    assert(!str_contains(strtolower($runtime), $forbidden), 'runtime must not contain project-specific default: ' . $forbidden);
}

echo "ReadModelContractTemplateTest OK\n";
