import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const require = createRequire(import.meta.url);
const budgets = JSON.parse(fs.readFileSync(path.join(here, 'budgets.json'), 'utf8'));
const config = require(path.join(here, 'lighthouserc.cjs'));
const workflow = fs.readFileSync(path.join(root, '.github/workflows/ci.yml'), 'utf8');

const fail = (message) => {
  console.error(`P1_03_CONFIG_ERROR ${message}`);
  process.exit(1);
};

if (budgets.schema_version !== 1) fail('schema_version_must_be_1');
if (budgets.tool?.package !== '@lhci/cli' || budgets.tool?.version !== '0.15.1') {
  fail('lhci_tool_must_be_exactly_pinned');
}
if (budgets.profile?.name !== 'mobile-simulated') fail('profile_must_be_mobile_simulated');
if (!Number.isInteger(budgets.profile?.number_of_runs) || budgets.profile.number_of_runs < 2) {
  fail('number_of_runs_must_be_at_least_2');
}
if (!Array.isArray(budgets.urls) || budgets.urls.length < 2) fail('at_least_two_fixture_urls_required');
for (const url of budgets.urls) {
  if (typeof url !== 'string' || !url.startsWith('/') || url.includes('://')) fail(`fixture_url_must_be_local=${url}`);
}

const required = {
  'categories:accessibility': {level: 'error', property: 'minScore', value: 1},
  'categories:performance': {level: 'warn', property: 'minScore', value: 0.9},
  'largest-contentful-paint': {level: 'error', property: 'maxNumericValue', value: 2500},
  'cumulative-layout-shift': {level: 'error', property: 'maxNumericValue', value: 0.1},
  'total-blocking-time': {level: 'error', property: 'maxNumericValue', value: 300},
};

for (const [name, expectation] of Object.entries(required)) {
  const budget = budgets.assertions?.[name];
  if (!budget) fail(`missing_assertion=${name}`);
  if (budget.level !== expectation.level) fail(`wrong_level=${name}`);
  if (budget[expectation.property] !== expectation.value) fail(`wrong_threshold=${name}`);
  if (!['median', 'median-run', 'pessimistic'].includes(budget.aggregationMethod)) {
    fail(`unsafe_aggregation=${name}`);
  }
}

const ci = config.ci;
if (!ci) fail('missing_ci_config');
if (ci.collect?.staticDistDir !== './tests/browser/fixture') fail('wrong_static_dist_dir');
if (ci.collect?.numberOfRuns !== budgets.profile.number_of_runs) fail('run_count_drift');
const expectedUrls = budgets.urls.map((pathname) => `http://localhost${pathname}`);
if (JSON.stringify(ci.collect?.url) !== JSON.stringify(expectedUrls)) fail('url_projection_drift');
if (JSON.stringify(ci.collect?.settings?.onlyCategories) !== JSON.stringify(['performance', 'accessibility'])) {
  fail('only_categories_must_be_performance_and_accessibility');
}
if (ci.collect?.settings?.chromeFlags !== '--disable-dev-shm-usage') fail('unexpected_chrome_flags');
if (ci.upload?.target !== 'filesystem' || ci.upload?.outputDir !== './artifacts/lighthouse') {
  fail('reports_must_remain_local_artifacts');
}

for (const [name, budget] of Object.entries(budgets.assertions)) {
  const generated = ci.assert?.assertions?.[name];
  if (!Array.isArray(generated) || generated[0] !== budget.level) fail(`assertion_projection_drift=${name}`);
}

const exactInstall = `npm install --global ${budgets.tool.package}@${budgets.tool.version}`;
if (!workflow.includes('browser_audit:')) fail('browser_audit_job_missing');
if (!workflow.includes('node-version: 22')) fail('node_22_pin_missing');
if (!workflow.includes(exactInstall)) fail('lhci_exact_install_missing');
if (!workflow.includes('lhci autorun --config=tests/browser/lighthouserc.cjs')) fail('lhci_autorun_missing');
if (!workflow.includes('actions/upload-artifact@v4')) fail('artifact_upload_missing');

console.log('P1_03_CONFIG_OK');
