const ALLOWED_METRICS = new Set(['LCP', 'INP', 'CLS']);
const ALLOWED_FORM_FACTORS = new Set(['mobile', 'desktop']);
const SAFE_LABEL = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const ALLOWED_SAMPLE_KEYS = new Set([
  'schema_version',
  'metric',
  'value',
  'route_group',
  'build_id',
  'form_factor',
]);

function configError(code) {
  throw new TypeError(`RUM_CONFIG_ERROR ${code}`);
}

function normalizeLabel(value, field) {
  if (typeof value !== 'string' || !SAFE_LABEL.test(value)) {
    configError(`${field}_must_be_low_cardinality_label`);
  }
  return value;
}

function normalizeEndpoint(endpoint) {
  if (typeof endpoint !== 'string'
      || endpoint.length < 2
      || endpoint.length > 160
      || !endpoint.startsWith('/')
      || endpoint.startsWith('//')
      || endpoint.includes('?')
      || endpoint.includes('#')
      || endpoint.includes('://')
      || endpoint.includes('\\')
      || /[\u0000-\u0020\u007f]/.test(endpoint)) {
    configError('endpoint_must_be_same_origin_path_without_query_or_fragment');
  }
  return endpoint;
}

function normalizeSampleRate(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) {
    configError('sample_rate_must_be_between_0_and_1');
  }
  return value;
}

function normalizeValue(metricName, value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    configError(`metric_value_must_be_nonnegative_finite=${metricName}`);
  }
  if (metricName === 'CLS') {
    return Math.round(value * 10000) / 10000;
  }
  return Math.round(value);
}

export function coarseFormFactor(viewportWidth, breakpoint = 768) {
  if (typeof viewportWidth !== 'number' || !Number.isFinite(viewportWidth) || viewportWidth <= 0) {
    configError('viewport_width_must_be_positive_finite');
  }
  if (typeof breakpoint !== 'number' || !Number.isFinite(breakpoint) || breakpoint <= 0) {
    configError('breakpoint_must_be_positive_finite');
  }
  return viewportWidth < breakpoint ? 'mobile' : 'desktop';
}

export function createRumPayload(metric, context) {
  if (!metric || typeof metric !== 'object') {
    configError('metric_must_be_object');
  }
  const metricName = typeof metric.name === 'string' ? metric.name.toUpperCase() : '';
  if (!ALLOWED_METRICS.has(metricName)) {
    configError(`unsupported_metric=${metricName || 'missing'}`);
  }
  if (!context || typeof context !== 'object') {
    configError('context_must_be_object');
  }

  const formFactor = normalizeLabel(context.formFactor, 'form_factor');
  if (!ALLOWED_FORM_FACTORS.has(formFactor)) {
    configError('form_factor_must_be_mobile_or_desktop');
  }

  return {
    schema_version: 1,
    metric: metricName,
    value: normalizeValue(metricName, metric.value),
    route_group: normalizeLabel(context.routeGroup, 'route_group'),
    build_id: normalizeLabel(context.buildId, 'build_id'),
    form_factor: formFactor,
  };
}

export function validateRumSample(sample) {
  if (!sample || typeof sample !== 'object' || Array.isArray(sample)) {
    configError('sample_must_be_object');
  }
  for (const key of Object.keys(sample)) {
    if (!ALLOWED_SAMPLE_KEYS.has(key)) {
      configError(`unknown_sample_field=${key}`);
    }
  }
  if (sample.schema_version !== 1) {
    configError('sample_schema_version_must_be_1');
  }
  return createRumPayload(
    {name: sample.metric, value: sample.value},
    {
      routeGroup: sample.route_group,
      buildId: sample.build_id,
      formFactor: sample.form_factor,
    },
  );
}

export function createFetchTransport({fetchImpl = globalThis.fetch} = {}) {
  if (typeof fetchImpl !== 'function') {
    configError('fetch_transport_requires_fetch');
  }
  return async function send(endpoint, payload) {
    const target = normalizeEndpoint(endpoint);
    try {
      const response = await fetchImpl(target, {
        method: 'POST',
        mode: 'same-origin',
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
        keepalive: true,
        headers: {'content-type': 'application/json'},
        body: JSON.stringify(payload),
      });
      return response?.ok === true;
    } catch {
      return false;
    }
  };
}

export function createRumReporter({
  endpoint = '/__rum/web-vitals',
  routeGroup,
  buildId,
  formFactor,
  sampleRate = 0.1,
  shouldCollect = () => false,
  random = Math.random,
  transport = createFetchTransport(),
} = {}) {
  const target = normalizeEndpoint(endpoint);
  const route = normalizeLabel(routeGroup, 'route_group');
  const build = normalizeLabel(buildId, 'build_id');
  const rate = normalizeSampleRate(sampleRate);

  if (typeof shouldCollect !== 'function') {
    configError('should_collect_must_be_function');
  }
  if (typeof random !== 'function') {
    configError('random_must_be_function');
  }
  if (typeof transport !== 'function') {
    configError('transport_must_be_function');
  }
  if (!(typeof formFactor === 'function' || typeof formFactor === 'string')) {
    configError('form_factor_must_be_string_or_function');
  }
  if (typeof formFactor === 'string') {
    const normalized = normalizeLabel(formFactor, 'form_factor');
    if (!ALLOWED_FORM_FACTORS.has(normalized)) {
      configError('form_factor_must_be_mobile_or_desktop');
    }
  }

  return async function report(metric) {
    try {
      if (shouldCollect() !== true) {
        return {status: 'disabled'};
      }
      const draw = random();
      if (typeof draw !== 'number' || !Number.isFinite(draw) || draw < 0 || draw >= 1) {
        return {status: 'dropped_invalid_sampler'};
      }
      if (draw >= rate) {
        return {status: 'sampled_out'};
      }

      const resolvedFormFactor = typeof formFactor === 'function' ? formFactor() : formFactor;
      const payload = createRumPayload(metric, {
        routeGroup: route,
        buildId: build,
        formFactor: resolvedFormFactor,
      });
      const sent = await transport(target, payload);
      return {status: sent ? 'sent' : 'transport_error'};
    } catch {
      return {status: 'dropped_runtime_error'};
    }
  };
}

export function wireWebVitals(provider, reporter) {
  if (!provider || typeof provider !== 'object') {
    configError('provider_must_be_object');
  }
  if (typeof reporter !== 'function') {
    configError('reporter_must_be_function');
  }

  const hooks = [
    ['onLCP', 'LCP'],
    ['onINP', 'INP'],
    ['onCLS', 'CLS'],
  ];

  for (const [hook, metricName] of hooks) {
    if (typeof provider[hook] !== 'function') {
      configError(`provider_missing_${hook}`);
    }
    provider[hook]((metric) => {
      const value = metric && typeof metric === 'object' ? metric.value : undefined;
      try {
        void Promise.resolve(reporter({name: metricName, value})).catch(() => {});
      } catch {
        // Telemetry must never break the project CUF.
      }
    }, {reportAllChanges: false});
  }
}
