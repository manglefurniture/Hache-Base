<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$standardPath = $root . '/docs/production-readiness/PRODUCTION-READINESS-STANDARD.md';
$checklistPath = $root . '/docs/production-readiness/PRODUCTION-READINESS-CHECKLIST.md';

$standard = file($standardPath, FILE_IGNORE_NEW_LINES);
$checklist = file($checklistPath, FILE_IGNORE_NEW_LINES);

assert(is_array($standard));
assert(is_array($checklist));

$canonical = [];
$inCanonical = false;
foreach ($standard as $line) {
    if (str_starts_with($line, '## 24. Registro canónico')) {
        $inCanonical = true;
        continue;
    }
    if (!$inCanonical || !preg_match('/^\|\s*([A-Z0-9]+-\d{3})\s*\|/', $line, $match)) {
        continue;
    }

    $cells = array_map('trim', explode('|', trim($line, '|')));
    assert(count($cells) >= 7, 'Malformed canonical row: ' . $line);
    [$id, $rule, $severity, $applies, $evidence] = array_slice($cells, 0, 5);
    assert(!isset($canonical[$id]), 'Duplicate Standard ID: ' . $id);
    $canonical[$id] = [
        'rule' => $rule,
        'severity' => $severity,
        'applies' => $applies,
        'evidence' => $evidence,
    ];
}

$projected = [];
foreach ($checklist as $line) {
    if (!preg_match('/^\|\s*\[([A-Z0-9]+-\d{3})\]\s*\|/', $line, $match)) {
        continue;
    }

    $cells = array_map('trim', explode('|', trim($line, '|')));
    assert(count($cells) >= 7, 'Malformed Checklist row: ' . $line);
    $id = trim($cells[0], '[]');
    assert(!isset($projected[$id]), 'Duplicate Checklist ID: ' . $id);
    $projected[$id] = [
        'severity' => $cells[1],
        'applies' => $cells[2],
        'rule' => $cells[3],
        'evidence' => $cells[4],
        'state' => $cells[5],
    ];
}

assert(count($canonical) === 126, 'Expected 126 canonical controls, got ' . count($canonical));
assert(count($projected) === 126, 'Expected 126 Checklist controls, got ' . count($projected));
assert(array_keys($canonical) === array_keys($projected), 'Standard/Checklist ID order or set differs.');

foreach ($canonical as $id => $expected) {
    $actual = $projected[$id];
    assert($actual['severity'] === $expected['severity'], $id . ' severity differs.');
    assert($actual['applies'] === $expected['applies'], $id . ' applicability differs.');
    assert($actual['rule'] === $expected['rule'], $id . ' rule differs.');
    assert($actual['evidence'] === $expected['evidence'], $id . ' evidence differs.');
    assert($actual['state'] === 'NOT EVALUATED', $id . ' must start NOT EVALUATED.');
}

echo "PRODUCTION_READINESS_DOCS_OK\n";
