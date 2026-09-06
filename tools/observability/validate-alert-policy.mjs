#!/usr/bin/env node

import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const SIGNALS = new Set([
  'latency',
  'traffic',
  'errors',
  'saturation',
  'cuf_success',
  'cuf_failure',
  'cuf_pending',
]);
const OPERATORS = new Set(['>', '>=', '<', '<=', '==']);
const SEVERITIES = new Set(['info', 'warning', 'critical']);
const MAX_WINDOW_SECONDS = 31 * 24 * 60 * 60;
const ID_PATTERN = /^[a-z0-9][a-z0-9._-]{2,79}$/;
const METRIC_PATTERN = /^[a-zA-Z][a-zA-Z0-9._-]{2,159}$/;

function fail(message) {
  throw new Error(`ALERT_POLICY_INVALID: ${message}`);
}

function requiredString(value, label, maxLength = 500) {
  if (typeof value !== 'string' || value.trim() === '') {
    fail(`${label} is required`);
  }
  const normalized = value.trim();
  if (normalized.length > maxLength || /[\u0000-\u001f\u007f]/u.test(normalized)) {
    fail(`${label} is invalid`);
  }
  return normalized;
}

function positiveInteger(value, label, { allowZero = false } = {}) {
  if (!Number.isInteger(value) || value < (allowZero ? 0 : 1)) {
    fail(`${label} must be ${allowZero ? 'a non-negative' : 'a positive'} integer`);
  }
  return value;
}

export function validateAlertPolicy(policy) {
  if (policy === null || typeof policy !== 'object' || Array.isArray(policy)) {
    fail('root must be an object');
  }
  if (policy.schema_version !== 1) {
    fail('schema_version must be 1');
  }

  requiredString(policy.project, 'project', 120);
  const reviewedAt = requiredString(policy.reviewed_at, 'reviewed_at', 10);
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(reviewedAt) || Number.isNaN(Date.parse(`${reviewedAt}T00:00:00Z`))) {
    fail('reviewed_at must be a valid YYYY-MM-DD date');
  }
  if (!Array.isArray(policy.alerts) || policy.alerts.length === 0) {
    fail('alerts must contain at least one configured alert');
  }

  const seenIds = new Set();
  for (const [index, alert] of policy.alerts.entries()) {
    const prefix = `alerts[${index}]`;
    if (alert === null || typeof alert !== 'object' || Array.isArray(alert)) {
      fail(`${prefix} must be an object`);
    }

    const id = requiredString(alert.id, `${prefix}.id`, 80);
    if (!ID_PATTERN.test(id)) {
      fail(`${prefix}.id must use low-cardinality slug characters`);
    }
    if (seenIds.has(id)) {
      fail(`${prefix}.id duplicates ${id}`);
    }
    seenIds.add(id);

    requiredString(alert.cuf, `${prefix}.cuf`, 120);
    if (!SIGNALS.has(alert.signal)) {
      fail(`${prefix}.signal must be one of ${[...SIGNALS].join(', ')}`);
    }

    const metric = requiredString(alert.metric, `${prefix}.metric`, 160);
    if (!METRIC_PATTERN.test(metric)) {
      fail(`${prefix}.metric must be a stable metric name, not a raw URL/payload`);
    }
    if (!OPERATORS.has(alert.operator)) {
      fail(`${prefix}.operator is unsupported`);
    }
    if (typeof alert.threshold !== 'number' || !Number.isFinite(alert.threshold)) {
      fail(`${prefix}.threshold must be a finite number`);
    }

    const windowSeconds = positiveInteger(alert.window_seconds, `${prefix}.window_seconds`);
    if (windowSeconds > MAX_WINDOW_SECONDS) {
      fail(`${prefix}.window_seconds exceeds the supported policy window`);
    }
    const forSeconds = positiveInteger(alert.for_seconds, `${prefix}.for_seconds`, { allowZero: true });
    if (forSeconds > windowSeconds) {
      fail(`${prefix}.for_seconds cannot exceed window_seconds`);
    }

    if (!SEVERITIES.has(alert.severity)) {
      fail(`${prefix}.severity must be info, warning or critical`);
    }
    requiredString(alert.owner, `${prefix}.owner`, 160);
    const runbook = requiredString(alert.runbook, `${prefix}.runbook`, 300);
    if (runbook.startsWith('javascript:') || runbook.startsWith('data:')) {
      fail(`${prefix}.runbook uses an unsafe location`);
    }
    requiredString(alert.action, `${prefix}.action`, 1000);
    requiredString(alert.data_source, `${prefix}.data_source`, 200);
  }

  return policy;
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) {
    console.error('Usage: node tools/observability/validate-alert-policy.mjs <alert-policy.json>');
    process.exit(64);
  }

  const absolute = path.resolve(configPath);
  const raw = await fs.readFile(absolute, 'utf8');
  const policy = JSON.parse(raw);
  validateAlertPolicy(policy);
  console.log(`ALERT_POLICY_OK alerts=${policy.alerts.length} project=${policy.project}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  });
}
