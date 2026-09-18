// Control Tower tests.
//
// These damage something and demand a refusal. A test that only confirms the
// happy path would have passed on every version of this dashboard that quietly
// rounded "not observed" up to "fine".

import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import path from 'node:path';
import test, { after, before } from 'node:test';
import { fileURLToPath } from 'node:url';

import { ORIGIN, PROVENANCE, isEvidential, provenanceFor } from '../provenance.mjs';
import { fabricSnapshot, labelMatrix, rowProvenance } from '../fabric-snapshot.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SERVER = path.join(__dirname, '..', 'server.mjs');

/* ---------------- provenance derivation ---------------- */

test('an origin nobody asked about is NOT_OBSERVED, never a guess', () => {
  assert.equal(provenanceFor({ origin: ORIGIN.UNCONFIGURED, stale: false, hasTimestamp: true }), PROVENANCE.NOT_OBSERVED);
  assert.equal(provenanceFor({ origin: ORIGIN.GATEWAY_ABSENT, stale: false, hasTimestamp: true }), PROVENANCE.NOT_OBSERVED);
  // An origin this module has never heard of must fail closed, not fall through
  // to the freshness branch and come out REAL_LIVE.
  assert.equal(provenanceFor({ origin: 'ORIGIN_THAT_DOES_NOT_EXIST', stale: false, hasTimestamp: true }), PROVENANCE.NOT_OBSERVED);
  assert.equal(provenanceFor({}), PROVENANCE.NOT_OBSERVED);
});

test('configured-only is CONFIGURED even when perfectly fresh', () => {
  assert.equal(
    provenanceFor({ origin: ORIGIN.GATEWAY_METADATA_ONLY, stale: false, hasTimestamp: true }),
    PROVENANCE.CONFIGURED);
});

test('an undatable answer is UNVERIFIED, not HISTORICAL_EVIDENCE', () => {
  // We cannot say WHEN it was true. That is a different failure from knowing it
  // is old, and collapsing the two is how a timeless payload reads as history.
  assert.equal(provenanceFor({ origin: ORIGIN.FETCHED, stale: true, hasTimestamp: false }), PROVENANCE.UNVERIFIED);
});

test('freshness decides only once something actually answered', () => {
  assert.equal(provenanceFor({ origin: ORIGIN.FETCHED, stale: false, hasTimestamp: true }), PROVENANCE.REAL_LIVE);
  assert.equal(provenanceFor({ origin: ORIGIN.FETCHED, stale: true, hasTimestamp: true }), PROVENANCE.HISTORICAL_EVIDENCE);
  // Asking and failing IS an observation - of a failure, right now.
  assert.equal(provenanceFor({ origin: ORIGIN.FETCH_FAILED, stale: false, hasTimestamp: true }), PROVENANCE.REAL_LIVE);
});

test('absence of evidence never counts as evidence', () => {
  assert.equal(isEvidential(PROVENANCE.NOT_OBSERVED), false);
  assert.equal(isEvidential(PROVENANCE.UNVERIFIED), false);
  assert.equal(isEvidential(PROVENANCE.REAL_LIVE), true);
  assert.equal(isEvidential(PROVENANCE.HISTORICAL_EVIDENCE), true);
});

/* ---------------- fabric rows ---------------- */

test('an unobserved gate stays unobserved', () => {
  assert.equal(rowProvenance('LIVE_RESEARCH_SMOKE', 'NOT_OBSERVED'), PROVENANCE.NOT_OBSERVED);
  assert.equal(rowProvenance('PRIMARY_HEALTH', 'NOT_OBSERVED'), PROVENANCE.NOT_OBSERVED);
  assert.equal(rowProvenance('PRIMARY_HEALTH', 'PASS'), PROVENANCE.HISTORICAL_EVIDENCE);
});

test('SIMULATED_ONLY failover is UNVERIFIED, because nothing served traffic', () => {
  assert.equal(rowProvenance('FAILOVER_PROOF', 'SIMULATED_ONLY'), PROVENANCE.UNVERIFIED);
  assert.equal(rowProvenance('FAILOVER_PROOF', 'UNVERIFIED'), PROVENANCE.UNVERIFIED);
  assert.equal(rowProvenance('FAILOVER_PROOF', 'PASS'), PROVENANCE.HISTORICAL_EVIDENCE);
});

test('FULL_ACTIVE is only as observed as the gates under it', () => {
  assert.equal(rowProvenance('FULL_ACTIVE', false), PROVENANCE.NOT_OBSERVED);
});

test('structural keys are not squeezed into scalar rows', () => {
  const rows = labelMatrix({
    FULL_ACTIVE: false, BLOCKERS: ['X'], STABLE_RUNTIMES: ['a'],
    DEVELOPMENT_LAB_RUNTIMES: ['b'], RUNTIME_LIFECYCLES: { a: 'STABLE' },
  });
  assert.deepEqual(rows.map((r) => r.key), ['FULL_ACTIVE']);
});

test('an unreadable fabric is UNAVAILABLE with no rows, never a partial matrix', async () => {
  const snap = await fabricSnapshot({ python: 'python3-that-does-not-exist' });
  assert.equal(snap.status, 'UNAVAILABLE');
  assert.deepEqual(snap.rows, []);
  assert.deepEqual(snap.blockers, []);
  assert.equal(snap.lifecycles.provenance, PROVENANCE.NOT_OBSERVED);
  assert.ok(snap.reason);
});

test('the canonical matrix is read, not re-derived', async () => {
  const snap = await fabricSnapshot();
  assert.equal(snap.status, 'OK', snap.reason);
  assert.equal(snap.authority, 'RUNTIME_FABRIC_V2');
  assert.ok(snap.rows.some((r) => r.key === 'FULL_ACTIVE'));
  assert.ok(snap.lifecycles.stable.length + snap.lifecycles.development_lab.length > 0);
});

/* ---------------- server ---------------- */

let upstream, upstreamPort, tower, towerPort, payload;

function listen(server) {
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
}

before(async () => {
  upstream = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(payload));
  });
  upstreamPort = await listen(upstream);

  const probe = http.createServer();
  towerPort = await listen(probe);
  await new Promise((r) => probe.close(r));

  payload = { state: 'ONLINE', last_updated: new Date().toISOString(), _origin: 'FETCHED' };

  tower = spawn(process.execPath, [SERVER], {
    env: {
      ...process.env,
      PORT: String(towerPort),
      CC_VPS_STATUS_URL: `http://127.0.0.1:${upstreamPort}/`,
      CONTROL_CENTER_REFRESH_MS: '2000',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Control Tower did not start')), 20_000);
    tower.stdout.on('data', (d) => { if (String(d).includes('listening')) { clearTimeout(timer); resolve(); } });
    tower.on('exit', (c) => { clearTimeout(timer); reject(new Error(`exited ${c}`)); });
  });
});

after(() => { tower?.kill(); upstream?.close(); });

const get = async (p, init) => fetch(`http://127.0.0.1:${towerPort}${p}`, init);

test('an upstream source cannot declare its own provenance', async () => {
  // The payload literally ships `_origin: FETCHED`, which is the value a source
  // would forge to look live. It survives only because the server re-stamps it;
  // the point of the test is the NEXT one, where a source that is unreachable
  // still ships `_origin: FETCHED` and must not be believed.
  const body = await (await get('/api/status')).json();
  assert.equal(body.systems.vps.state, 'ONLINE');
  assert.equal(body.systems.vps._provenance, PROVENANCE.REAL_LIVE);
  // Sources that were never configured must not inherit anything.
  assert.equal(body.systems.telegram._provenance, PROVENANCE.NOT_OBSERVED);
  assert.deepEqual(body.provenance_values, Object.values(PROVENANCE));
});

test('a source with no timestamp cannot pass itself off as live', async () => {
  // A genuine forgery attempt: the payload claims BOTH the origin and the
  // provenance of a live observation, while carrying nothing that can be dated.
  payload = { state: 'ONLINE', _origin: 'FETCHED', _provenance: 'REAL_LIVE', last_updated: null };
  await new Promise((r) => setTimeout(r, 2600));
  const body = await (await get('/api/status')).json();
  assert.equal(body.systems.vps._provenance, PROVENANCE.UNVERIFIED);
  // And the existing contract still holds: a stale success is demoted.
  assert.equal(body.systems.vps.state, 'DEGRADED');
});

test('the Control Tower refuses to be commanded', async () => {
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
    const res = await get('/api/status', { method });
    assert.equal(res.status, 405, `${method} must be refused`);
    assert.equal(res.headers.get('allow'), 'GET, HEAD');
    assert.equal((await res.json()).error, 'CONTROL_TOWER_IS_READ_ONLY');
  }
});

test('/api/fabric serves the canonical matrix with provenance on every row', async () => {
  const body = await (await get('/api/fabric')).json();
  assert.equal(body.status, 'OK', body.reason);
  assert.ok(body.rows.length > 0);
  for (const row of body.rows) {
    assert.ok(Object.values(PROVENANCE).includes(row.provenance), `${row.key} has no provenance`);
  }
  assert.equal(body.rows.find((r) => r.key === 'FULL_ACTIVE').provenance, PROVENANCE.NOT_OBSERVED);
});
