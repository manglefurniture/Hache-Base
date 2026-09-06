import assert from 'node:assert/strict';
import {execFileSync, spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

const root = resolve(new URL('../..', import.meta.url).pathname);
const tool = join(root, 'tools/supply-chain/p2-evidence.mjs');

function run(command, args, cwd) {
  return execFileSync(command, args, {cwd, encoding: 'utf8'});
}

function initRepo(prefix, workflow) {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  mkdirSync(join(dir, '.github/workflows'), {recursive: true});
  writeFileSync(join(dir, '.github/workflows/ci.yml'), workflow);
  run('git', ['init'], dir);
  run('git', ['config', 'user.email', 'fixture@example.invalid'], dir);
  run('git', ['config', 'user.name', 'Fixture'], dir);
  return dir;
}

function commitFixture(dir, message = 'fixture') {
  run('git', ['add', '.'], dir);
  run('git', ['commit', '-m', message], dir);
}

function verifyFixture(dir) {
  return spawnSync('node', [tool, 'verify-workflows', dir], {encoding: 'utf8'});
}

// The repository's own Level C-facing workflow references must be immutable.
const ownVerification = run('node', [tool, 'verify-workflows', root], root);
assert.match(ownVerification, /P2_IMMUTABLE_REFERENCES_OK/);

const checkoutSha = '11d5960a326750d5838078e36cf38b85af677262';
const imageDigest = '2439dcd7d14010ecd1ff7a4e1c5abe8e208c34fe35290744deeeaac3569043c3';
const fixtureWorkflow = `name: fixture\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    services:\n      db:\n        image: mariadb:11.8@sha256:${imageDigest}\n    steps:\n      - uses: actions/checkout@${checkoutSha}\n      - uses: ./local-action\n`;

const fixture = initRepo('hache-p2-evidence-', fixtureWorkflow);
try {
  writeFileSync(join(fixture, 'package.json'), JSON.stringify({name: 'fixture', version: '1.0.0', packageManager: 'npm@11.0.0'}));
  writeFileSync(join(fixture, 'package-lock.json'), JSON.stringify({
    name: 'fixture',
    lockfileVersion: 3,
    packages: {
      '': {name: 'fixture', version: '1.0.0', dependencies: {pkg: '^1.0.0'}},
      'node_modules/pkg': {name: 'pkg', version: '1.2.3'},
    },
  }));
  writeFileSync(join(fixture, 'composer.lock'), JSON.stringify({
    packages: [{name: 'vendor/lib', version: '2.4.0'}],
    'packages-dev': [],
  }));
  mkdirSync(join(fixture, 'local-action'), {recursive: true});
  writeFileSync(join(fixture, 'local-action/action.yml'), 'name: local\nruns:\n  using: composite\n  steps: []\n');
  commitFixture(fixture);
  const commit = run('git', ['rev-parse', 'HEAD'], fixture).trim();

  const artifact = Buffer.from('artifact-bytes');
  const artifactPath = join(fixture, 'artifact.tar.gz');
  const artifactSha = createHash('sha256').update(artifact).digest('hex');
  writeFileSync(artifactPath, artifact);
  const manifest = {
    schema: 'hache-artifact-manifest/v1',
    source_commit: commit,
    artifact_name: 'artifact.tar.gz',
    artifact_size_bytes: artifact.length,
    artifact_sha256: artifactSha,
    ci_run_ref: 'fixture-run-1',
    build_evidence_ref: 'fixture-build-1',
    test_evidence_ref: 'fixture-tests-1',
    created_at: '2026-09-06T22:00:00Z',
    decision: 'ARTIFACT_IDENTITY_ONLY_NOT_PRODUCTION_READY_DECLARATION',
  };
  const manifestPath = join(fixture, 'artifact.manifest.json');
  writeFileSync(manifestPath, JSON.stringify(manifest));

  const output = join(fixture, 'evidence');
  const generation = run('node', [
    tool,
    'generate',
    '--root', fixture,
    '--artifact-manifest', manifestPath,
    '--artifact', artifactPath,
    '--output-dir', output,
    '--project', 'fixture-app',
    '--repository', 'https://example.invalid/fixture.git',
  ], fixture);
  assert.match(generation, /P2_RELEASE_EVIDENCE_OK/);

  const sbom = JSON.parse(readFileSync(join(output, 'sbom.cdx.json'), 'utf8'));
  assert.equal(sbom.bomFormat, 'CycloneDX');
  assert.equal(sbom.specVersion, '1.6');
  assert.equal(sbom.metadata.component.name, 'fixture-app');
  assert.equal(sbom.metadata.component.version, commit);
  assert.equal(sbom.metadata.component.hashes[0].content, artifactSha);
  assert.deepEqual(sbom.components.map((component) => `${component.name}@${component.version}`).sort(), [
    'pkg@1.2.3',
    'vendor/lib@2.4.0',
  ]);

  const provenance = JSON.parse(readFileSync(join(output, 'provenance.json'), 'utf8'));
  assert.equal(provenance.schema, 'hache-release-provenance/v1');
  assert.equal(provenance.subject.sha256, artifactSha);
  assert.equal(provenance.source.commit, commit);
  assert.equal(provenance.decision, 'UNSIGNED_PROVENANCE_LINKAGE_ONLY_NOT_SLSA_ATTESTATION');
  assert.equal(provenance.materials_scope, 'VERSIONED_GITHUB_ACTIONS_AND_WORKFLOW_CONTAINERS_ONLY');
  assert.ok(provenance.materials.some((item) => item.reference === `actions/checkout@${checkoutSha}`));
  assert.ok(provenance.materials.some((item) => item.reference.includes(`@sha256:${imageDigest}`)));
  assert.match(provenance.sbom.sha256, /^[0-9a-f]{64}$/);

  // Fabricating only the manifest is insufficient: evidence must re-hash the artifact bytes.
  writeFileSync(artifactPath, Buffer.from('tampered-artifact'));
  const tampered = spawnSync('node', [
    tool,
    'generate',
    '--root', fixture,
    '--artifact-manifest', manifestPath,
    '--artifact', artifactPath,
    '--output-dir', join(fixture, 'tampered-evidence'),
    '--project', 'fixture-app',
    '--repository', 'https://example.invalid/fixture.git',
  ], {encoding: 'utf8'});
  assert.equal(tampered.status, 1);
  assert.match(tampered.stderr, /artifact_(size|sha256)_mismatch/);
} finally {
  rmSync(fixture, {recursive: true, force: true});
}

// A mutable block-style tag is rejected.
const mutable = initRepo('hache-p2-mutable-', 'name: bad\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n');
try {
  commitFixture(mutable, 'mutable block action');
  const result = verifyFixture(mutable);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /external action must use a full 40-char commit SHA/);
} finally {
  rmSync(mutable, {recursive: true, force: true});
}

// Flow-style `uses` is security-relevant too: a mutable ref must not bypass the checker.
const mutableFlow = initRepo(
  'hache-p2-mutable-flow-',
  'name: bad-flow\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - { uses: actions/checkout@v4 }\n',
);
try {
  commitFixture(mutableFlow, 'mutable flow action');
  const result = verifyFixture(mutableFlow);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /external action must use a full 40-char commit SHA/);
} finally {
  rmSync(mutableFlow, {recursive: true, force: true});
}

// A pinned flow-style action is accepted and counted as an immutable reference.
const pinnedFlow = initRepo(
  'hache-p2-pinned-flow-',
  `name: pinned-flow\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - { uses: actions/checkout@${checkoutSha} }\n`,
);
try {
  commitFixture(pinnedFlow, 'pinned flow action');
  const result = verifyFixture(pinnedFlow);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /references=1/);
} finally {
  rmSync(pinnedFlow, {recursive: true, force: true});
}

// An action input named `image` is not a container declaration and must not be digest-checked.
const imageInput = initRepo(
  'hache-p2-image-input-',
  `name: image-input\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@${checkoutSha}\n        with: { image: ./docs/logo.png }\n      - run: |\n          echo 'image: not-a-container'\n          echo 'uses: actions/example@v1'\n`,
);
try {
  commitFixture(imageInput, 'non-container image input');
  const result = verifyFixture(imageInput);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /references=1/);
} finally {
  rmSync(imageInput, {recursive: true, force: true});
}

// Whole flow-style job mappings are rejected fail-closed because nested container/service
// declarations cannot be proved complete by the conservative parser.
const flowJob = initRepo(
  'hache-p2-flow-job-',
  `name: flow-job\non: [push]\njobs:\n  test: { runs-on: ubuntu-latest, steps: [ { uses: actions/checkout@${checkoutSha} } ] }\n`,
);
try {
  commitFixture(flowJob, 'unsupported flow job');
  const result = verifyFixture(flowJob);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /flow-style job mappings are unsupported/);
} finally {
  rmSync(flowJob, {recursive: true, force: true});
}

console.log('P2_SUPPLY_CHAIN_EVIDENCE_OK');
