import assert from 'node:assert/strict';
import {
  nearestRankPercentile,
  summarizeP75,
} from '../../integrations/rum/field-p75.mjs';

assert.equal(nearestRankPercentile([4, 1, 2, 3], 0.75), 3);
assert.equal(nearestRankPercentile([0.01, 0.02, 0.03, 0.04], 0.75), 0.03);
assert.throws(() => nearestRankPercentile([], 0.75), /values_must_be_nonempty_array/);

const sample = (metric, value, formFactor = 'mobile', buildId = 'build-1') => ({
  schema_version: 1,
  metric,
  value,
  route_group: 'registration',
  build_id: buildId,
  form_factor: formFactor,
});

const samples = [
  sample('LCP', 1000),
  sample('LCP', 1800),
  sample('LCP', 2500),
  sample('LCP', 3100),
  sample('INP', 100),
  sample('INP', 180),
  sample('INP', 220),
  sample('INP', 300),
  sample('CLS', 0.01, 'desktop'),
  sample('CLS', 0.02, 'desktop'),
  sample('CLS', 0.03, 'desktop'),
  sample('CLS', 0.2, 'desktop'),
];

const report = summarizeP75(samples, {
  windowLabel: '2026-09-01..2026-09-07',
  minimumSampleCount: 4,
});

assert.equal(report.schema_version, 1);
assert.equal(report.percentile_method, 'nearest-rank');
assert.equal(report.minimum_sample_count, 4);
assert.equal(report.production_readiness_state, 'NOT EVALUATED');
assert.equal(report.decision, 'HUMAN_REVIEW_REQUIRED');
assert.equal('samples' in report, false);
assert.equal(report.groups.length, 3);

const lcp = report.groups.find((group) => group.metric === 'LCP');
assert.equal(lcp.p75, 2500);
assert.equal(lcp.target_max, 2500);
assert.equal(lcp.within_target, true);
assert.equal(lcp.meets_project_sample_floor, true);

const inp = report.groups.find((group) => group.metric === 'INP');
assert.equal(inp.p75, 220);
assert.equal(inp.target_max, 200);
assert.equal(inp.within_target, false);

const cls = report.groups.find((group) => group.metric === 'CLS');
assert.equal(cls.form_factor, 'desktop');
assert.equal(cls.p75, 0.03);
assert.equal(cls.target_max, 0.1);
assert.equal(cls.within_target, true);

const noUniversalFloor = summarizeP75([sample('LCP', 1000)], {
  windowLabel: 'pilot-window',
});
assert.equal(noUniversalFloor.minimum_sample_count, null);
assert.equal(noUniversalFloor.groups[0].meets_project_sample_floor, null);
assert.equal(noUniversalFloor.production_readiness_state, 'NOT EVALUATED');

const justOver = summarizeP75([
  sample('LCP', 2500.4),
  sample('INP', 200.4),
  sample('CLS', 0.10004),
], {
  windowLabel: 'precision-boundary',
  minimumSampleCount: 1,
});
const justOverByMetric = new Map(justOver.groups.map((group) => [group.metric, group]));
assert.equal(justOverByMetric.get('LCP').p75, 2500.4);
assert.equal(justOverByMetric.get('LCP').within_target, false);
assert.equal(justOverByMetric.get('INP').p75, 200.4);
assert.equal(justOverByMetric.get('INP').within_target, false);
assert.equal(justOverByMetric.get('CLS').p75, 0.10004);
assert.equal(justOverByMetric.get('CLS').within_target, false);

assert.throws(
  () => summarizeP75([{...sample('LCP', 1000), user_id: '42'}], {windowLabel: 'bad'}),
  /unknown_sample_field=user_id/,
);
assert.throws(
  () => summarizeP75([sample('TTFB', 100)], {windowLabel: 'bad'}),
  /unsupported_metric=TTFB/,
);
assert.throws(
  () => summarizeP75([sample('LCP', 1000)], {windowLabel: 'bad', minimumSampleCount: 0}),
  /minimum_sample_count_must_be_positive_integer_or_null/,
);

console.log('RUM_FIELD_P75_OK');
