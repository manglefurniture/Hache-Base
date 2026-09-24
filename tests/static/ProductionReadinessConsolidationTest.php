<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);

/** @return string */
function consolidationDocument(string $root, string $relativePath): string
{
    $contents = file_get_contents($root . '/' . $relativePath);
    assert(is_string($contents), 'Could not read ' . $relativePath);
    return $contents;
}

$roadmap = consolidationDocument($root, 'docs/production-readiness/PRODUCTION-READINESS-ROADMAP.md');
$consolidation = consolidationDocument($root, 'docs/production-readiness/CONSOLIDATION-2026-09.md');
$p2Status = consolidationDocument($root, 'docs/production-readiness/P2-IMPLEMENTATION-STATUS.md');
$p1Status = consolidationDocument($root, 'docs/production-readiness/P1-IMPLEMENTATION-STATUS.md');
$index = consolidationDocument($root, 'docs/production-readiness/README.md');
$readme = consolidationDocument($root, 'README.md');
$catalog = consolidationDocument($root, 'CATALOGO_MODULOS.md');
$audit = consolidationDocument($root, 'docs/production-readiness/PRODUCTION-READINESS-AUDIT.md');
$normalization = consolidationDocument($root, 'docs/production-readiness/PRODUCTION-READINESS-NORMALIZATION-REPORT.md');
$supplyChainPolicy = consolidationDocument($root, 'security/supply-chain/POLICY.md');

assert(!str_contains($roadmap, 'Propuesta de implementación futura; no ejecutada'));
assert(str_contains($roadmap, 'roadmap vivo consolidado al 24 de septiembre de 2026'));
assert(str_contains($roadmap, 'P2-05 | Rate limit shared-store'));
assert(str_contains($roadmap, 'NOT STARTED / NOT CURRENTLY JUSTIFIED'));
assert(str_contains($roadmap, 'IMPLEMENTED; PILOT ACTIVE / RECURRING EVIDENCE PENDING'));
assert(substr_count($roadmap, 'NOT CURRENTLY JUSTIFIED') >= 6, 'Expected P2-05 plus every P3 item.');

foreach ([
    '### P2-04 — matriz de adopción contra `templates/UPLOAD-ADOPTION.md`',
    '**PASS DEMONSTRATED**',
    '**NOT EVALUATED**',
    '**FAIL DEMONSTRATED**',
    '**NOT STARTED / NOT CURRENTLY JUSTIFIED**',
    '**PILOT ACTIVE / RECURRING EVIDENCE PENDING**',
    '2026-10-01',
    'is_uploaded_file()',
    'PR #7',
] as $fragment) {
    assert(str_contains($consolidation, $fragment), 'Missing consolidation fragment: ' . $fragment);
}

assert(!str_contains($p2Status, 'Falta únicamente la revisión humana final'));
assert(str_contains($p2Status, 'TECHNICALLY VERIFIED / HUMAN REVIEW PENDING'));
assert(str_contains($p2Status, 'NOT STARTED / NOT CURRENTLY JUSTIFIED'));
assert(str_contains($p2Status, 'IMPLEMENTED / PILOT ACTIVE / RECURRING EVIDENCE PENDING'));
assert(str_contains($p2Status, 'NOT EVALUATED'));
assert(!str_contains($p1Status, 'No inicia P2 ni migra automáticamente'));
assert(str_contains($p1Status, 'P2 fue implementado posteriormente de forma incremental'));
assert(str_contains($supplyChainPolicy, 'P2-06 aporta por separado SBOM/provenance de enlace'));

assert(str_contains($index, 'CONSOLIDATION-2026-09.md'));
assert(str_contains($readme, 'P0-11 aporta el contrato reusable'));
assert(str_contains($catalog, 'Norma canónica + P0/P1 implementados + P2 incremental'));
assert(str_contains($audit, 'fotografía histórica del 2026-09-01'));
assert(str_contains($normalization, 'corte exclusivamente documental del 2026-09-01'));

echo "PRODUCTION_READINESS_CONSOLIDATION_OK\n";
