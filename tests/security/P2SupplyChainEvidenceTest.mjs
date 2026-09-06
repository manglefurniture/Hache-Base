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
  run('git', ['add', '.'], fixture);
  run('git', ['commit', '-m', 'fixture'], fixture);
  const commit = run('git', ['rev-parse', 'HEAD'], fixture).trim();

  const artifact = Buffer.from('artifact-bytes');
  const artifactSha = createHash('sha256').update(artifact).digest('hex');
  writeFileSync(join(fixture, 'artifact.tar.gz'), artifact);
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
  writeFileSync(join(fixture, 'artifact.manifest.json'), JSON.stringify(manifest));

  const output = join(fixture, 'evidence');
  const generation = run('node', [
    tool,
    'generate',
    '--root', fixture,
    '--artifact-manifest', join(fixture, 'artifact.manifest.json'),
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
  assert.ok(provenance.materials.some((item) => item.reference === `actions/checkout@${checkoutSha}`));
  assert.ok(provenance.materials.some((item) => item.reference.includes(`@sha256:${imageDigest}`)));
  assert.match(provenance.sbom.sha256, /^[0-9a-f]{64}$/);
} finally {
  rmSync(fixture, {recursive: true, force: true});
}

// A mutable tag is rejected; absence of pinning cannot silently become evidence.
const mutable = initRepo('hache-p2-mutable-', 'name: bad\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n');
try {
  run('git', ['add', '.'], mutable);
  run('git', ['commit', '-m', 'mutable'], mutable);
  const result = spawnSync('node', [tool, 'verify-workflows', mutable], {encoding: 'utf8'});
  assert.equal(result.status, 1);
  assert.match(result.stderr, /external action must use a full 40-char commit SHA/);
} finally {
  rmSync(mutable, {recursive: true, force: true});
}

console.log('P2_SUPPLY_CHAIN_EVIDENCE_OK');
