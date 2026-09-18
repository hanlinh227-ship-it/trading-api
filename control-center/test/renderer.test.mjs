// Renderer smoke tests.
//
// The console is served as a static file, so a unit test of the server proves
// nothing about whether the page actually draws. This drives app.js against a
// minimal DOM and real /api payloads and asserts what appears on screen -
// specifically that unobserved things appear as unobserved.

import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const APP = path.join(__dirname, '..', 'public', 'app.js');

const IDS = ['nav', 'legend', 'view', 'viewTitle', 'viewSub', 'liveBadge', 'footMeta', 'filter'];

/** Load app.js against a stub DOM and a stub fetch, and return the stub nodes. */
let bootCount = 0;

/** @param {{hash?: string}} opts */
async function boot({ status, fabric, statusFails = false, hash = '' }) {
  const nodes = Object.fromEntries(IDS.map((id) => [id, {
    id, innerHTML: '', textContent: '', className: '', value: '',
    addEventListener() {}, focus() {},
  }]));

  const timers = [];
  globalThis.document = { getElementById: (id) => nodes[id] ?? null };
  globalThis.location = { hash };
  globalThis.window = { addEventListener() {} };
  globalThis.setInterval = (fn) => { timers.push(fn); return 0; };
  globalThis.fetch = async (url) => {
    if (url.includes('/api/status')) {
      if (statusFails) return { ok: false, status: 503 };
      return { ok: true, json: async () => status };
    }
    return { ok: true, json: async () => fabric };
  };

  // Fresh module instance per boot. The suffix matters: ESM caches by
  // specifier, so without it every boot after the first would silently reuse
  // the first one's module state and the assertions would pass on stale nodes.
  const src = `${await fs.readFile(APP, 'utf8')}\n// boot ${++bootCount}\n`;
  const mod = `data:text/javascript;base64,${Buffer.from(src).toString('base64')}`;
  await import(mod);
  // The bootstrap's tick() is async; let its microtasks settle.
  await new Promise((r) => setTimeout(r, 30));
  return nodes;
}

const freshStatus = () => ({
  last_updated: new Date().toISOString(),
  refresh_ms: 5000,
  provenance_values: ['REAL_LIVE', 'HISTORICAL_EVIDENCE', 'CONFIGURED', 'NOT_OBSERVED', 'UNVERIFIED'],
  systems: {
    vps: { state: 'ONLINE', _provenance: 'REAL_LIVE', age_ms: 1000 },
    github: { state: 'UNKNOWN', _provenance: 'NOT_OBSERVED', age_ms: null },
    cloudflare: { state: 'ONLINE', _provenance: 'HISTORICAL_EVIDENCE', age_ms: 900000 },
    telegram: { state: 'UNKNOWN', _provenance: 'NOT_OBSERVED', age_ms: null },
  },
  ai: {
    deepseek: { state: 'ONLINE', _provenance: 'REAL_LIVE', model: 'deepseek-chat', role: 'implementer' },
    codex: { state: 'UNKNOWN', _provenance: 'CONFIGURED' },
    claude: { state: 'UNKNOWN', _provenance: 'NOT_OBSERVED' },
    qwen: { state: 'UNKNOWN', _provenance: 'NOT_OBSERVED' },
    openrouter: { state: 'UNKNOWN', _provenance: 'NOT_OBSERVED' },
  },
  pipeline: { intake: 'PASS' },
  events: [{ source: 'github', timestamp: new Date().toISOString(), message: 'run finished' }],
});

const okFabric = () => ({
  status: 'OK',
  source: 'acceptance.py --json',
  rows: [
    { key: 'FULL_ACTIVE', value: false, provenance: 'NOT_OBSERVED' },
    { key: 'PRIMARY_RUNTIME', value: 'cloudflare_workers', provenance: 'CONFIGURED' },
    { key: 'FAILOVER_PROOF', value: 'PASS', provenance: 'HISTORICAL_EVIDENCE' },
    { key: 'ZERO_COST_GUARD', value: 'ENFORCED', provenance: 'CONFIGURED' },
    { key: 'PAID_FALLBACK', value: false, provenance: 'CONFIGURED' },
  ],
  blockers: ['CLOUDFLARE_HEALTH'],
  lifecycles: { provenance: 'HISTORICAL_EVIDENCE', stable: ['cloudflare_workers'], development_lab: ['render_free'], by_runtime: { cloudflare_workers: 'STABLE', render_free: 'DISCOVERED' } },
});

test('the overview draws the fabric gates and its blockers', async () => {
  const n = await boot({ status: freshStatus(), fabric: okFabric() });
  assert.match(n.view.innerHTML, /FULL_ACTIVE|Full active/);
  assert.match(n.view.innerHTML, /CLOUDFLARE_HEALTH/);
  assert.match(n.view.innerHTML, /prov NOT_OBSERVED/);
  assert.match(n.nav.innerHTML, /Runtime Fabric/);
  assert.match(n.legend.innerHTML, /REAL_LIVE/);
});

test('LIVE requires every card to be healthy AND actually observed live', async () => {
  // This status has healthy cards whose provenance is not REAL_LIVE. A badge
  // that keyed off state alone would say LIVE here, which is the whole trap.
  const n = await boot({ status: freshStatus(), fabric: okFabric() });
  assert.equal(n.liveBadge.textContent, 'OBSERVING');

  const all = freshStatus();
  for (const group of ['systems', 'ai']) {
    for (const k of Object.keys(all[group])) all[group][k] = { state: 'ONLINE', _provenance: 'REAL_LIVE', age_ms: 10 };
  }
  const live = await boot({ status: all, fabric: okFabric() });
  assert.equal(live.liveBadge.textContent, 'LIVE');

  // One stale card is enough to lose LIVE, even though it still reads ONLINE.
  all.systems.vps._provenance = 'HISTORICAL_EVIDENCE';
  const demoted = await boot({ status: all, fabric: okFabric() });
  assert.equal(demoted.liveBadge.textContent, 'OBSERVING');
});

test('an unreadable fabric draws no fabric values at all', async () => {
  const n = await boot({
    status: freshStatus(),
    fabric: { status: 'UNAVAILABLE', reason: 'tool missing', rows: [], blockers: [] },
    hash: '#runtime',
  });
  assert.match(n.viewTitle.textContent, /Runtime Fabric/);
  assert.match(n.view.innerHTML, /không đọc được/);
  assert.doesNotMatch(n.view.innerHTML, /ENFORCED/);
});

test('a dead /api/status blanks the view instead of showing the last values', async () => {
  const n = await boot({ status: freshStatus(), fabric: okFabric(), statusFails: true });
  assert.match(n.viewSub.textContent, /API error/);
  assert.match(n.view.innerHTML, /Không hiển thị giá trị nào/);
  assert.equal(n.liveBadge.textContent, 'OFFLINE');
});
