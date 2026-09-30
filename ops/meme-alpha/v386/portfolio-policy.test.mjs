import assert from 'node:assert/strict';
import { test } from 'node:test';
import { rotationDecision, capitalBudget, discoveryDisposition } from './portfolio-policy.mjs';
const nowMs = 10000000;
function fixture() {
  const common = { evidenceAtMs: nowMs, quoteAtMs: nowMs, uncertaintyBps: 50,
    sampleCount: 100, confidence: .9, horizonMs: 3600000, sellRouteVerified: true };
  return { nowMs, gateAllowed: true, pendingOrder: false,
    held: { ...common, mint: 'A', expectedNetReturnBps: 50, thesisWeakening: true,
      trendHealthy: false, independentWeaknessSignals: ['FLOW', 'STRUCTURE'],
      weakObservations: [120000, 60000, 0].map(age => ({ atMs: nowMs - age, weak: true })) },
    target: { ...common, mint: 'B', expectedNetReturnBps: 800, hardSafetyPassed: true,
      alreadyHeld: false, executableSizeVerified: true },
    costs: { atMs: nowMs, allInVerified: true, notionalLamports: 10000000,
      sellFeeBps: 10, buyFeeBps: 10, sellImpactBps: 20, buyImpactBps: 20,
      networkFeeBps: 10, slippageBufferBps: 30 },
    history: [], rotationNotionalLamports: 10000000, equityLamports: 100000000 };
}
test('qualified rotation is a proposal, never an order; no input mutation', () => {
  const x = fixture(), copy = structuredClone(x), r = rotationDecision(x);
  assert.equal(r.action, 'ROTATION_CANDIDATE');
  assert.equal(r.conservativeAdvantageBps, 550);
  assert.equal(r.requiresConfirmedSell, true); assert.deepEqual(x, copy);
});
const mutations = {
  'closed gate': x => x.gateAllowed = false,
  'pending order': x => x.pendingOrder = true,
  'missing pending status': x => delete x.pendingOrder,
  'unverified security': x => x.target.hardSafetyPassed = false,
  'unverified sell route': x => x.target.sellRouteVerified = false,
  'stale quote': x => x.target.quoteAtMs -= 10001,
  'future evidence': x => x.held.evidenceAtMs += 1,
  'score is not forecast': x => { delete x.target.expectedNetReturnBps; x.target.score = 99; },
  'insufficient samples': x => x.target.sampleCount = 3,
  'mismatched horizon': x => x.target.horizonMs *= 2,
  'healthy winner': x => x.held.trendHealthy = true,
  'flat alone insufficient': x => x.held.thesisWeakening = false,
  'duplicate signals': x => x.held.independentWeaknessSignals = ['FLOW', 'FLOW'],
  'same snapshot repeated': x => x.held.weakObservations.forEach(o => o.atMs = nowMs),
  'missing fee': x => delete x.costs.networkFeeBps,
  'negative fee': x => x.costs.sellFeeBps = -1,
  'cost notional mismatch': x => x.costs.notionalLamports = 1,
  'costs consume advantage': x => x.costs.buyImpactBps = 900,
  'missing history': x => delete x.history,
  'cooldown': x => x.history.push({ atMs: nowMs - 1000, notionalLamports: 100 }),
  'turnover limit': x => x.history.push({ atMs: nowMs - 400000, notionalLamports: 20000000 }),
  'unknown equity': x => x.equityLamports = null,
  'same mint': x => x.target.mint = 'A',
  'held target': x => x.target.alreadyHeld = true,
};
for (const [name, mutate] of Object.entries(mutations)) test(name, () => {
  const x = fixture(); mutate(x); assert.equal(rotationDecision(x).action, 'HOLD');
});
test('unsafe policy is rejected', () => assert.equal(rotationDecision(fixture(), {
  minimumSamples: 0 }).reason, 'INVALID_POLICY'));
test('new confirmed snapshots permit later reevaluation', () => {
  const x = fixture(); x.history = [{ atMs: nowMs - 400000, notionalLamports: 1000000 }];
  assert.equal(rotationDecision(x).action, 'ROTATION_CANDIDATE');
});
const budget = { cashLamports: 100000000, reserveLamports: 10000000,
  entryFeeLamports: 1000000, markedEquityLamports: 200000000, valuationFresh: true,
  sizeFraction: .2, riskBudgetLamports: 60000000, scaleAllowed: true,
  unscaledOrderCeilingLamports: 10000000, pendingOrder: false };
test('confirmed growth compounds within cash and risk', () => {
  assert.equal(capitalBudget(budget).amountLamports, 40000000);
  assert.equal(capitalBudget({ ...budget, markedEquityLamports: 300000000 }).amountLamports, 60000000);
});
test('scaleAllowed false remains effective', () => assert.equal(capitalBudget({
  ...budget, scaleAllowed: false }).amountLamports, 10000000));
test('unrealized gains cannot spend cash or reserve', () => assert.equal(capitalBudget({
  ...budget, cashLamports: 20000000, markedEquityLamports: 900000000 }).amountLamports, 9000000));
test('stale valuation blocks new sizing', () => assert.equal(capitalBudget({
  ...budget, valuationFresh: false }).amountLamports, 0));
test('unknown values are not zero', () => assert.equal(capitalBudget({
  ...budget, cashLamports: null }).reason, 'CAPITAL_UNVERIFIED'));
test('labels do not exclude safe discovery or authorize execution', () => {
  for (const label of ['MEME_CONFIRMED','NON_MEME','UNCLASSIFIED'])
    assert.equal(discoveryDisposition({ mint: 'A', chain: 'solana', label }), 'WATCH');
  assert.equal(discoveryDisposition({ mint: 'A', chain: 'solana', securityBlocked: true }), 'REJECT');
  assert.equal(discoveryDisposition({ mint: 'A', chain: 'ethereum' }), 'UNSUPPORTED_CHAIN');
});
