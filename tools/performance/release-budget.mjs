#!/usr/bin/env node

import {promises as fs} from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import {fileURLToPath} from 'node:url';

const SCHEMA_VERSION = 1;
const DEFAULT_EXTENSIONS = Object.freeze({
  javascript: ['.js', '.mjs', '.cjs'],
  css: ['.css'],
  images: ['.png', '.jpg', '.jpeg', '.webp', '.avif', '.gif', '.svg', '.ico'],
  fonts: ['.woff', '.woff2', '.ttf', '.otf', '.eot'],
});

class ConfigError extends Error {}

function usage() {
  return [
    'Usage: node tools/performance/release-budget.mjs --config <json> --root <release-dir> [--lighthouse-dir <dir>] [--json <report.json>]',
    '',
    'Exit codes: 0=within configured budgets, 1=budget exceeded, 2=config/input error.',
  ].join('\n');
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }
    if (!['--config', '--root', '--lighthouse-dir', '--json'].includes(token)) {
      throw new ConfigError(`unknown_argument=${token}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new ConfigError(`missing_value=${token}`);
    }
    args[token.slice(2)] = value;
    index += 1;
  }
  return args;
}

function requireObject(value, field) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new ConfigError(`invalid_object=${field}`);
  }
  return value;
}

function requireString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new ConfigError(`invalid_string=${field}`);
  }
  return value.trim();
}

function rejectUnknownKeys(object, allowedKeys, field) {
  const allowed = new Set(allowedKeys);
  for (const key of Object.keys(object)) {
    if (!allowed.has(key)) {
      throw new ConfigError(`unknown_key=${field}.${key}`);
    }
  }
}

function optionalBudget(value, field) {
  if (value === undefined || value === null) return null;
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new ConfigError(`invalid_budget=${field}`);
  }
  return value;
}

function validateDate(value, field) {
  const text = requireString(value, field);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    throw new ConfigError(`invalid_date=${field}`);
  }
  const date = new Date(`${text}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== text) {
    throw new ConfigError(`invalid_date=${field}`);
  }
  return text;
}

function normalizeOrigin(value, field) {
  const text = requireString(value, field);
  let parsed;
  try {
    parsed = new URL(text);
  } catch {
    throw new ConfigError(`invalid_origin=${field}`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new ConfigError(`invalid_origin_scheme=${field}`);
  }
  if (parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new ConfigError(`origin_must_not_include_path=${field}`);
  }
  return parsed.origin;
}

function normalizeExtensions(rawConfig) {
  let config = rawConfig;
  if (config !== undefined) {
    config = requireObject(config, 'extensions');
    rejectUnknownKeys(config, Object.keys(DEFAULT_EXTENSIONS), 'extensions');
  }

  const result = {};
  const seen = new Map();
  for (const [category, defaults] of Object.entries(DEFAULT_EXTENSIONS)) {
    const supplied = config?.[category];
    const values = supplied === undefined ? defaults : supplied;
    if (!Array.isArray(values) || values.length === 0) {
      throw new ConfigError(`invalid_extensions=${category}`);
    }
    result[category] = values.map((value, index) => {
      let extension = requireString(value, `extensions.${category}[${index}]`).toLowerCase();
      if (!extension.startsWith('.')) extension = `.${extension}`;
      if (!/^\.[a-z0-9]+$/.test(extension)) {
        throw new ConfigError(`invalid_extension=${category}:${extension}`);
      }
      if (seen.has(extension)) {
        throw new ConfigError(`duplicate_extension=${extension}:${seen.get(extension)}:${category}`);
      }
      seen.set(extension, category);
      return extension;
    });
  }
  return result;
}

function validateConfig(raw) {
  const config = requireObject(raw, 'root');
  rejectUnknownKeys(
    config,
    ['schema_version', 'project', 'baseline', 'first_party_origins', 'release', 'network', 'extensions'],
    'root',
  );
  if (config.schema_version !== SCHEMA_VERSION) {
    throw new ConfigError(`unsupported_schema_version=${config.schema_version}`);
  }
  const project = requireString(config.project, 'project');
  const baseline = requireObject(config.baseline, 'baseline');
  rejectUnknownKeys(baseline, ['reference', 'justification', 'owner', 'reviewed_at'], 'baseline');
  const baselineMeta = {
    reference: requireString(baseline.reference, 'baseline.reference'),
    justification: requireString(baseline.justification, 'baseline.justification'),
    owner: requireString(baseline.owner, 'baseline.owner'),
    reviewed_at: validateDate(baseline.reviewed_at, 'baseline.reviewed_at'),
  };

  const releaseRaw = requireObject(config.release ?? {}, 'release');
  rejectUnknownKeys(
    releaseRaw,
    ['total_bytes', 'javascript_bytes', 'css_bytes', 'image_bytes', 'font_bytes', 'other_bytes', 'max_image_bytes', 'max_font_bytes'],
    'release',
  );
  const release = {
    total_bytes: optionalBudget(releaseRaw.total_bytes, 'release.total_bytes'),
    javascript_bytes: optionalBudget(releaseRaw.javascript_bytes, 'release.javascript_bytes'),
    css_bytes: optionalBudget(releaseRaw.css_bytes, 'release.css_bytes'),
    image_bytes: optionalBudget(releaseRaw.image_bytes, 'release.image_bytes'),
    font_bytes: optionalBudget(releaseRaw.font_bytes, 'release.font_bytes'),
    other_bytes: optionalBudget(releaseRaw.other_bytes, 'release.other_bytes'),
    max_image_bytes: optionalBudget(releaseRaw.max_image_bytes, 'release.max_image_bytes'),
    max_font_bytes: optionalBudget(releaseRaw.max_font_bytes, 'release.max_font_bytes'),
  };

  const networkRaw = requireObject(config.network ?? {}, 'network');
  rejectUnknownKeys(
    networkRaw,
    [
      'total_transfer_bytes',
      'javascript_transfer_bytes',
      'css_transfer_bytes',
      'image_transfer_bytes',
      'font_transfer_bytes',
      'third_party_transfer_bytes',
      'third_party_requests',
      'per_origin',
    ],
    'network',
  );
  const network = {
    total_transfer_bytes: optionalBudget(networkRaw.total_transfer_bytes, 'network.total_transfer_bytes'),
    javascript_transfer_bytes: optionalBudget(networkRaw.javascript_transfer_bytes, 'network.javascript_transfer_bytes'),
    css_transfer_bytes: optionalBudget(networkRaw.css_transfer_bytes, 'network.css_transfer_bytes'),
    image_transfer_bytes: optionalBudget(networkRaw.image_transfer_bytes, 'network.image_transfer_bytes'),
    font_transfer_bytes: optionalBudget(networkRaw.font_transfer_bytes, 'network.font_transfer_bytes'),
    third_party_transfer_bytes: optionalBudget(networkRaw.third_party_transfer_bytes, 'network.third_party_transfer_bytes'),
    third_party_requests: optionalBudget(networkRaw.third_party_requests, 'network.third_party_requests'),
    per_origin: {},
  };

  if (networkRaw.per_origin !== undefined) {
    const perOrigin = requireObject(networkRaw.per_origin, 'network.per_origin');
    for (const [originText, rawBudget] of Object.entries(perOrigin)) {
      const origin = normalizeOrigin(originText, `network.per_origin.${originText}`);
      const budget = requireObject(rawBudget, `network.per_origin.${originText}`);
      rejectUnknownKeys(budget, ['transfer_bytes', 'requests'], `network.per_origin.${origin}`);
      if (network.per_origin[origin]) {
        throw new ConfigError(`duplicate_per_origin=${origin}`);
      }
      network.per_origin[origin] = {
        transfer_bytes: optionalBudget(budget.transfer_bytes, `network.per_origin.${origin}.transfer_bytes`),
        requests: optionalBudget(budget.requests, `network.per_origin.${origin}.requests`),
      };
      if (network.per_origin[origin].transfer_bytes === null && network.per_origin[origin].requests === null) {
        throw new ConfigError(`empty_per_origin_budget=${origin}`);
      }
    }
  }

  const firstPartyOrigins = new Set();
  if (config.first_party_origins !== undefined) {
    if (!Array.isArray(config.first_party_origins)) {
      throw new ConfigError('invalid_array=first_party_origins');
    }
    for (let index = 0; index < config.first_party_origins.length; index += 1) {
      firstPartyOrigins.add(normalizeOrigin(config.first_party_origins[index], `first_party_origins[${index}]`));
    }
  }

  for (const origin of Object.keys(network.per_origin)) {
    if (firstPartyOrigins.has(origin)) {
      throw new ConfigError(`per_origin_conflicts_first_party=${origin}`);
    }
  }

  const extensions = normalizeExtensions(config.extensions);
  const configuredBudgetCount = [
    ...Object.values(release),
    ...Object.entries(network)
      .filter(([key]) => key !== 'per_origin')
      .map(([, value]) => value),
  ].filter((value) => value !== null).length + Object.keys(network.per_origin).length;

  if (configuredBudgetCount === 0) {
    throw new ConfigError('no_budgets_configured');
  }

  const networkConfigured = Object.entries(network)
    .some(([key, value]) => key === 'per_origin' ? Object.keys(value).length > 0 : value !== null);

  return {
    schema_version: SCHEMA_VERSION,
    project,
    baseline: baselineMeta,
    first_party_origins: firstPartyOrigins,
    extensions,
    release,
    network,
    networkConfigured,
  };
}

async function readJson(filePath, field) {
  let raw;
  try {
    raw = await fs.readFile(filePath, 'utf8');
  } catch (error) {
    throw new ConfigError(`unreadable_${field}=${filePath}:${error.code ?? 'error'}`);
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new ConfigError(`invalid_json_${field}=${filePath}`);
  }
}

function categoryForFile(relativePath, extensions) {
  const extension = path.extname(relativePath).toLowerCase();
  for (const [category, values] of Object.entries(extensions)) {
    if (values.includes(extension)) return category;
  }
  return 'other';
}

async function scanRelease(root, config) {
  const totals = {
    total: 0,
    javascript: 0,
    css: 0,
    images: 0,
    fonts: 0,
    other: 0,
    files: 0,
  };
  const files = [];

  async function walk(directory) {
    const entries = await fs.readdir(directory, {withFileTypes: true});
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const absolute = path.join(directory, entry.name);
      const relative = path.relative(root, absolute).split(path.sep).join('/');
      if (entry.isSymbolicLink()) {
        throw new ConfigError(`release_symlink_not_supported=${relative}`);
      }
      if (entry.isDirectory()) {
        await walk(absolute);
        continue;
      }
      if (!entry.isFile()) continue;
      const stat = await fs.stat(absolute);
      if (!Number.isSafeInteger(stat.size) || stat.size < 0) {
        throw new ConfigError(`invalid_file_size=${relative}`);
      }
      const category = categoryForFile(relative, config.extensions);
      totals.total += stat.size;
      totals[category] += stat.size;
      totals.files += 1;
      files.push({path: relative, bytes: stat.size, category});
    }
  }

  await walk(root);
  return {totals, files};
}

function addFailure(failures, scope, dimension, actual, limit, detail = null) {
  failures.push({scope, dimension, actual, limit, detail});
}

function evaluateRelease(releaseScan, config, failures) {
  const {totals, files} = releaseScan;
  const mapping = {
    total_bytes: totals.total,
    javascript_bytes: totals.javascript,
    css_bytes: totals.css,
    image_bytes: totals.images,
    font_bytes: totals.fonts,
    other_bytes: totals.other,
  };

  for (const [dimension, actual] of Object.entries(mapping)) {
    const limit = config.release[dimension];
    if (limit !== null && actual > limit) {
      addFailure(failures, 'release', dimension, actual, limit);
    }
  }

  if (config.release.max_image_bytes !== null) {
    for (const file of files.filter((item) => item.category === 'images')) {
      if (file.bytes > config.release.max_image_bytes) {
        addFailure(failures, 'release-file', 'max_image_bytes', file.bytes, config.release.max_image_bytes, file.path);
      }
    }
  }
  if (config.release.max_font_bytes !== null) {
    for (const file of files.filter((item) => item.category === 'fonts')) {
      if (file.bytes > config.release.max_font_bytes) {
        addFailure(failures, 'release-file', 'max_font_bytes', file.bytes, config.release.max_font_bytes, file.path);
      }
    }
  }
}

function networkCategory(resourceType) {
  switch (String(resourceType ?? '').toLowerCase()) {
    case 'script': return 'javascript';
    case 'stylesheet': return 'css';
    case 'image': return 'images';
    case 'font': return 'fonts';
    default: return 'other';
  }
}

function safeHttpOrigin(urlText, field) {
  let parsed;
  try {
    parsed = new URL(urlText);
  } catch {
    throw new ConfigError(`invalid_url=${field}`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) return null;
  return parsed.origin;
}

function summarizeLighthouseReport(report, reportName, configuredFirstPartyOrigins) {
  const finalUrl = report.finalUrl ?? report.finalDisplayedUrl ?? report.requestedUrl;
  const pageOrigin = safeHttpOrigin(requireString(finalUrl, `${reportName}.finalUrl`), `${reportName}.finalUrl`);
  if (!pageOrigin) throw new ConfigError(`non_http_page_url=${reportName}`);

  const items = report?.audits?.['network-requests']?.details?.items;
  if (!Array.isArray(items)) {
    throw new ConfigError(`missing_network_requests=${reportName}`);
  }

  const firstPartyOrigins = new Set(configuredFirstPartyOrigins);
  firstPartyOrigins.add(pageOrigin);
  const totals = {
    total_transfer_bytes: 0,
    javascript_transfer_bytes: 0,
    css_transfer_bytes: 0,
    image_transfer_bytes: 0,
    font_transfer_bytes: 0,
    third_party_transfer_bytes: 0,
    third_party_requests: 0,
  };
  const perOrigin = {};

  for (let index = 0; index < items.length; index += 1) {
    const item = requireObject(items[index], `${reportName}.network[${index}]`);
    const urlText = requireString(item.url, `${reportName}.network[${index}].url`);
    const origin = safeHttpOrigin(urlText, `${reportName}.network[${index}].url`);
    if (!origin) continue;
    const transfer = item.transferSize ?? 0;
    if (!Number.isSafeInteger(transfer) || transfer < 0) {
      throw new ConfigError(`invalid_transfer_size=${reportName}:${index}`);
    }
    totals.total_transfer_bytes += transfer;
    const category = networkCategory(item.resourceType);
    if (category === 'javascript') totals.javascript_transfer_bytes += transfer;
    if (category === 'css') totals.css_transfer_bytes += transfer;
    if (category === 'images') totals.image_transfer_bytes += transfer;
    if (category === 'fonts') totals.font_transfer_bytes += transfer;

    if (!firstPartyOrigins.has(origin)) {
      totals.third_party_transfer_bytes += transfer;
      totals.third_party_requests += 1;
      perOrigin[origin] ??= {transfer_bytes: 0, requests: 0};
      perOrigin[origin].transfer_bytes += transfer;
      perOrigin[origin].requests += 1;
    }
  }

  return {report: reportName, page_url: finalUrl, page_origin: pageOrigin, totals, per_origin: perOrigin};
}

async function loadLighthouseSummaries(directory, config) {
  let entries;
  try {
    entries = await fs.readdir(directory, {withFileTypes: true});
  } catch (error) {
    throw new ConfigError(`unreadable_lighthouse_dir=${directory}:${error.code ?? 'error'}`);
  }
  const summaries = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isFile() || !entry.name.toLowerCase().endsWith('.json')) continue;
    const filePath = path.join(directory, entry.name);
    const report = await readJson(filePath, 'lighthouse_report');
    if (!report?.audits?.['network-requests']) continue;
    const summary = summarizeLighthouseReport(report, entry.name, config.first_party_origins);
    if (Object.prototype.hasOwnProperty.call(config.network.per_origin, summary.page_origin)) {
      throw new ConfigError(`per_origin_matches_page_origin=${entry.name}:${summary.page_origin}`);
    }
    summaries.push(summary);
  }
  if (summaries.length === 0) {
    throw new ConfigError(`no_lighthouse_network_reports=${directory}`);
  }
  return summaries;
}

function evaluateNetwork(summaries, config, failures) {
  const simpleDimensions = [
    'total_transfer_bytes',
    'javascript_transfer_bytes',
    'css_transfer_bytes',
    'image_transfer_bytes',
    'font_transfer_bytes',
    'third_party_transfer_bytes',
    'third_party_requests',
  ];

  for (const summary of summaries) {
    for (const dimension of simpleDimensions) {
      const limit = config.network[dimension];
      if (limit !== null && summary.totals[dimension] > limit) {
        addFailure(failures, `network:${summary.report}`, dimension, summary.totals[dimension], limit, summary.page_url);
      }
    }
    for (const [origin, originBudget] of Object.entries(config.network.per_origin)) {
      const actual = summary.per_origin[origin] ?? {transfer_bytes: 0, requests: 0};
      if (originBudget.transfer_bytes !== null && actual.transfer_bytes > originBudget.transfer_bytes) {
        addFailure(failures, `network-origin:${summary.report}`, 'transfer_bytes', actual.transfer_bytes, originBudget.transfer_bytes, origin);
      }
      if (originBudget.requests !== null && actual.requests > originBudget.requests) {
        addFailure(failures, `network-origin:${summary.report}`, 'requests', actual.requests, originBudget.requests, origin);
      }
    }
  }
}

async function writeJsonReport(filePath, report) {
  const parent = path.dirname(filePath);
  await fs.mkdir(parent, {recursive: true});
  await fs.writeFile(filePath, `${JSON.stringify(report, null, 2)}\n`, {encoding: 'utf8', mode: 0o600});
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`RELEASE_BUDGET_CONFIG_ERROR ${error.message}`);
    console.error(usage());
    process.exitCode = 2;
    return;
  }

  if (args.help) {
    console.log(usage());
    return;
  }
  if (!args.config || !args.root) {
    console.error('RELEASE_BUDGET_CONFIG_ERROR --config and --root are required');
    console.error(usage());
    process.exitCode = 2;
    return;
  }

  try {
    const configPath = await fs.realpath(args.config);
    const root = await fs.realpath(args.root);
    const rootStat = await fs.stat(root);
    if (!rootStat.isDirectory()) throw new ConfigError(`release_root_not_directory=${root}`);
    const rawConfig = await readJson(configPath, 'config');
    const config = validateConfig(rawConfig);
    if (config.networkConfigured && !args['lighthouse-dir']) {
      throw new ConfigError('network_budgets_require_lighthouse_dir');
    }

    const release = await scanRelease(root, config);
    const failures = [];
    evaluateRelease(release, config, failures);

    let lighthouse = [];
    if (args['lighthouse-dir']) {
      const lighthouseDir = await fs.realpath(args['lighthouse-dir']);
      lighthouse = await loadLighthouseSummaries(lighthouseDir, config);
      evaluateNetwork(lighthouse, config, failures);
    }

    const report = {
      schema: 'hache-release-budget-report/v1',
      project: config.project,
      baseline: config.baseline,
      release_root: root,
      release,
      lighthouse,
      failures,
      decision: failures.length === 0 ? 'WITHIN_CONFIGURED_BUDGETS' : 'BUDGET_EXCEEDED',
      note: 'This result evaluates configured release/network budgets only; it is not a Production Ready declaration or a substitute for field metrics/human review.',
    };

    if (args.json) await writeJsonReport(path.resolve(args.json), report);

    if (failures.length > 0) {
      for (const failure of failures) {
        console.error(`BUDGET_FAIL scope=${failure.scope} dimension=${failure.dimension} actual=${failure.actual} limit=${failure.limit}${failure.detail ? ` detail=${JSON.stringify(failure.detail)}` : ''}`);
      }
      console.error(`RELEASE_BUDGET_FAILED failures=${failures.length} project=${JSON.stringify(config.project)}`);
      process.exitCode = 1;
      return;
    }

    console.log(`RELEASE_BUDGET_OK project=${JSON.stringify(config.project)} files=${release.totals.files} bytes=${release.totals.total} lighthouse_reports=${lighthouse.length}`);
  } catch (error) {
    if (error instanceof ConfigError) {
      console.error(`RELEASE_BUDGET_CONFIG_ERROR ${error.message}`);
      process.exitCode = 2;
      return;
    }
    console.error(`RELEASE_BUDGET_CONFIG_ERROR unexpected=${error?.message ?? String(error)}`);
    process.exitCode = 2;
  }
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1] ?? '')) {
  await main();
}
