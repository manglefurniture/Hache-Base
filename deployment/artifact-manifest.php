<?php

declare(strict_types=1);

const ARTIFACT_SCHEMA = 'hache-artifact-manifest/v1';

function fail(string $message, int $exit = 2): never
{
    fwrite(STDERR, "ARTIFACT_MANIFEST_FAILED {$message}\n");
    exit($exit);
}

function requiredEnv(string $name): string
{
    $value = getenv($name);
    if ($value === false || trim($value) === '') {
        fail("missing_env={$name}");
    }

    return trim($value);
}

function canonicalCommit(string $value, string $field): string
{
    if (!preg_match('/^[0-9a-f]{40}$/i', $value)) {
        fail("invalid_{$field}");
    }

    return strtolower($value);
}

function artifactMetadata(string $artifactPath): array
{
    if (!is_file($artifactPath) || !is_readable($artifactPath)) {
        fail('artifact_unreadable');
    }

    $size = filesize($artifactPath);
    $sha = hash_file('sha256', $artifactPath);
    if ($size === false || $sha === false) {
        fail('artifact_metadata_unavailable');
    }

    return [
        'size' => $size,
        'sha256' => strtolower($sha),
    ];
}

function validateCreatedAt(string $value): void
{
    $parsed = DateTimeImmutable::createFromFormat(
        '!Y-m-d\\TH:i:s\\Z',
        $value,
        new DateTimeZone('UTC')
    );
    $errors = DateTimeImmutable::getLastErrors();

    if ($parsed === false || ($errors !== false && ($errors['warning_count'] > 0 || $errors['error_count'] > 0))) {
        fail('invalid_created_at');
    }

    if ($parsed->format('Y-m-d\\TH:i:s\\Z') !== $value) {
        fail('invalid_created_at_roundtrip');
    }
}

function loadManifest(string $manifestPath): array
{
    if (!is_file($manifestPath) || !is_readable($manifestPath)) {
        fail('manifest_unreadable');
    }

    $raw = file_get_contents($manifestPath);
    if ($raw === false) {
        fail('manifest_read_failed');
    }

    try {
        $decoded = json_decode($raw, true, 64, JSON_THROW_ON_ERROR);
    } catch (JsonException) {
        fail('manifest_invalid_json');
    }

    if (!is_array($decoded)) {
        fail('manifest_not_object');
    }

    return $decoded;
}

function requireStringField(array $manifest, string $field): string
{
    $value = $manifest[$field] ?? null;
    if (!is_string($value) || trim($value) === '') {
        fail("manifest_invalid_field={$field}");
    }

    return trim($value);
}

$command = $argv[1] ?? '';
if (!in_array($command, ['create', 'verify'], true)) {
    fail('usage=create|verify');
}

$artifactPath = requiredEnv('ARTIFACT_PATH');
$manifestPath = requiredEnv('ARTIFACT_MANIFEST');

if ($command === 'create') {
    $directory = dirname($manifestPath);
    if (!is_dir($directory) || !is_writable($directory)) {
        fail('manifest_directory_not_writable');
    }

    $artifactReal = realpath($artifactPath);
    $directoryReal = realpath($directory);
    if ($artifactReal === false || $directoryReal === false) {
        fail('artifact_or_manifest_path_unresolved');
    }

    $manifestTarget = $directoryReal . DIRECTORY_SEPARATOR . basename($manifestPath);
    $manifestExistingReal = file_exists($manifestPath) ? realpath($manifestPath) : false;
    if ($artifactReal === $manifestTarget || ($manifestExistingReal !== false && $artifactReal === $manifestExistingReal)) {
        fail('artifact_manifest_path_collision');
    }

    $sourceCommit = canonicalCommit(requiredEnv('SOURCE_COMMIT'), 'source_commit');
    $ciRunRef = requiredEnv('CI_RUN_REF');
    $buildEvidenceRef = requiredEnv('BUILD_EVIDENCE_REF');
    $testEvidenceRef = requiredEnv('TEST_EVIDENCE_REF');
    $metadata = artifactMetadata($artifactReal);

    $manifest = [
        'schema' => ARTIFACT_SCHEMA,
        'source_commit' => $sourceCommit,
        'artifact_name' => basename($artifactReal),
        'artifact_size_bytes' => $metadata['size'],
        'artifact_sha256' => $metadata['sha256'],
        'ci_run_ref' => $ciRunRef,
        'build_evidence_ref' => $buildEvidenceRef,
        'test_evidence_ref' => $testEvidenceRef,
        'created_at' => gmdate('Y-m-d\\TH:i:s\\Z'),
        'decision' => 'ARTIFACT_IDENTITY_ONLY_NOT_PRODUCTION_READY_DECLARATION',
    ];

    try {
        $json = json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
    } catch (JsonException) {
        fail('manifest_json_encode_failed');
    }

    $temporary = tempnam($directoryReal, '.artifact-manifest-');
    if ($temporary === false) {
        fail('manifest_temp_create_failed');
    }

    try {
        if (file_put_contents($temporary, $json, LOCK_EX) === false) {
            fail('manifest_write_failed');
        }
        @chmod($temporary, 0600);
        if (!rename($temporary, $manifestTarget)) {
            fail('manifest_rename_failed');
        }
    } finally {
        if (is_file($temporary)) {
            @unlink($temporary);
        }
    }

    printf(
        "ARTIFACT_MANIFEST_CREATED source_commit=%s sha256=%s size=%d manifest=%s\n",
        $sourceCommit,
        $metadata['sha256'],
        $metadata['size'],
        $manifestTarget
    );
    exit(0);
}

$manifest = loadManifest($manifestPath);
if (($manifest['schema'] ?? null) !== ARTIFACT_SCHEMA) {
    fail('manifest_schema_mismatch');
}
if (($manifest['decision'] ?? null) !== 'ARTIFACT_IDENTITY_ONLY_NOT_PRODUCTION_READY_DECLARATION') {
    fail('manifest_decision_missing');
}

$sourceCommit = canonicalCommit(requireStringField($manifest, 'source_commit'), 'manifest_source_commit');
$artifactName = requireStringField($manifest, 'artifact_name');
$shaExpected = strtolower(requireStringField($manifest, 'artifact_sha256'));
$ciRunRef = requireStringField($manifest, 'ci_run_ref');
$buildEvidenceRef = requireStringField($manifest, 'build_evidence_ref');
$testEvidenceRef = requireStringField($manifest, 'test_evidence_ref');
$createdAt = requireStringField($manifest, 'created_at');

if (!preg_match('/^[0-9a-f]{64}$/', $shaExpected)) {
    fail('manifest_invalid_sha256');
}
if ($artifactName !== basename($artifactPath)) {
    fail('artifact_name_mismatch');
}

$sizeExpected = $manifest['artifact_size_bytes'] ?? null;
if (!is_int($sizeExpected) || $sizeExpected < 0) {
    fail('manifest_invalid_size');
}

validateCreatedAt($createdAt);
$metadata = artifactMetadata($artifactPath);
if ($metadata['size'] !== $sizeExpected) {
    fail('artifact_size_mismatch', 1);
}
if (!hash_equals($shaExpected, $metadata['sha256'])) {
    fail('artifact_sha256_mismatch', 1);
}

$expectedCommit = getenv('EXPECTED_COMMIT');
if ($expectedCommit !== false && trim($expectedCommit) !== '') {
    $expectedCommit = canonicalCommit(trim($expectedCommit), 'expected_commit');
    if (!hash_equals($expectedCommit, $sourceCommit)) {
        fail('source_commit_mismatch', 1);
    }
}

// These fields are required above so artifact identity never loses its CI/test linkage.
assert($ciRunRef !== '');
assert($buildEvidenceRef !== '');
assert($testEvidenceRef !== '');

printf(
    "ARTIFACT_VERIFY_OK source_commit=%s sha256=%s size=%d\n",
    $sourceCommit,
    $metadata['sha256'],
    $metadata['size']
);
