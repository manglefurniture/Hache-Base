#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const target = path.resolve(process.argv[2] || '.');
const mode = process.env.SEO_MODE || 'public';
const expectIndexable = process.env.SEO_EXPECT_INDEXABLE !== '0';
const requireCanonical = process.env.SEO_REQUIRE_CANONICAL !== '0';

const failures = [];
const warnings = [];

function fail(id, message) {
  failures.push(`${id} FAIL ${message}`);
}

function warn(id, message) {
  warnings.push(`${id} WARNING ${message}`);
}

function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['.git', 'node_modules', 'vendor'].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

function attr(tag, name) {
  const re = new RegExp(`\\b${name}\\s*=\\s*(["'])(.*?)\\1`, 'i');
  return tag.match(re)?.[2] ?? null;
}

function hasAccessibleName(html, inputTag) {
  if (attr(inputTag, 'aria-label')?.trim()) return true;
  if (attr(inputTag, 'aria-labelledby')?.trim()) return true;
  const id = attr(inputTag, 'id');
  if (!id) return false;
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`<label\\b[^>]*\\bfor\\s*=\\s*(["'])${escaped}\\1`, 'i').test(html);
}

function checkHtml(file) {
  const rel = path.relative(target, file) || path.basename(file);
  const html = fs.readFileSync(file, 'utf8');

  const title = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/<[^>]+>/g, '').trim();
  if (!title) fail('SEO-ONPAGE-001', `${rel}: missing/empty <title>`);

  if (!/<meta\b[^>]*name\s*=\s*(["'])viewport\1[^>]*>/i.test(html)) {
    fail('SEO-MOBILE-001', `${rel}: viewport meta missing`);
  }

  if (expectIndexable && /<meta\b[^>]*name\s*=\s*(["'])robots\1[^>]*content\s*=\s*(["'])[^"']*noindex/i.test(html)) {
    fail('SEO-INDEX-001', `${rel}: unexpected noindex`);
  }

  const canonicals = [...html.matchAll(/<link\b[^>]*rel\s*=\s*(["'])canonical\1[^>]*>/gi)];
  if (requireCanonical) {
    if (canonicals.length !== 1) {
      fail('SEO-INDEX-002', `${rel}: expected exactly one canonical, found ${canonicals.length}`);
    } else {
      const href = attr(canonicals[0][0], 'href');
      if (!href || !/^https:\/\//i.test(href)) fail('SEO-INDEX-002', `${rel}: canonical must be absolute HTTPS`);
    }
  }

  if (!/<h1\b[^>]*>[\s\S]*?<\/h1>/i.test(html)) {
    warn('SEO-ONPAGE-002', `${rel}: no H1 found; verify visible primary context`);
  }

  for (const match of html.matchAll(/<img\b[^>]*>/gi)) {
    if (attr(match[0], 'alt') === null) fail('SEO-A11Y-001', `${rel}: image missing alt attribute`);
  }

  for (const match of html.matchAll(/<(?:input|select|textarea)\b[^>]*>/gi)) {
    const tag = match[0];
    const type = (attr(tag, 'type') || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    if (!hasAccessibleName(html, tag)) fail('SEO-A11Y-002', `${rel}: form control lacks accessible name`);
  }

  for (const match of html.matchAll(/<a\b[^>]*>/gi)) {
    const href = attr(match[0], 'href');
    if (!href && /onclick\s*=/i.test(match[0])) warn('SEO-CRAWL-003', `${rel}: interactive anchor uses onclick without href`);
  }

  for (const match of html.matchAll(/<script\b[^>]*type\s*=\s*(["'])application\/ld\+json\1[^>]*>([\s\S]*?)<\/script>/gi)) {
    try {
      JSON.parse(match[2].trim());
    } catch {
      fail('SEO-SCHEMA-001', `${rel}: invalid JSON-LD`);
    }
  }
}

function checkRobots() {
  if (!['public', 'hybrid'].includes(mode)) return;
  const file = path.join(target, 'robots.txt');
  if (!fs.existsSync(file)) {
    fail('SEO-CRAWL-001', 'robots.txt missing for public/hybrid mode');
    return;
  }

  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split(/\r?\n/).map((line) => line.replace(/#.*$/, '').trim()).filter(Boolean);
  let appliesToAll = false;
  for (const line of lines) {
    const [rawKey, ...rest] = line.split(':');
    const key = rawKey.toLowerCase();
    const value = rest.join(':').trim();
    if (key === 'user-agent') appliesToAll = value === '*';
    if (appliesToAll && key === 'disallow' && value === '/') {
      fail('SEO-CRAWL-002', 'robots.txt contains global Disallow: /');
    }
  }
}

function checkSitemap() {
  const file = path.join(target, 'sitemap.xml');
  if (!fs.existsSync(file)) {
    warn('SEO-SITEMAP-001', 'sitemap.xml not found; verify whether this project requires one');
    return;
  }
  const xml = fs.readFileSync(file, 'utf8');
  if (!/<(?:urlset|sitemapindex)\b/i.test(xml)) fail('SEO-SITEMAP-001', 'sitemap.xml has no urlset/sitemapindex root');
  for (const match of xml.matchAll(/<loc>([\s\S]*?)<\/loc>/gi)) {
    const loc = match[1].trim();
    if (!/^https:\/\//i.test(loc)) fail('SEO-SITEMAP-001', `non-HTTPS/relative sitemap URL: ${loc}`);
  }
}

if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) {
  console.error(`SEO_STATIC_FAIL target is not a directory: ${target}`);
  process.exit(2);
}

for (const file of walk(target).filter((f) => /\.html?$/i.test(f))) checkHtml(file);
checkRobots();
checkSitemap();

for (const line of warnings) console.warn(line);
for (const line of failures) console.error(line);

if (failures.length) {
  console.error(`SEO_STATIC_FAIL failures=${failures.length} warnings=${warnings.length}`);
  process.exit(1);
}

console.log(`SEO_STATIC_OK warnings=${warnings.length}`);
