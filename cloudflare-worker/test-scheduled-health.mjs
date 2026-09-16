// Contract for the bounded Cloudflare scheduled health refresh.
//
// The mesh needs proactive health refresh inside LIVE_TTL_MS (30 min). GitHub
// Actions cron cannot deliver it: over 4.9h with a fixed-minute 20-minute
// cadence live on main, exactly one scheduled run fired. The Worker's own cron
// is the reliable, zero-local mechanism.
//
// The safety rule is SEMANTIC, not "no crons at all": a read-only Model Mesh
// health-maintenance cron is allowed; a financial/trading/deploy/autonomous
// cron is still forbidden.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {HEALTH_REFRESH_CRON, assertHealthOnlyCrons, handleScheduledHealthRefresh} from './model-mesh/scheduled-health.js';
import {markSelfHealAttempt} from './model-mesh/self-heal.js';

// Owned here, not by the module, so the module never names what it must not touch.
const FORBIDDEN_CRON_INTENTS = ['bybit', 'order', 'wallet', 'withdraw', 'transfer', 'deploy', 'wrangler', 'autoHub', 'liveAck'];

// --- the cron the Worker is allowed to carry -------------------------------
{
  const [minute, ...rest] = HEALTH_REFRESH_CRON.split(' ');
  assert.deepEqual(rest, ['*', '*', '*', '*'], 'health cron must run every hour');
  const stepMatch = minute.match(/^\*\/(\d+)$/);
  assert.ok(stepMatch, 'health cron uses a step minute field');
  const stepMinutes = Number(stepMatch[1]);
  assert.ok(stepMinutes <= 25, `cadence ${stepMinutes}min must stay inside LIVE_TTL_MS (30min) with margin`);
}

// --- semantic invariant: only the health cron may be configured ------------
assert.doesNotThrow(() => assertHealthOnlyCrons([HEALTH_REFRESH_CRON]));
assert.doesNotThrow(() => assertHealthOnlyCrons([]));
// A second, unexplained cron is refused even if it looks harmless.
assert.throws(() => assertHealthOnlyCrons([HEALTH_REFRESH_CRON, '*/5 * * * *']), /unexpected_cron/);
assert.throws(() => assertHealthOnlyCrons(['0 * * * *']), /unexpected_cron/);

// --- the scheduled handler is health-only and fails closed ----------------
const kv = () => {
  const store = new Map();
  return {get: async k => store.get(k) ?? null, put: async (k, v) => void store.set(k, v)};
};
const waitUntilCtx = () => {
  const pending = [];
  return {ctx: {waitUntil: p => pending.push(p)}, settle: () => Promise.allSettled(pending)};
};

// Runs the canonical probe for the allowed cron.
{
  let probed = 0;
  const {ctx, settle} = waitUntilCtx();
  const res = await handleScheduledHealthRefresh({
    event: {cron: HEALTH_REFRESH_CRON}, env: {TRADING_STATE: kv()}, ctx,
    probeProviders: async () => {probed += 1;}, modelSnapshot: {models: []},
  });
  await settle();
  assert.equal(res.ran, true, 'allowed cron must run the refresh');
  assert.equal(probed, 1, 'canonical probe called exactly once');
}

// Any other cron is refused: an attacker or a mis-edit cannot borrow this handler.
{
  let probed = 0;
  const {ctx, settle} = waitUntilCtx();
  const res = await handleScheduledHealthRefresh({
    event: {cron: '*/1 * * * *'}, env: {TRADING_STATE: kv()}, ctx,
    probeProviders: async () => {probed += 1;}, modelSnapshot: {models: []},
  });
  await settle();
  assert.equal(res.ran, false);
  assert.equal(res.reason, 'unexpected_cron');
  assert.equal(probed, 0, 'unrecognised cron must never probe');
}

// A manual (deploy / refresh-job) probe marks the same claim, so a cron firing right after
// it does not probe again inside the interval.
{
  let probed = 0;
  const env = {TRADING_STATE: kv()};
  const marked = await markSelfHealAttempt(env.TRADING_STATE, {nowMs: Date.now()});
  assert.equal(marked.marked, true);
  const {ctx, settle} = waitUntilCtx();
  const res = await handleScheduledHealthRefresh({
    event: {cron: HEALTH_REFRESH_CRON}, env, ctx,
    probeProviders: async () => {probed += 1;}, modelSnapshot: {models: []},
  });
  await settle();
  assert.equal(res.ran, false, 'cron must yield to a probe that just ran');
  assert.equal(res.reason, 'recently_attempted');
  assert.equal(probed, 0);
}

// Overlap guard: a second invocation inside the min interval does not re-probe.
{
  let probed = 0;
  const env = {TRADING_STATE: kv()};
  for (let i = 0; i < 2; i += 1) {
    const {ctx, settle} = waitUntilCtx();
    await handleScheduledHealthRefresh({
      event: {cron: HEALTH_REFRESH_CRON}, env, ctx,
      probeProviders: async () => {probed += 1;}, modelSnapshot: {models: []},
    });
    await settle();
  }
  assert.equal(probed, 1, 'overlapping invocation must be suppressed by the shared lock');
}

// A failing provider probe must never throw out of the scheduled handler.
{
  const {ctx, settle} = waitUntilCtx();
  const res = await handleScheduledHealthRefresh({
    event: {cron: HEALTH_REFRESH_CRON}, env: {TRADING_STATE: kv()}, ctx,
    probeProviders: async () => {throw new Error('provider down');}, modelSnapshot: {models: []},
  });
  await settle();
  assert.equal(res.ran, true, 'a provider outage is isolated, not surfaced');
}

// --- the handler must not reach trading, financial or deploy surfaces ------
{
  // Scan executable code only. The module documents what it must never do, and
  // that prose is the point -- it is reachable CODE that would be the defect.
  const code = fs.readFileSync('model-mesh/scheduled-health.js', 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n').map(line => line.replace(/\/\/.*$/, '')).join('\n');
  for (const intent of FORBIDDEN_CRON_INTENTS) {
    assert.doesNotMatch(code, new RegExp(intent, 'i'), `health cron must not reference ${intent}`);
  }
  // Guard the guard: the stripper must not simply blank the file out.
  assert.match(code, /handleScheduledHealthRefresh/);
  assert.match(code, /claimSelfHeal/);
}

// --- index.js wires scheduled to the health refresh only ------------------
{
  const index = fs.readFileSync('index.js', 'utf8');
  assert.match(index, /async scheduled\(/, 'worker exposes a scheduled handler');
  const scheduled = index.slice(index.indexOf('async scheduled('));
  assert.match(scheduled, /handleScheduledHealthRefresh/);
  for (const forbidden of ['bybit', 'order', 'autoHub', 'deploy']) {
    assert.doesNotMatch(scheduled, new RegExp(forbidden, 'i'), `scheduled handler must not touch ${forbidden}`);
  }
}

console.log('bounded scheduled health-refresh contracts ok');
