import {validateRumSample} from './web-vitals-rum.mjs';

const TARGETS = Object.freeze({
  LCP: 2500,
  INP: 200,
  CLS: 0.1,
});

function aggregateError(code) {
  throw new TypeError(`RUM_AGGREGATION_ERROR ${code}`);
}

export function nearestRankPercentile(values, percentile = 0.75) {
  if (!Array.isArray(values) || values.length === 0) {
    aggregateError('values_must_be_nonempty_array');
  }
  if (typeof percentile !== 'number' || !Number.isFinite(percentile) || percentile <= 0 || percentile > 1) {
    aggregateError('percentile_must_be_gt_0_lte_1');
  }
  const normalized = values.map((value) => {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
      aggregateError('values_must_be_nonnegative_finite');
    }
    return value;
  }).sort((left, right) => left - right);

  const index = Math.max(0, Math.ceil(percentile * normalized.length) - 1);
  return normalized[index];
}

function validateWindowLabel(value) {
  if (typeof value !== 'string' || value.trim() === '' || value.length > 120 || /[\r\n]/.test(value)) {
    aggregateError('window_label_must_be_nonempty_single_line');
  }
  return value.trim();
}

function validateMinimumSampleCount(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (!Number.isInteger(value) || value < 1) {
    aggregateError('minimum_sample_count_must_be_positive_integer_or_null');
  }
  return value;
}

export function summarizeP75(samples, {
  windowLabel,
  minimumSampleCount = null,
} = {}) {
  if (!Array.isArray(samples)) {
    aggregateError('samples_must_be_array');
  }

  const window = validateWindowLabel(windowLabel);
  const sampleFloor = validateMinimumSampleCount(minimumSampleCount);
  const groups = new Map();

  for (const raw of samples) {
    const sample = validateRumSample(raw);
    const key = [
      sample.metric,
      sample.route_group,
      sample.build_id,
      sample.form_factor,
    ].join('\u0000');

    if (!groups.has(key)) {
      groups.set(key, {
        metric: sample.metric,
        route_group: sample.route_group,
        build_id: sample.build_id,
        form_factor: sample.form_factor,
        values: [],
      });
    }
    groups.get(key).values.push(sample.value);
  }

  const summaries = [...groups.values()].map((group) => {
    const p75 = nearestRankPercentile(group.values, 0.75);
    return {
      metric: group.metric,
      route_group: group.route_group,
      build_id: group.build_id,
      form_factor: group.form_factor,
      sample_count: group.values.length,
      p75,
      target_max: TARGETS[group.metric],
      within_target: p75 <= TARGETS[group.metric],
      meets_project_sample_floor: sampleFloor === null ? null : group.values.length >= sampleFloor,
    };
  }).sort((left, right) => (
    left.route_group.localeCompare(right.route_group)
    || left.form_factor.localeCompare(right.form_factor)
    || left.metric.localeCompare(right.metric)
    || left.build_id.localeCompare(right.build_id)
  ));

  return {
    schema_version: 1,
    window,
    percentile_method: 'nearest-rank',
    minimum_sample_count: sampleFloor,
    production_readiness_state: 'NOT EVALUATED',
    decision: 'HUMAN_REVIEW_REQUIRED',
    note: 'Targets and sample-floor calculations are evidence only; PERF-001 requires project-level field coverage, documented sufficiency, and human review.',
    groups: summaries,
  };
}
