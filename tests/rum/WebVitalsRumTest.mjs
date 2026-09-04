import assert from 'node:assert/strict';
import {
  coarseFormFactor,
  createFetchTransport,
  createRumPayload,
  createRumReporter,
  validateRumSample,
  wireWebVitals,
} from '../../integrations/rum/web-vitals-rum.mjs';

assert.equal(coarseFormFactor(390), 'mobile');
assert.equal(coarseFormFactor(1440), 'desktop');
assert.throws(() => coarseFormFactor(0), /viewport_width_must_be_positive_finite/);

const payload = createRumPayload(
  {
    name: 'lcp',
    value: 1834.6,
    id: 'provider-session-like-id',
    url: 'https://example.test/account?email=user@example.test',
  },
  {
    routeGroup: 'registration',
    buildId: '20260904.1',
    formFactor: 'mobile',
  },
);

assert.deepEqual(payload, {
  schema_version: 1,
  metric: 'LCP',
  value: 1835,
  route_group: 'registration',
  build_id: '20260904.1',
  form_factor: 'mobile',
});
assert.equal('id' in payload, false);
assert.equal('url' in payload, false);

assert.deepEqual(validateRumSample(payload), payload);
assert.throws(
  () => validateRumSample({...payload, referrer: 'https://example.test/private'}),
  /unknown_sample_field=referrer/,
);
assert.throws(
  () => createRumPayload(
    {name: 'CLS', value: 0.123456},
    {routeGroup: '/user/123', buildId: 'build', formFactor: 'mobile'},
  ),
  /route_group_must_be_low_cardinality_label/,
);

let fetchCall;
const fetchTransport = createFetchTransport({
  fetchImpl: async (url, options) => {
    fetchCall = {url, options};
    return {ok: true};
  },
});
assert.equal(await fetchTransport('/__rum/web-vitals', payload), true);
assert.equal(fetchCall.url, '/__rum/web-vitals');
assert.equal(fetchCall.options.method, 'POST');
assert.equal(fetchCall.options.mode, 'same-origin');
assert.equal(fetchCall.options.credentials, 'omit');
assert.equal(fetchCall.options.referrerPolicy, 'no-referrer');
assert.equal(fetchCall.options.cache, 'no-store');
assert.equal(fetchCall.options.redirect, 'error');
assert.equal(fetchCall.options.keepalive, true);
assert.deepEqual(JSON.parse(fetchCall.options.body), payload);
assert.throws(
  () => createRumReporter({
    endpoint: 'https://collector.example/rum',
    routeGroup: 'home',
    buildId: 'build',
    formFactor: 'desktop',
  }),
  /endpoint_must_be_same_origin_path_without_query_or_fragment/,
);
assert.throws(
  () => createRumReporter({
    endpoint: '/\\evil.example/rum',
    routeGroup: 'home',
    buildId: 'build',
    formFactor: 'desktop',
  }),
  /endpoint_must_be_same_origin_path_without_query_or_fragment/,
);
assert.throws(
  () => createRumReporter({
    endpoint: '/rum path',
    routeGroup: 'home',
    buildId: 'build',
    formFactor: 'desktop',
  }),
  /endpoint_must_be_same_origin_path_without_query_or_fragment/,
);
const failedFetchTransport = createFetchTransport({
  fetchImpl: async () => ({ok: false}),
});
assert.equal(await failedFetchTransport('/__rum/web-vitals', payload), false);

let sendCount = 0;
const disabledReporter = createRumReporter({
  routeGroup: 'home',
  buildId: 'build',
  formFactor: 'desktop',
  transport: async () => {
    sendCount++;
    return true;
  },
});
assert.deepEqual(await disabledReporter({name: 'CLS', value: 0.02}), {status: 'disabled'});
assert.equal(sendCount, 0);

const sampledOutReporter = createRumReporter({
  routeGroup: 'home',
  buildId: 'build',
  formFactor: 'desktop',
  sampleRate: 0.25,
  shouldCollect: () => true,
  random: () => 0.9,
  transport: async () => {
    sendCount++;
    return true;
  },
});
assert.deepEqual(await sampledOutReporter({name: 'INP', value: 100}), {status: 'sampled_out'});
assert.equal(sendCount, 0);

let sentPayload;
const enabledReporter = createRumReporter({
  endpoint: '/rum',
  routeGroup: 'checkout',
  buildId: 'abc123',
  formFactor: () => 'mobile',
  sampleRate: 1,
  shouldCollect: () => true,
  random: () => 0,
  transport: async (endpoint, body) => {
    assert.equal(endpoint, '/rum');
    sentPayload = body;
    return true;
  },
});
assert.deepEqual(
  await enabledReporter({name: 'INP', value: 199.7, id: 'drop-me', navigationType: 'navigate'}),
  {status: 'sent'},
);
assert.deepEqual(sentPayload, {
  schema_version: 1,
  metric: 'INP',
  value: 200,
  route_group: 'checkout',
  build_id: 'abc123',
  form_factor: 'mobile',
});

const safeFailureReporter = createRumReporter({
  routeGroup: 'home',
  buildId: 'build',
  formFactor: () => {
    throw new Error('project callback failed');
  },
  sampleRate: 1,
  shouldCollect: () => true,
  random: () => 0,
  transport: async () => {
    throw new Error('network failed');
  },
});
assert.deepEqual(
  await safeFailureReporter({name: 'LCP', value: 1000}),
  {status: 'dropped_runtime_error'},
);

const callbacks = {};
const provider = {
  onLCP(callback, options) {
    assert.deepEqual(options, {reportAllChanges: false});
    callbacks.LCP = callback;
  },
  onINP(callback) {
    callbacks.INP = callback;
  },
  onCLS(callback) {
    callbacks.CLS = callback;
  },
};
const wired = [];
wireWebVitals(provider, async (metric) => {
  wired.push(metric);
});
callbacks.LCP({name: 'LCP', value: 1111, id: 'ignored'});
callbacks.INP({name: 'INP', value: 123});
callbacks.CLS({name: 'CLS', value: 0.01});
await new Promise((resolve) => setTimeout(resolve, 0));
assert.deepEqual(wired, [
  {name: 'LCP', value: 1111},
  {name: 'INP', value: 123},
  {name: 'CLS', value: 0.01},
]);

assert.throws(
  () => wireWebVitals({onLCP() {}, onCLS() {}}, async () => {}),
  /provider_missing_onINP/,
);

console.log('WEB_VITALS_RUM_OK');
