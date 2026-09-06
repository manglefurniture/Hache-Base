import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateAlertPolicy } from '../../tools/observability/validate-alert-policy.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const example = JSON.parse(
  await fs.readFile(path.join(root, 'templates/alert-policy.example.json'), 'utf8'),
);

assert.deepEqual(validateAlertPolicy(structuredClone(example)), example);
assert.equal(example.alerts.length, 2);

function expectInvalid(mutator, expectedFragment) {
  const candidate = structuredClone(example);
  mutator(candidate);
  assert.throws(
    () => validateAlertPolicy(candidate),
    (error) => error instanceof Error
      && error.message.startsWith('ALERT_POLICY_INVALID:')
      && error.message.includes(expectedFragment),
  );
}

expectInvalid((policy) => { policy.schema_version = 2; }, 'schema_version');
expectInvalid((policy) => { policy.alerts = []; }, 'at least one');
expectInvalid((policy) => { policy.alerts[1].id = policy.alerts[0].id; }, 'duplicates');
expectInvalid((policy) => { policy.alerts[0].signal = 'mystery'; }, 'signal');
expectInvalid((policy) => { policy.alerts[0].metric = '/users/42?email=x@example.com'; }, 'stable metric name');
expectInvalid((policy) => { policy.alerts[0].threshold = Number.POSITIVE_INFINITY; }, 'finite number');
expectInvalid((policy) => { policy.alerts[0].window_seconds = 0; }, 'positive integer');
expectInvalid((policy) => { policy.alerts[0].for_seconds = policy.alerts[0].window_seconds + 1; }, 'cannot exceed');
expectInvalid((policy) => { policy.alerts[0].owner = ' '; }, 'owner');
expectInvalid((policy) => { policy.alerts[0].runbook = ''; }, 'runbook');
expectInvalid((policy) => { policy.alerts[0].runbook = 'javascript:alert(1)'; }, 'unsafe');
expectInvalid((policy) => { policy.alerts[0].runbook = 'JaVaScRiPt:alert(1)'; }, 'unsafe');
expectInvalid((policy) => { policy.alerts[0].action = ''; }, 'action');
expectInvalid((policy) => { policy.alerts[0].data_source = ''; }, 'data_source');
expectInvalid((policy) => { policy.reviewed_at = '2026-99-99'; }, 'valid YYYY-MM-DD');
expectInvalid((policy) => { policy.reviewed_at = '2026-02-31'; }, 'valid YYYY-MM-DD');

const allowedSignals = new Set(example.alerts.map((alert) => alert.signal));
assert(allowedSignals.has('latency'));
assert(allowedSignals.has('cuf_failure'));

const template = await fs.readFile(path.join(root, 'templates/ALERTING-RUNBOOKS.md'), 'utf8');
for (const required of [
  'latency',
  'traffic',
  'errors',
  'saturation',
  'cuf_success',
  'cuf_failure',
  'cuf_pending',
  'threshold',
  'ventana',
  'Owner',
  'runbook',
  'Control de ruido',
  'NOT EVALUATED',
]) {
  assert(template.includes(required), `missing template contract: ${required}`);
}

console.log('ALERT_POLICY_TEST_OK');
