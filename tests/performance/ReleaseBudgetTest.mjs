import assert from 'node:assert/strict';
import {promises as fs} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const tool = path.join(root, 'tools/performance/release-budget.mjs');
const templateMd = await fs.readFile(path.join(root, 'templates/PERFORMANCE-BUDGET.md'), 'utf8');
const thirdPartyMd = await fs.readFile(path.join(root, 'templates/THIRD-PARTY-INVENTORY.md'), 'utf8');
const exampleConfig = JSON.parse(await fs.readFile(path.join(root, 'templates/performance-budget.example.json'), 'utf8'));

for (const fragment of [
  'P1-11 / PERF-004',
  'Imagen individual máxima',
  'Fuente individual máxima',
  'Transferencia de terceros',
  'Requests de terceros',
  'release-budget.mjs',
  'WITHIN_CONFIGURED_BUDGETS',
  'no equivale a Production Ready',
  'Subir un límite es un cambio de política',
]) {
  assert(templateMd.includes(fragment), `missing PERFORMANCE-BUDGET fragment: ${fragment}`);
}
for (const fragment of [
  'P1-11 budget key/origen',
  'No reclasificar un origen como first-party únicamente para ocultarlo de un budget P1-11',
]) {
  assert(thirdPartyMd.includes(fragment), `missing THIRD-PARTY fragment: ${fragment}`);
}
assert.equal(exampleConfig.schema_version, 1);
assert.equal(exampleConfig.release.image_bytes, null);
assert.equal(exampleConfig.release.font_bytes, null);
assert.equal(exampleConfig.network.third_party_transfer_bytes, null);
assert.equal(exampleConfig.network.third_party_requests, null);
assert.deepEqual(exampleConfig.network.per_origin, {});

const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'hache-release-budget-'));
try {
  const releaseDir = path.join(tmp, 'release');
  const lhrDir = path.join(tmp, 'lighthouse');
  await fs.mkdir(releaseDir, {recursive: true});
  await fs.mkdir(lhrDir, {recursive: true});

  const writeSized = async (name, bytes) => {
    await fs.mkdir(path.dirname(path.join(releaseDir, name)), {recursive: true});
    await fs.writeFile(path.join(releaseDir, name), Buffer.alloc(bytes, 0x61));
  };
  await writeSized('assets/app.js', 100);
  await writeSized('assets/site.css', 50);
  await writeSized('assets/hero.webp', 200);
  await writeSized('assets/body.woff2', 80);
  await writeSized('index.html', 60);

  const networkItems = [
    {url: 'https://app.example.test/assets/app.js', transferSize: 100, resourceType: 'Script'},
    {url: 'https://app.example.test/assets/site.css', transferSize: 45, resourceType: 'Stylesheet'},
    {url: 'https://app.example.test/assets/hero.webp', transferSize: 180, resourceType: 'Image'},
    {url: 'https://app.example.test/assets/body.woff2', transferSize: 70, resourceType: 'Font'},
    {url: 'https://cdn.example.test/brand.woff2', transferSize: 20, resourceType: 'Font'},
    {url: 'https://analytics.example.test/sdk.js', transferSize: 40, resourceType: 'Script'},
    {url: 'https://analytics.example.test/pixel.gif', transferSize: 10, resourceType: 'Image'},
  ];

  const makeLhr = (finalUrl) => ({
    finalUrl,
    audits: {
      'network-requests': {
        details: {items: networkItems},
      },
    },
  });
  await fs.writeFile(path.join(lhrDir, 'run-1.json'), JSON.stringify(makeLhr('https://app.example.test/index.html')));
  await fs.writeFile(path.join(lhrDir, 'run-2.json'), JSON.stringify(makeLhr('https://app.example.test/other.html')));
  await fs.writeFile(path.join(lhrDir, 'not-lhr.json'), JSON.stringify({hello: 'world'}));

  const baseConfig = {
    schema_version: 1,
    project: 'release-budget-fixture',
    baseline: {
      reference: 'fixture-baseline-1',
      justification: 'Fixture limits are set just above measured release/network values.',
      owner: 'test-owner',
      reviewed_at: '2026-09-05',
    },
    first_party_origins: ['https://cdn.example.test'],
    release: {
      total_bytes: 500,
      javascript_bytes: 120,
      css_bytes: 60,
      image_bytes: 220,
      font_bytes: 100,
      other_bytes: 70,
      max_image_bytes: 210,
      max_font_bytes: 90,
    },
    network: {
      total_transfer_bytes: 500,
      javascript_transfer_bytes: 160,
      css_transfer_bytes: 60,
      image_transfer_bytes: 210,
      font_transfer_bytes: 100,
      third_party_transfer_bytes: 60,
      third_party_requests: 2,
      per_origin: {
        'https://analytics.example.test': {
          transfer_bytes: 60,
          requests: 2,
        },
      },
    },
  };

  const configPath = path.join(tmp, 'budget.json');
  const reportPath = path.join(tmp, 'budget-report.json');
  const writeConfig = async (config) => fs.writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`);
  const run = (extra = []) => spawnSync(process.execPath, [
    tool,
    '--config', configPath,
    '--root', releaseDir,
    ...extra,
  ], {encoding: 'utf8'});

  await writeConfig(baseConfig);
  let result = run(['--lighthouse-dir', lhrDir, '--json', reportPath]);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /RELEASE_BUDGET_OK/);
  const report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
  assert.equal(report.decision, 'WITHIN_CONFIGURED_BUDGETS');
  assert.equal(report.release.totals.total, 490);
  assert.equal(report.release.totals.images, 200);
  assert.equal(report.release.totals.fonts, 80);
  assert.equal(report.lighthouse.length, 2);
  // Each Lighthouse run is evaluated independently, not summed across repetitions.
  assert.equal(report.lighthouse[0].totals.third_party_transfer_bytes, 50);
  assert.equal(report.lighthouse[0].totals.third_party_requests, 2);
  assert.equal(report.lighthouse[0].per_origin['https://analytics.example.test'].transfer_bytes, 50);
  assert.equal(report.lighthouse[0].per_origin['https://cdn.example.test'], undefined);

  const imageTotalFail = structuredClone(baseConfig);
  imageTotalFail.release.image_bytes = 199;
  await writeConfig(imageTotalFail);
  result = run(['--lighthouse-dir', lhrDir]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /dimension=image_bytes actual=200 limit=199/);

  const imageFileFail = structuredClone(baseConfig);
  imageFileFail.release.max_image_bytes = 199;
  await writeConfig(imageFileFail);
  result = run(['--lighthouse-dir', lhrDir]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /scope=release-file dimension=max_image_bytes actual=200 limit=199/);
  assert.match(result.stderr, /hero\.webp/);

  const fontFileFail = structuredClone(baseConfig);
  fontFileFail.release.max_font_bytes = 79;
  await writeConfig(fontFileFail);
  result = run(['--lighthouse-dir', lhrDir]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /scope=release-file dimension=max_font_bytes actual=80 limit=79/);
  assert.match(result.stderr, /body\.woff2/);

  const thirdPartyFail = structuredClone(baseConfig);
  thirdPartyFail.network.third_party_transfer_bytes = 49;
  await writeConfig(thirdPartyFail);
  result = run(['--lighthouse-dir', lhrDir]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /dimension=third_party_transfer_bytes actual=50 limit=49/);

  const thirdPartyRequestFail = structuredClone(baseConfig);
  thirdPartyRequestFail.network.third_party_requests = 1;
  await writeConfig(thirdPartyRequestFail);
  result = run(['--lighthouse-dir', lhrDir]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /dimension=third_party_requests actual=2 limit=1/);

  const perOriginFail = structuredClone(baseConfig);
  perOriginFail.network.per_origin['https://analytics.example.test'].requests = 1;
  await writeConfig(perOriginFail);
  result = run(['--lighthouse-dir', lhrDir]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /scope=network-origin:run-1\.json dimension=requests actual=2 limit=1/);

  await writeConfig(baseConfig);
  result = run();
  assert.equal(result.status, 2);
  assert.match(result.stderr, /network_budgets_require_lighthouse_dir/);

  const releaseOnly = structuredClone(baseConfig);
  releaseOnly.network = {};
  await writeConfig(releaseOnly);
  result = run();
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);

  const missingJustification = structuredClone(releaseOnly);
  missingJustification.baseline.justification = '';
  await writeConfig(missingJustification);
  result = run();
  assert.equal(result.status, 2);
  assert.match(result.stderr, /invalid_string=baseline\.justification/);

  const invalidDate = structuredClone(releaseOnly);
  invalidDate.baseline.reviewed_at = '2026-02-31';
  await writeConfig(invalidDate);
  result = run();
  assert.equal(result.status, 2);
  assert.match(result.stderr, /invalid_date=baseline\.reviewed_at/);

  const noBudget = structuredClone(releaseOnly);
  noBudget.release = {};
  await writeConfig(noBudget);
  result = run();
  assert.equal(result.status, 2);
  assert.match(result.stderr, /no_budgets_configured/);

  if (process.platform !== 'win32') {
    const outside = path.join(tmp, 'outside.bin');
    await fs.writeFile(outside, Buffer.alloc(10));
    await fs.symlink(outside, path.join(releaseDir, 'escape.bin'));
    await writeConfig(releaseOnly);
    result = run();
    assert.equal(result.status, 2);
    assert.match(result.stderr, /release_symlink_not_supported=escape\.bin/);
    await fs.unlink(path.join(releaseDir, 'escape.bin'));
  }

  console.log('RELEASE_BUDGET_TEST_OK');
} finally {
  await fs.rm(tmp, {recursive: true, force: true});
}
