// Pure decision helpers. No RPC, signing, orders, state mutation or auto-activation.
// Forecasts must be calibrated externally in basis points, never raw ranking scores.
const finite = x => typeof x === 'number' && Number.isFinite(x);
const amount = x => Number.isSafeInteger(x) && x >= 0;
const fresh = (at, now, ttl) => finite(at) && at <= now && now - at <= ttl;
const wait = reason => ({ action: 'HOLD', reason });

export const DEFAULTS = Object.freeze({
  evidenceTtlMs: 60000, quoteTtlMs: 10000,
  minimumSamples: 30, minimumConfidence: 0.8,
  advantageBufferBps: 100, minimumIndependentSignals: 2,
  observationSpanMs: 60000, rotationIntervalMs: 300000,
  maxRotationsPerHour: 2, maxTurnoverFractionPerHour: 0.25,
  maximumForecastBps: 10000,
});

export function discoveryDisposition(token) {
  // Labels (meme/non-meme/unclassified) are not security evidence.
  // This classifies WATCH candidates only. Execution still needs original hard gates.
  if (!token || typeof token.mint !== 'string' || !token.mint.trim()) return 'INVALID';
  if (token.chain !== 'solana') return 'UNSUPPORTED_CHAIN';
  return token.securityBlocked === true ? 'REJECT' : 'WATCH';
}

function policyValid(p) {
  return Object.keys(DEFAULTS).every(k => finite(p[k]) && p[k] >= 0)
    && p.evidenceTtlMs > 0 && p.quoteTtlMs > 0
    && Number.isInteger(p.minimumSamples) && p.minimumSamples >= 30
    && p.minimumConfidence >= 0.8 && p.minimumConfidence <= 1
    && p.advantageBufferBps >= 100
    && Number.isInteger(p.minimumIndependentSignals) && p.minimumIndependentSignals >= 2
    && p.observationSpanMs >= 60000 && p.rotationIntervalMs >= 300000
    && Number.isInteger(p.maxRotationsPerHour) && p.maxRotationsPerHour > 0
    && p.maxTurnoverFractionPerHour > 0 && p.maxTurnoverFractionPerHour <= 0.25;
}

export function rotationDecision(input, overrides = {}) {
  const p = { ...DEFAULTS, ...overrides };
  if (!policyValid(p)) return wait('INVALID_POLICY');
  const { nowMs, held, target, costs, history, rotationNotionalLamports,
    equityLamports, gateAllowed, pendingOrder } = input || {};
  if (!finite(nowMs) || nowMs < 0) return wait('INVALID_CLOCK');
  if (gateAllowed !== true || pendingOrder !== false) return wait('GATE_OR_PENDING_ORDER');
  if (!held || !target || !held.mint || !target.mint || held.mint === target.mint)
    return wait('INVALID_PAIR');
  if (target.alreadyHeld !== false || target.hardSafetyPassed !== true
      || target.executableSizeVerified !== true || target.sellRouteVerified !== true)
    return wait('TARGET_NOT_EXECUTABLE');
  if (held.sellRouteVerified !== true) return wait('SOURCE_EXIT_UNVERIFIED');
  if (!amount(rotationNotionalLamports) || rotationNotionalLamports === 0
      || !amount(equityLamports) || equityLamports === 0)
    return wait('INVALID_CAPITAL');
  for (const row of [held, target]) {
    if (!fresh(row.evidenceAtMs, nowMs, p.evidenceTtlMs)
        || !fresh(row.quoteAtMs, nowMs, p.quoteTtlMs)) return wait('STALE_EVIDENCE');
    if (!finite(row.expectedNetReturnBps) || Math.abs(row.expectedNetReturnBps) > p.maximumForecastBps
        || !finite(row.uncertaintyBps) || row.uncertaintyBps < 0
        || !Number.isInteger(row.sampleCount) || row.sampleCount < p.minimumSamples
        || !finite(row.confidence) || row.confidence < p.minimumConfidence || row.confidence > 1
        || !finite(row.horizonMs) || row.horizonMs <= 0)
      return wait('UNVALIDATED_FORECAST');
  }
  if (held.horizonMs !== target.horizonMs) return wait('HORIZON_MISMATCH');
  // A flat price alone is insufficient; preserve healthy runners.
  if (held.thesisWeakening !== true || held.trendHealthy !== false)
    return wait('HOLD_HEALTHY_THESIS');
  const signals = held.independentWeaknessSignals;
  if (!Array.isArray(signals) || signals.some(x => typeof x !== 'string' || !x.trim())
      || new Set(signals).size < p.minimumIndependentSignals)
    return wait('WEAKNESS_NOT_CONFIRMED');
  const observations = held.weakObservations;
  if (!Array.isArray(observations) || observations.length < 3
      || observations.some((x, i) => !x || x.weak !== true || !finite(x.atMs)
        || x.atMs < 0 || x.atMs > nowMs || (i > 0 && x.atMs <= observations[i - 1].atMs))
      || observations.at(-1).atMs - observations[0].atMs < p.observationSpanMs
      || nowMs - observations.at(-1).atMs > p.evidenceTtlMs)
    return wait('NEED_DISTINCT_WEAK_OBSERVATIONS');
  if (!costs || costs.allInVerified !== true
      || costs.notionalLamports !== rotationNotionalLamports
      || !fresh(costs.atMs, nowMs, p.quoteTtlMs)) return wait('COSTS_UNVERIFIED');
  const costNames = ['sellFeeBps', 'buyFeeBps', 'sellImpactBps', 'buyImpactBps',
    'networkFeeBps', 'slippageBufferBps'];
  if (costNames.some(k => !finite(costs[k]) || costs[k] < 0)) return wait('COSTS_UNVERIFIED');
  if (!Array.isArray(history) || history.some(x => !x || !finite(x.atMs)
      || x.atMs > nowMs || x.atMs < 0 || !amount(x.notionalLamports)))
    return wait('ROTATION_HISTORY_UNAVAILABLE');
  const recent = history.filter(x => nowMs - x.atMs < 3600000);
  if (recent.some(x => nowMs - x.atMs < p.rotationIntervalMs)) return wait('ROTATION_SETTLING');
  if (recent.length >= p.maxRotationsPerHour) return wait('CHURN_COUNT_LIMIT');
  const turnover = recent.reduce((sum, x) => sum + x.notionalLamports, 0) + rotationNotionalLamports;
  if (!amount(turnover) || turnover > equityLamports * p.maxTurnoverFractionPerHour)
    return wait('CHURN_CAPITAL_LIMIT');
  const switchingCostBps = costNames.reduce((sum, k) => sum + costs[k], 0);
  const conservativeAdvantageBps = target.expectedNetReturnBps - target.uncertaintyBps
    - held.expectedNetReturnBps - held.uncertaintyBps - switchingCostBps;
  if (conservativeAdvantageBps <= p.advantageBufferBps) return wait('EDGE_BELOW_COST_AND_UNCERTAINTY');
  return { action: 'ROTATION_CANDIDATE', fromMint: held.mint, toMint: target.mint,
    rotationNotionalLamports, switchingCostBps, conservativeAdvantageBps,
    requiresPreSellRevalidation: true, requiresConfirmedSell: true,
    requiresPostSellBalanceReconciliation: true, requiresPostSellTargetRevalidation: true };
}

export function capitalBudget(input) {
  // Compound confirmed cash gains; never treat unrealized gains as spendable cash.
  const { cashLamports, reserveLamports, entryFeeLamports, markedEquityLamports,
    valuationFresh, sizeFraction, riskBudgetLamports, scaleAllowed,
    unscaledOrderCeilingLamports, pendingOrder } = input || {};
  const values = [cashLamports, reserveLamports, entryFeeLamports, markedEquityLamports,
    riskBudgetLamports, unscaledOrderCeilingLamports];
  if (values.some(x => !amount(x)) || !finite(sizeFraction) || sizeFraction <= 0
      || sizeFraction > 1 || valuationFresh !== true || pendingOrder !== false
      || typeof scaleAllowed !== 'boolean') return { amountLamports: 0, reason: 'CAPITAL_UNVERIFIED' };
  const spendable = Math.max(0, cashLamports - reserveLamports - entryFeeLamports);
  const amountLamports = Math.floor(Math.min(spendable,
    markedEquityLamports * sizeFraction, riskBudgetLamports,
    scaleAllowed ? Number.MAX_SAFE_INTEGER : unscaledOrderCeilingLamports));
  return { amountLamports, reason: scaleAllowed ? 'CONFIRMED_CAPITAL_COMPOUNDING' : 'SCALE_GATE_PRESERVED' };
}
