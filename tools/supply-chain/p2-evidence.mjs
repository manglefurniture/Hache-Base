#!/usr/bin/env node

import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdirSync, readFileSync, statSync, writeFileSync} from 'node:fs';
import {basename, resolve} from 'node:path';

const ACTION_SHA = /^[0-9a-f]{40}$/;
const DIGEST = /@sha256:([0-9a-f]{64})(?:$|\s)/;
const COMMIT_SHA = /^[0-9a-f]{40}$/;
const ARTIFACT_SHA = /^[0-9a-f]{64}$/;

function fail(message, exitCode = 2) {
  process.stderr.write(`P2_SUPPLY_CHAIN_FAILED ${message}\n`);
  process.exit(exitCode);
}

function git(root, args) {
  try {
    return execFileSync('git', ['-C', root, ...args], {encoding: 'utf8'}).trimEnd();
  } catch {
    fail(`git_command_failed=${args.join('_')}`);
  }
}

function headCommit(root) {
  const value = git(root, ['rev-parse', 'HEAD']).trim().toLowerCase();
  if (!COMMIT_SHA.test(value)) fail('invalid_head_commit');
  return value;
}

function trackedFiles(root) {
  return git(root, ['ls-tree', '-r', '--name-only', 'HEAD'])
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean);
}

function headFile(root, path) {
  try {
    return execFileSync('git', ['-C', root, 'show', `HEAD:${path}`], {encoding: 'utf8'});
  } catch {
    fail(`tracked_file_unreadable=${path}`);
  }
}

function parseWorkflowReferences(path, content) {
  const references = [];
  const errors = [];
  const lines = content.split(/\r?\n/);

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    const uses = line.match(/^\s*-?\s*uses:\s*['"]?([^'"\s#]+)['"]?/);
    if (uses) {
      const reference = uses[1];
      if (reference.startsWith('./')) {
        references.push({kind: 'local_action', reference, path, line: index + 1});
      } else if (reference.startsWith('docker://')) {
        if (!DIGEST.test(`${reference} `)) {
          errors.push(`${path}:${index + 1}: docker action must be pinned by sha256 digest (${reference})`);
        } else {
          references.push({kind: 'container_action', reference, path, line: index + 1});
        }
      } else {
        const at = reference.lastIndexOf('@');
        const revision = at >= 0 ? reference.slice(at + 1).toLowerCase() : '';
        if (at <= 0 || !ACTION_SHA.test(revision)) {
          errors.push(`${path}:${index + 1}: external action must use a full 40-char commit SHA (${reference})`);
        } else {
          references.push({kind: 'github_action', reference: `${reference.slice(0, at)}@${revision}`, path, line: index + 1});
        }
      }
    }

    const image = line.match(/^\s*image:\s*['"]?([^'"\s#]+)['"]?/);
    if (image) {
      const reference = image[1];
      if (reference.includes('${{')) {
        errors.push(`${path}:${index + 1}: dynamic container image cannot prove an immutable digest`);
      } else if (!DIGEST.test(`${reference} `)) {
        errors.push(`${path}:${index + 1}: container image must be pinned by sha256 digest (${reference})`);
      } else {
        references.push({kind: 'container_image', reference, path, line: index + 1});
      }
    }
  }

  return {references, errors};
}

function workflowEvidence(root) {
  const files = trackedFiles(root).filter((path) => /^\.github\/workflows\/[^/]+\.ya?ml$/i.test(path));
  const references = [];
  const errors = [];
  for (const path of files) {
    const parsed = parseWorkflowReferences(path, headFile(root, path));
    references.push(...parsed.references);
    errors.push(...parsed.errors);
  }
  return {files, references, errors};
}

function verifyWorkflows(root) {
  const result = workflowEvidence(root);
  if (result.errors.length > 0) {
    for (const error of result.errors) process.stderr.write(`${error}\n`);
    fail(`mutable_workflow_references=${result.errors.length}`, 1);
  }
  process.stdout.write(`P2_IMMUTABLE_REFERENCES_OK workflows=${result.files.length} references=${result.references.length}\n`);
  return result;
}

function parseJson(text, label) {
  try {
    return JSON.parse(text);
  } catch {
    fail(`invalid_json=${label}`);
  }
}

function npmComponents(lock, lockPath) {
  if (![2, 3].includes(lock?.lockfileVersion) || typeof lock?.packages !== 'object' || lock.packages === null || Array.isArray(lock.packages)) {
    fail(`unsupported_npm_lock=${lockPath}`);
  }
  const components = [];
  for (const [packagePath, metadata] of Object.entries(lock.packages)) {
    if (packagePath === '' || !packagePath.includes('node_modules/') || metadata?.link === true) continue;
    if (!metadata || typeof metadata !== 'object') continue;
    const marker = packagePath.lastIndexOf('node_modules/');
    const fallbackName = packagePath.slice(marker + 'node_modules/'.length);
    const name = typeof metadata.name === 'string' && metadata.name.trim() !== '' ? metadata.name.trim() : fallbackName;
    const version = typeof metadata.version === 'string' ? metadata.version.trim() : '';
    if (!name || !version) continue;
    components.push({ecosystem: 'npm', name, version, source: lockPath});
  }
  return components;
}

function composerComponents(lock, lockPath) {
  if (!Array.isArray(lock?.packages) || (lock['packages-dev'] !== undefined && !Array.isArray(lock['packages-dev']))) {
    fail(`unsupported_composer_lock=${lockPath}`);
  }
  const lists = [...lock.packages, ...(Array.isArray(lock['packages-dev']) ? lock['packages-dev'] : [])];
  const components = [];
  for (const metadata of lists) {
    const name = typeof metadata?.name === 'string' ? metadata.name.trim() : '';
    const version = typeof metadata?.version === 'string' ? metadata.version.trim() : '';
    if (name && version) components.push({ecosystem: 'composer', name, version, source: lockPath});
  }
  return components;
}

function dependencyInventory(root) {
  const files = trackedFiles(root);
  const supported = files.filter((path) => /(^|\/)(package-lock\.json|npm-shrinkwrap\.json|composer\.lock)$/.test(path));
  const unsupported = files.filter((path) => /(^|\/)(yarn\.lock|pnpm-lock\.yaml)$/.test(path));
  const components = [];

  for (const path of supported) {
    const parsed = parseJson(headFile(root, path), path);
    if (path.endsWith('composer.lock')) components.push(...composerComponents(parsed, path));
    else components.push(...npmComponents(parsed, path));
  }

  const seen = new Set();
  const unique = components
    .sort((a, b) => `${a.ecosystem}:${a.name}:${a.version}:${a.source}`.localeCompare(`${b.ecosystem}:${b.name}:${b.version}:${b.source}`))
    .filter((item) => {
      const key = `${item.ecosystem}\0${item.name}\0${item.version}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

  const coverage = unsupported.length > 0
    ? 'PARTIAL_UNSUPPORTED_LOCKFILES'
    : supported.length > 0
      ? 'SUPPORTED_LOCKFILES_PARSED'
      : 'NO_SUPPORTED_LOCKFILES_FOUND';

  return {components: unique, supported, unsupported, coverage};
}

function componentRef(component) {
  return `urn:hache:component:${encodeURIComponent(component.ecosystem)}:${encodeURIComponent(component.name)}:${encodeURIComponent(component.version)}`;
}

function sha256Bytes(value) {
  return createHash('sha256').update(value).digest('hex');
}

function stableJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function loadArtifactManifest(path) {
  const manifest = parseJson(readFileSync(path, 'utf8'), path);
  if (manifest?.schema !== 'hache-artifact-manifest/v1') fail('artifact_manifest_schema_mismatch');
  if (manifest?.decision !== 'ARTIFACT_IDENTITY_ONLY_NOT_PRODUCTION_READY_DECLARATION') fail('artifact_manifest_decision_mismatch');
  if (!COMMIT_SHA.test(String(manifest?.source_commit ?? '').toLowerCase())) fail('artifact_manifest_invalid_source_commit');
  if (!ARTIFACT_SHA.test(String(manifest?.artifact_sha256 ?? '').toLowerCase())) fail('artifact_manifest_invalid_sha256');
  if (!Number.isInteger(manifest?.artifact_size_bytes) || manifest.artifact_size_bytes < 0) fail('artifact_manifest_invalid_size');
  for (const field of ['artifact_name', 'ci_run_ref', 'build_evidence_ref', 'test_evidence_ref', 'created_at']) {
    if (typeof manifest?.[field] !== 'string' || manifest[field].trim() === '') fail(`artifact_manifest_invalid_field=${field}`);
  }
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(manifest.created_at)) fail('artifact_manifest_invalid_created_at');
  return manifest;
}

function verifyArtifact(artifactPath, manifest) {
  let bytes;
  let size;
  try {
    bytes = readFileSync(artifactPath);
    size = statSync(artifactPath).size;
  } catch {
    fail('artifact_unreadable');
  }
  if (basename(artifactPath) !== manifest.artifact_name) fail('artifact_name_mismatch', 1);
  if (size !== manifest.artifact_size_bytes) fail('artifact_size_mismatch', 1);
  const digest = sha256Bytes(bytes);
  if (digest !== manifest.artifact_sha256.toLowerCase()) fail('artifact_sha256_mismatch', 1);
}

function cleanLabel(value, field) {
  const normalized = String(value ?? '').trim();
  if (normalized === '' || normalized.length > 300 || /[\x00-\x1f\x7f]/.test(normalized)) fail(`invalid_argument=${field}`);
  return normalized;
}

function generateEvidence({root, manifestPath, artifactPath, outputDir, project, repository}) {
  const manifest = loadArtifactManifest(manifestPath);
  verifyArtifact(artifactPath, manifest);
  const head = headCommit(root);
  const sourceCommit = manifest.source_commit.toLowerCase();
  if (head !== sourceCommit) fail(`source_commit_mismatch expected=${sourceCommit} actual=${head}`, 1);

  const workflow = verifyWorkflows(root);
  const inventory = dependencyInventory(root);
  const rootRef = `urn:hache:application:${encodeURIComponent(project)}:${sourceCommit}`;
  const components = inventory.components.map((component) => ({
    type: 'library',
    'bom-ref': componentRef(component),
    name: component.name,
    version: component.version,
    properties: [
      {name: 'hache:ecosystem', value: component.ecosystem},
      {name: 'hache:lock_source', value: component.source},
    ],
  }));

  const sbom = {
    bomFormat: 'CycloneDX',
    specVersion: '1.6',
    version: 1,
    metadata: {
      component: {
        type: 'application',
        'bom-ref': rootRef,
        name: project,
        version: sourceCommit,
        hashes: [{alg: 'SHA-256', content: manifest.artifact_sha256.toLowerCase()}],
      },
      properties: [
        {name: 'hache:source_commit', value: sourceCommit},
        {name: 'hache:dependency_coverage', value: inventory.coverage},
        {name: 'hache:supported_lockfiles', value: inventory.supported.join(',')},
        {name: 'hache:unsupported_lockfiles', value: inventory.unsupported.join(',')},
        {name: 'hache:decision', value: 'SBOM_INVENTORY_ONLY_NOT_VULNERABILITY_OR_LICENSE_APPROVAL'},
      ],
    },
    components,
    dependencies: [{ref: rootRef, dependsOn: components.map((component) => component['bom-ref']).sort()}],
  };

  const sbomText = stableJson(sbom);
  const materialMap = new Map();
  for (const item of workflow.references) {
    if (item.kind === 'local_action') continue;
    const key = `${item.kind}\0${item.reference}\0${item.path}`;
    materialMap.set(key, {kind: item.kind, reference: item.reference, workflow: item.path});
  }
  const materials = [...materialMap.values()]
    .sort((a, b) => `${a.kind}:${a.reference}:${a.workflow}`.localeCompare(`${b.kind}:${b.reference}:${b.workflow}`));

  const provenance = {
    schema: 'hache-release-provenance/v1',
    subject: {
      name: manifest.artifact_name,
      sha256: manifest.artifact_sha256.toLowerCase(),
      size_bytes: manifest.artifact_size_bytes,
    },
    source: {repository, commit: sourceCommit},
    ci: {
      run_ref: manifest.ci_run_ref,
      build_evidence_ref: manifest.build_evidence_ref,
      test_evidence_ref: manifest.test_evidence_ref,
    },
    materials,
    sbom: {name: 'sbom.cdx.json', sha256: sha256Bytes(sbomText), dependency_coverage: inventory.coverage},
    created_at: manifest.created_at,
    decision: 'UNSIGNED_PROVENANCE_LINKAGE_ONLY_NOT_SLSA_ATTESTATION',
  };

  mkdirSync(outputDir, {recursive: true});
  const sbomPath = resolve(outputDir, 'sbom.cdx.json');
  const provenancePath = resolve(outputDir, 'provenance.json');
  writeFileSync(sbomPath, sbomText, {encoding: 'utf8', mode: 0o600});
  writeFileSync(provenancePath, stableJson(provenance), {encoding: 'utf8', mode: 0o600});

  process.stdout.write(`P2_RELEASE_EVIDENCE_OK source_commit=${sourceCommit} components=${components.length} materials=${materials.length} sbom=${sbomPath} provenance=${provenancePath}\n`);
}

function parseGenerateArgs(argv) {
  const options = {};
  if (argv.length % 2 !== 0) fail('invalid_generate_arguments');
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || value === undefined) fail('invalid_generate_arguments');
    options[key.slice(2)] = value;
  }
  for (const required of ['root', 'artifact-manifest', 'artifact', 'output-dir', 'project', 'repository']) {
    if (!options[required]) fail(`missing_argument=${required}`);
  }
  return {
    root: resolve(options.root),
    manifestPath: resolve(options['artifact-manifest']),
    artifactPath: resolve(options.artifact),
    outputDir: resolve(options['output-dir']),
    project: cleanLabel(options.project, 'project'),
    repository: cleanLabel(options.repository, 'repository'),
  };
}

const command = process.argv[2] ?? '';
if (command === 'verify-workflows') {
  verifyWorkflows(resolve(process.argv[3] ?? '.'));
} else if (command === 'generate') {
  generateEvidence(parseGenerateArgs(process.argv.slice(3)));
} else {
  fail('usage=verify-workflows|generate');
}
