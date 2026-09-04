<?php

declare(strict_types=1);

const READINESS_STATES = ['PASS', 'FAIL', 'N/A', 'NOT EVALUATED'];
const READINESS_SEVERITIES = ['BLOCKER', 'REQUIRED', 'RECOMMENDED', 'OPTIONAL'];
const READINESS_SEVERITY_RANK = ['OPTIONAL' => 1, 'RECOMMENDED' => 2, 'REQUIRED' => 3, 'BLOCKER' => 4];
const READINESS_LEVEL_RANK = ['A' => 1, 'B' => 2, 'C' => 3];

/** @return never */
function readinessFail(string $message): void
{
    fwrite(STDERR, 'READINESS_REPORT_CONFIG_ERROR ' . $message . PHP_EOL);
    exit(2);
}

/** @return array<string,string|null> */
function readinessOptions(array $argv): array
{
    $options = [
        'level' => null,
        'standard' => null,
        'evidence' => null,
        'json' => null,
        'markdown' => null,
    ];

    for ($i = 1, $count = count($argv); $i < $count; $i++) {
        $arg = $argv[$i];
        if ($arg === '--help' || $arg === '-h') {
            echo "Usage: php tools/production-readiness/report.php --level A|B|C [--evidence file.json] [--json path|-] [--markdown path|-] [--standard path]\n";
            exit(0);
        }
        if (!str_starts_with($arg, '--')) {
            readinessFail('unexpected_argument=' . $arg);
        }
        $name = substr($arg, 2);
        if (!array_key_exists($name, $options)) {
            readinessFail('unknown_option=' . $name);
        }
        if ($i + 1 >= $count) {
            readinessFail('missing_value=' . $name);
        }
        $options[$name] = $argv[++$i];
    }

    $level = strtoupper(trim((string) $options['level']));
    if (!isset(READINESS_LEVEL_RANK[$level])) {
        readinessFail('level_must_be_A_B_or_C');
    }
    $options['level'] = $level;

    return $options;
}

/** @return array{min_level:string,condition:?string} */
function readinessApplicability(string $value): array
{
    if (!preg_match('/^\s*([ABC])(?:\s*,\s*(.+))?\s*$/u', $value, $match)) {
        readinessFail('unsupported_applicability=' . $value);
    }

    $condition = isset($match[2]) ? trim($match[2]) : null;
    if ($condition === '') {
        $condition = null;
    }

    return ['min_level' => $match[1], 'condition' => $condition];
}

function readinessAppliesToLevel(string $minimum, string $level): bool
{
    return READINESS_LEVEL_RANK[$level] >= READINESS_LEVEL_RANK[$minimum];
}

function readinessEffectiveSeverity(string $canonical, string $level): string
{
    $matches = [];
    foreach (array_map('trim', explode(';', $canonical)) as $clause) {
        if ($clause === '') {
            continue;
        }
        if (!preg_match('/^(BLOCKER|REQUIRED|RECOMMENDED|OPTIONAL)\b(.*)$/u', $clause, $match)) {
            readinessFail('unsupported_severity_clause=' . $clause);
        }

        $severity = $match[1];
        $suffix = trim($match[2]);
        preg_match_all('/\b([ABC])\b/u', $suffix, $levelMatches);
        $explicitLevels = array_values(array_unique($levelMatches[1] ?? []));
        if ($explicitLevels !== [] && !in_array($level, $explicitLevels, true)) {
            continue;
        }
        $matches[] = $severity;
    }

    if ($matches === []) {
        readinessFail('severity_has_no_clause_for_level=' . $level . ';canonical=' . $canonical);
    }

    usort($matches, static fn (string $left, string $right): int => READINESS_SEVERITY_RANK[$right] <=> READINESS_SEVERITY_RANK[$left]);
    return $matches[0];
}

/**
 * @return array<string,array{
 *   id:string,category:string,rule:string,severity:string,applies:string,evidence_required:string,
 *   automatable:string,human:string,min_level:string,condition:?string
 * }>
 */
function readinessCanonicalRegistry(string $standardPath): array
{
    $lines = file($standardPath, FILE_IGNORE_NEW_LINES);
    if (!is_array($lines)) {
        readinessFail('cannot_read_standard=' . $standardPath);
    }

    $registry = [];
    $inCanonical = false;
    $category = 'Uncategorized';

    foreach ($lines as $line) {
        if (str_starts_with($line, '## 24. Registro canónico')) {
            $inCanonical = true;
            continue;
        }
        if (!$inCanonical) {
            continue;
        }
        if (preg_match('/^###\s+24\.\d+\s+(.+)$/u', $line, $heading)) {
            $category = trim($heading[1]);
            continue;
        }
        if (!preg_match('/^\|\s*([A-Z0-9]+-\d{3})\s*\|/', $line, $match)) {
            continue;
        }

        $cells = array_map('trim', explode('|', trim($line, '|')));
        if (count($cells) < 7) {
            readinessFail('malformed_canonical_row=' . $match[1]);
        }
        [$id, $rule, $severity, $applies, $evidence, $automatable, $human] = array_slice($cells, 0, 7);
        if (isset($registry[$id])) {
            readinessFail('duplicate_control=' . $id);
        }
        if (!in_array($automatable, ['Sí', 'Parcial', 'No'], true)) {
            readinessFail('unsupported_automatable=' . $id . ':' . $automatable);
        }
        if (!in_array($human, ['Sí', 'No'], true)) {
            readinessFail('unsupported_human=' . $id . ':' . $human);
        }
        $applicability = readinessApplicability($applies);
        $registry[$id] = [
            'id' => $id,
            'category' => $category,
            'rule' => $rule,
            'severity' => $severity,
            'applies' => $applies,
            'evidence_required' => $evidence,
            'automatable' => $automatable,
            'human' => $human,
            'min_level' => $applicability['min_level'],
            'condition' => $applicability['condition'],
        ];
    }

    if (count($registry) !== 126) {
        readinessFail('expected_126_controls_got=' . count($registry));
    }

    return $registry;
}

/** @return array{project:array<string,mixed>,controls:array<string,array<string,mixed>>} */
function readinessEvidence(?string $path, array $registry): array
{
    if ($path === null) {
        return ['project' => [], 'controls' => []];
    }
    $raw = @file_get_contents($path);
    if ($raw === false) {
        readinessFail('cannot_read_evidence=' . $path);
    }
    $decoded = json_decode($raw, true);
    if (!is_array($decoded) || json_last_error() !== JSON_ERROR_NONE) {
        readinessFail('invalid_evidence_json=' . $path);
    }
    $project = $decoded['project'] ?? [];
    $controls = $decoded['controls'] ?? [];
    if (!is_array($project) || !is_array($controls)) {
        readinessFail('evidence_requires_project_and_controls_objects');
    }
    foreach ($controls as $id => $evaluation) {
        if (!is_string($id) || !isset($registry[$id])) {
            readinessFail('unknown_evidence_control=' . (string) $id);
        }
        if (!is_array($evaluation)) {
            readinessFail('evaluation_must_be_object=' . $id);
        }
    }
    return ['project' => $project, 'controls' => $controls];
}

/** @return list<string> */
function readinessEvidenceRefs(array $evaluation, string $id): array
{
    $refs = $evaluation['evidence'] ?? [];
    if ($refs === null) {
        return [];
    }
    if (!is_array($refs)) {
        readinessFail('evidence_refs_must_be_array=' . $id);
    }
    $normalized = [];
    foreach ($refs as $ref) {
        if (!is_string($ref) || trim($ref) === '') {
            readinessFail('evidence_ref_must_be_nonempty_string=' . $id);
        }
        $normalized[] = trim($ref);
    }
    return $normalized;
}

function readinessValidReviewDate(mixed $value): bool
{
    if (!is_string($value) || !preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $value, $match)) {
        return false;
    }
    return checkdate((int) $match[2], (int) $match[3], (int) $match[1]);
}

/** @return array<string,mixed> */
function readinessEvaluation(string $id, array $control, ?array $provided): array
{
    $evaluation = $provided ?? [];
    $state = $evaluation['state'] ?? 'NOT EVALUATED';
    if (!is_string($state)) {
        readinessFail('state_must_be_string=' . $id);
    }
    $state = strtoupper(trim($state));
    if (!in_array($state, READINESS_STATES, true)) {
        readinessFail('invalid_state=' . $id . ':' . $state);
    }

    $evidence = readinessEvidenceRefs($evaluation, $id);
    $note = $evaluation['note'] ?? null;
    if ($note !== null && (!is_string($note) || trim($note) === '')) {
        readinessFail('note_must_be_nonempty_string=' . $id);
    }
    $justification = $evaluation['justification'] ?? null;
    if ($justification !== null && (!is_string($justification) || trim($justification) === '')) {
        readinessFail('justification_must_be_nonempty_string=' . $id);
    }
    $reviewedBy = $evaluation['reviewed_by'] ?? null;
    $reviewedAt = $evaluation['reviewed_at'] ?? null;

    if ($state === 'PASS' && $evidence === []) {
        readinessFail('pass_requires_evidence=' . $id);
    }
    if ($state === 'FAIL' && $evidence === [] && $note === null) {
        readinessFail('fail_requires_evidence_or_note=' . $id);
    }
    if ($state === 'N/A') {
        if (!is_string($justification) || trim($justification) === '' || $evidence === []) {
            readinessFail('na_requires_justification_and_evidence=' . $id);
        }
    }

    if ($control['human'] === 'Sí' && in_array($state, ['PASS', 'N/A'], true)) {
        if (!is_string($reviewedBy) || trim($reviewedBy) === '' || !readinessValidReviewDate($reviewedAt)) {
            readinessFail('human_pass_or_na_requires_reviewer_and_date=' . $id);
        }
    }

    return [
        'state' => $state,
        'evidence' => $evidence,
        'note' => is_string($note) ? trim($note) : null,
        'justification' => is_string($justification) ? trim($justification) : null,
        'reviewed_by' => is_string($reviewedBy) ? trim($reviewedBy) : null,
        'reviewed_at' => is_string($reviewedAt) ? $reviewedAt : null,
    ];
}

function readinessSourceLabel(string $standardPath, string $root): string
{
    $realStandard = realpath($standardPath);
    $realRoot = realpath($root);
    if ($realStandard !== false && $realRoot !== false) {
        $prefix = rtrim($realRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
        if (str_starts_with($realStandard, $prefix)) {
            return str_replace(DIRECTORY_SEPARATOR, '/', substr($realStandard, strlen($prefix)));
        }
    }

    return $realStandard !== false ? $realStandard : $standardPath;
}

/** @return array<string,mixed> */
function readinessBuildReport(string $level, string $standardPath, string $standardSource, array $registry, array $evidence): array
{
    $controls = [];
    $stateCounts = array_fill_keys(READINESS_STATES, 0);
    $severityCounts = array_fill_keys(READINESS_SEVERITIES, 0);
    $applicableCount = 0;
    $outOfLevelCount = 0;
    $blockingUnresolved = 0;
    $humanPending = 0;

    $validatedProvided = [];
    foreach ($evidence['controls'] as $id => $provided) {
        $validatedProvided[$id] = readinessEvaluation($id, $registry[$id], $provided);
    }

    foreach ($registry as $id => $control) {
        $applicable = readinessAppliesToLevel($control['min_level'], $level);
        if (!$applicable) {
            $outOfLevelCount++;
            $controls[] = [
                'id' => $id,
                'category' => $control['category'],
                'rule' => $control['rule'],
                'canonical_severity' => $control['severity'],
                'effective_severity' => null,
                'applies' => $control['applies'],
                'condition' => $control['condition'],
                'evidence_required' => $control['evidence_required'],
                'automatable' => $control['automatable'],
                'human_required' => $control['human'] === 'Sí',
                'scope' => 'out_of_level',
                'evaluation' => null,
            ];
            continue;
        }

        $effectiveSeverity = readinessEffectiveSeverity($control['severity'], $level);
        $evaluation = $validatedProvided[$id] ?? readinessEvaluation($id, $control, null);
        $applicableCount++;
        $stateCounts[$evaluation['state']]++;
        $severityCounts[$effectiveSeverity]++;

        if (in_array($effectiveSeverity, ['BLOCKER', 'REQUIRED'], true)
            && !in_array($evaluation['state'], ['PASS', 'N/A'], true)) {
            $blockingUnresolved++;
        }
        if ($control['human'] === 'Sí' && !in_array($evaluation['state'], ['PASS', 'N/A'], true)) {
            $humanPending++;
        }

        $controls[] = [
            'id' => $id,
            'category' => $control['category'],
            'rule' => $control['rule'],
            'canonical_severity' => $control['severity'],
            'effective_severity' => $effectiveSeverity,
            'applies' => $control['applies'],
            'condition' => $control['condition'],
            'evidence_required' => $control['evidence_required'],
            'automatable' => $control['automatable'],
            'human_required' => $control['human'] === 'Sí',
            'scope' => 'applicable',
            'evaluation' => $evaluation,
        ];
    }

    return [
        'schema_version' => 1,
        'source' => [
            'standard' => $standardSource,
            'sha256' => hash_file('sha256', $standardPath),
            'canonical_control_count' => count($registry),
        ],
        'level' => $level,
        'project' => $evidence['project'],
        'decision' => 'NOT_A_PRODUCTION_READY_DECLARATION',
        'disclaimer' => 'This report projects the canonical registry and explicit evidence only. It never auto-passes controls, never converts missing evidence to PASS, and does not replace required human review.',
        'summary' => [
            'applicable_controls' => $applicableCount,
            'out_of_level_controls' => $outOfLevelCount,
            'states' => $stateCounts,
            'effective_severity' => $severityCounts,
            'blocking_or_required_unresolved' => $blockingUnresolved,
            'human_review_pending' => $humanPending,
        ],
        'controls' => $controls,
    ];
}

function readinessMarkdown(array $report): string
{
    $escape = static function (mixed $value): string {
        if ($value === null) {
            return '';
        }
        $text = is_bool($value) ? ($value ? 'Sí' : 'No') : (string) $value;
        return str_replace(["\r", "\n", '\\', '|'], [' ', ' ', '\\\\', '\\|'], $text);
    };

    $summary = $report['summary'];
    $lines = [
        '# Production Readiness CI report — Level ' . $report['level'],
        '',
        '> **No es una declaración de Production Ready.** Proyecta el registro canónico y evidencia explícita; no auto-aprueba controles ni sustituye revisión humana.',
        '',
        '- Standard: `' . $escape($report['source']['standard']) . '`',
        '- Standard SHA-256: `' . $report['source']['sha256'] . '`',
        '- Controles canónicos: ' . $report['source']['canonical_control_count'],
        '- Aplicables por nivel: ' . $summary['applicable_controls'],
        '- Fuera de nivel: ' . $summary['out_of_level_controls'],
        '- BLOCKER/REQUIRED sin resolver: ' . $summary['blocking_or_required_unresolved'],
        '- Revisión humana pendiente: ' . $summary['human_review_pending'],
        '',
        '## Estados aplicables',
        '',
        '| Estado | Cantidad |',
        '| --- | ---: |',
    ];
    foreach (READINESS_STATES as $state) {
        $lines[] = '| ' . $escape($state) . ' | ' . $summary['states'][$state] . ' |';
    }

    $lines[] = '';
    $lines[] = '## Controles aplicables';
    $lines[] = '';
    $lines[] = '| ID | Severidad efectiva | Condición | Auto | Humana | Estado | Evidencia | Nota | Justificación | Revisado por | Fecha revisión |';
    $lines[] = '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |';
    foreach ($report['controls'] as $control) {
        if ($control['scope'] !== 'applicable') {
            continue;
        }
        $evaluation = $control['evaluation'];
        $lines[] = '| ' . $escape($control['id'])
            . ' | ' . $escape($control['effective_severity'])
            . ' | ' . $escape($control['condition'])
            . ' | ' . $escape($control['automatable'])
            . ' | ' . $escape($control['human_required'])
            . ' | ' . $escape($evaluation['state'])
            . ' | ' . $escape(implode(', ', $evaluation['evidence']))
            . ' | ' . $escape($evaluation['note'])
            . ' | ' . $escape($evaluation['justification'])
            . ' | ' . $escape($evaluation['reviewed_by'])
            . ' | ' . $escape($evaluation['reviewed_at']) . ' |';
    }

    return implode(PHP_EOL, $lines) . PHP_EOL;
}

function readinessWrite(?string $path, string $content): void
{
    if ($path === null) {
        return;
    }
    if ($path === '-') {
        echo $content;
        return;
    }
    $directory = dirname($path);
    if ($directory !== '.' && !is_dir($directory) && !@mkdir($directory, 0777, true) && !is_dir($directory)) {
        readinessFail('cannot_create_output_directory=' . $directory);
    }
    if (@file_put_contents($path, $content) === false) {
        readinessFail('cannot_write_output=' . $path);
    }
}

$options = readinessOptions($argv);
$root = dirname(__DIR__, 2);
$defaultStandardPath = $root . '/docs/production-readiness/PRODUCTION-READINESS-STANDARD.md';
$standardPath = $options['standard'] ?? $defaultStandardPath;
if (!is_string($standardPath) || !is_file($standardPath)) {
    readinessFail('standard_not_found=' . (string) $standardPath);
}
$standardSource = readinessSourceLabel($standardPath, $root);

$registry = readinessCanonicalRegistry($standardPath);
$evidence = readinessEvidence(is_string($options['evidence']) ? $options['evidence'] : null, $registry);
$report = readinessBuildReport((string) $options['level'], $standardPath, $standardSource, $registry, $evidence);
$json = json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
if (!is_string($json)) {
    readinessFail('json_encode_failed');
}
$json .= PHP_EOL;
$markdown = readinessMarkdown($report);

if ($options['json'] === null && $options['markdown'] === null) {
    echo $json;
    exit(0);
}
readinessWrite(is_string($options['json']) ? $options['json'] : null, $json);
readinessWrite(is_string($options['markdown']) ? $options['markdown'] : null, $markdown);
