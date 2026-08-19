// V78-014 — DecisionEvidence SHADOW-POPULATE.
// Schema authority: docs/ai-coengineer/V78_DECISION_EVIDENCE_SCHEMA.md (V78-002).
//
// Every function here is a PURE MAPPING from an already-computed decision
// object into the V78-002 DecisionEvidence envelope. Nothing in this file
// re-derives a gate, threshold, score, or execution outcome — it only
// observes and records what the existing pipeline already decided.
//
// Writes go ONLY to the two new keys below. Nothing here reads or writes
// v775:*, v7712:*, v7713:*, v7718:hyro:runtime, or any other production
// key. This module is fire-and-forget safe: every write path is wrapped so
// a failure here can never affect the caller's own return value.
//
// Conservative by design (schema §3.1, §3.2): any field this module cannot
// confidently derive from already-present data is left null/UNKNOWN/MISSING
// rather than guessed or fabricated.

const SIGNAL_EVIDENCE_KEY = "v78014:evidence:signal";
const HYRO_EVIDENCE_KEY = "v78014:evidence:hyro";
const EVIDENCE_CAP = 200;
const EVIDENCE_TTL_SEC = 21600;

function freshnessFromQuote(q) {
  if (!q) return "UNKNOWN";
  if (q.fresh === true) return "LIVE";
  if (q.fresh === false) return "STALE";
  return "UNKNOWN";
}

function actionFromStatus(status) {
  const map = {
    MARKET: "MARKET",
    LIMIT: "LIMIT",
    MARKET_PLAN: "MARKET_PLAN",
    LIMIT_PLAN: "LIMIT_PLAN",
    MARKET_SIGNAL: "MARKET_PLAN",
    NEAR_MARKET_PLAN: "MARKET_PLAN",
    WATCH: "WATCH",
    DATA_BLOCK: "DATA_BLOCK",
    HOLD: "HOLD",
    TIGHTEN: "TIGHTEN",
    CUT: "CUT",
  };
  return map[status] || "UNKNOWN";
}

export function buildSignalDecisionEvidence(a, {runtimeVersion = null, scanId = null} = {}) {
  if (!a || !a.symbol) return null;
  const q = a.quote || a.analysisQuote || null;
  const now = Date.now();
  const sourceKey = q ? (q.source || "unknown_source") : null;
  const sources = {};
  if (q) {
    sources[sourceKey] = {
      provider: q.source || "unknown",
      providerSymbol: q.providerSymbol || a.symbol,
      requestedSymbol: a.symbol,
      instrumentType: a.market || null,
      providerTimestamp: Number.isFinite(q.providerTimestamp) ? q.providerTimestamp : null,
      observedAt: now,
      ageSec: Number.isFinite(q.quoteAgeSec) ? q.quoteAgeSec : null,
      freshness: freshnessFromQuote(q),
      analysisOnly: q.analysisOnly !== false,
      executionVerified: !!q.executionVerified,
      degradedReason: q.fresh === false ? "QUOTE_STALE" : null,
    };
  }

  const gates = [];
  const news = a.canonical?.news;
  if (news) {
    gates.push({
      name: "NEWS_CLEARANCE",
      state: news.cleared ? (news.soft ? "DEGRADED" : "PASS") : "BLOCK",
      reason: news.source || (news.cleared ? null : "NEWS_CONTEXT_REQUIRED"),
      checkedAt: now,
      hard: false,
    });
  }
  if (a.reason === "M15_LOCATION_REQUIRED" || a.reason === "M5_MSS_DISPLACEMENT_RETEST_REQUIRED") {
    gates.push({name: "STRUCTURE_TRIGGER", state: "BLOCK", reason: a.reason, checkedAt: now, hard: true});
  }
  if (a.reason === "RR_QUALITY_REQUIRED") {
    gates.push({name: "RR_QUALITY", state: "BLOCK", reason: a.reason, checkedAt: now, hard: true});
  }
  if (a.status === "DATA_BLOCK") {
    gates.push({name: "DATA_AVAILABILITY", state: "BLOCK", reason: a.reason || a.error || "DATA_UNAVAILABLE", checkedAt: now, hard: true});
  }

  const staleRefs = sourceKey && sources[sourceKey]?.freshness === "STALE" ? [sourceKey] : [];
  const missingRefs = q ? [] : ["analysisQuote"];
  const overallFreshness = q ? freshnessFromQuote(q) : "MISSING";
  const planned = a.planned || null;

  return {
    schemaVersion: "V78-002",
    decisionId: `signal:${a.market || "unknown"}:${a.symbol}:${now}`,
    createdAt: now,
    market: a.market || "unknown",
    symbol: a.symbol,
    side: ["LONG", "BUY"].includes(a.side) ? "BUY" : ["SHORT", "SELL"].includes(a.side) ? "SELL" : null,
    action: actionFromStatus(a.status),
    sources,
    observations: [],
    gates,
    decision: {
      status: a.status || "UNKNOWN",
      reason: a.reason || (a.status === "DATA_BLOCK" ? (a.error || "DATA_BLOCK") : "N/A"),
      score: Number.isFinite(a.score) ? a.score : null,
      rr: Number.isFinite(planned?.targetRR) ? planned.targetRR : (Number.isFinite(a.targetRR) ? a.targetRR : null),
      entry: Number.isFinite(planned?.entry) ? planned.entry : (Number.isFinite(a.entry) ? a.entry : null),
      sl: Number.isFinite(planned?.sl) ? planned.sl : (Number.isFinite(a.sl) ? a.sl : null),
      tp: Number.isFinite(planned?.tp2) ? planned.tp2 : (Number.isFinite(a.tp2) ? a.tp2 : null),
      strategy: a.method?.profile || null,
      profile: a.entryPolicy?.profile || a.method?.activeMode || null,
    },
    dataIntegrity: {
      overallFreshness,
      providerAgreement: q ? "SINGLE_SOURCE" : "UNKNOWN",
      staleRefs,
      missingRefs,
      degradedRefs: [],
      fabricatedValues: false,
    },
    execution: {
      suitability: "ADVISORY_ONLY",
      executionAuthority: "NONE",
      quoteRef: sourceKey,
      quoteFreshness: overallFreshness,
      hardBlockReasons: gates.filter(g => g.hard && g.state === "BLOCK").map(g => g.reason || g.name),
      accountId: null,
    },
    lineage: {
      engine: a.engine || null,
      runtimeVersion,
      sourceCommit: null,
      scanId,
      setupId: null,
      parentDecisionId: null,
    },
  };
}

export function buildHyroDecisionEvidence(out, {runtimeVersion = null} = {}) {
  if (!out) return [];
  const now = Date.now();
  const results = [];

  for (const p of out.preview || []) {
    if (!p?.symbol) continue;
    results.push({
      schemaVersion: "V78-002",
      decisionId: `hyro:${p.symbol}:${now}`,
      createdAt: now,
      market: "hyro",
      symbol: p.symbol,
      side: p.side === "Buy" || p.side === "BUY" ? "BUY" : p.side === "Sell" || p.side === "SELL" ? "SELL" : null,
      action: actionFromStatus(p.status),
      sources: {},
      observations: [
        {id: "microScore", category: "MICROSTRUCTURE", value: p.microScore ?? null, supports: null, reason: null},
        {id: "funding", category: "MICROSTRUCTURE", value: p.funding ?? null, supports: null, reason: "Funding is carry evidence only; does not satisfy the NEWS gate (schema §6)."},
      ],
      gates: p.antiMirrorBlocked ? [{name: "ANTI_MIRROR", state: "BLOCK", reason: "ANTI_MIRROR_SIGNATURE", checkedAt: now, hard: true}] : [],
      decision: {
        status: p.status || "UNKNOWN",
        reason: p.reason || out.reason || "N/A",
        score: null,
        rr: Number.isFinite(p.rr) ? p.rr : null,
        entry: Number.isFinite(p.entry) ? p.entry : null,
        sl: Number.isFinite(p.sl) ? p.sl : null,
        tp: Number.isFinite(p.tp3 ?? p.tp) ? (p.tp3 ?? p.tp) : null,
        strategy: p.strategy || null,
        profile: p.profile || null,
      },
      dataIntegrity: {overallFreshness: "UNKNOWN", providerAgreement: "UNKNOWN", staleRefs: [], missingRefs: [], degradedRefs: [], fabricatedValues: false},
      execution: {
        suitability: out.executed && out.execution?.symbol === p.symbol ? "EXECUTION_ELIGIBLE" : "UNKNOWN",
        executionAuthority: "HYRO",
        quoteRef: null,
        quoteFreshness: "UNKNOWN",
        hardBlockReasons: out.reason && out.reason !== "ORDER_SUBMITTED" ? [out.reason] : [],
        accountId: out.accountId || null,
      },
      lineage: {engine: "hyro-runtime", runtimeVersion, sourceCommit: null, scanId: null, setupId: null, parentDecisionId: null},
    });
  }

  results.push({
    schemaVersion: "V78-002",
    decisionId: `hyro:cycle:${now}`,
    createdAt: now,
    market: "hyro",
    symbol: out.execution?.symbol || "CYCLE",
    side: null,
    action: out.executed ? "MARKET" : "NO_TRADE",
    sources: {},
    observations: [],
    gates: [],
    decision: {status: out.reason || "UNKNOWN", reason: out.reason || "N/A", score: null, rr: null, entry: null, sl: null, tp: null, strategy: null, profile: null},
    dataIntegrity: {overallFreshness: "UNKNOWN", providerAgreement: "UNKNOWN", staleRefs: [], missingRefs: [], degradedRefs: [], fabricatedValues: false},
    execution: {
      suitability: out.executed ? "EXECUTION_ELIGIBLE" : "UNKNOWN",
      executionAuthority: "HYRO",
      quoteRef: null,
      quoteFreshness: "UNKNOWN",
      hardBlockReasons: out.executed ? [] : [out.reason || "UNKNOWN"],
      accountId: out.accountId || null,
    },
    lineage: {engine: "hyro-runtime", runtimeVersion, sourceCommit: null, scanId: null, setupId: null, parentDecisionId: null},
  });

  return results;
}

async function appendEvidence(env, key, entries) {
  if (!env?.TRADING_STATE || !Array.isArray(entries) || !entries.length) return;
  try {
    const old = await env.TRADING_STATE.get(key, "json");
    const rows = Array.isArray(old?.rows) ? old.rows : [];
    rows.unshift(...entries);
    await env.TRADING_STATE.put(key, JSON.stringify({rows: rows.slice(0, EVIDENCE_CAP), updatedAt: Date.now()}), {expirationTtl: EVIDENCE_TTL_SEC});
  } catch {}
}

export async function recordSignalDecisionEvidence(env, evidence) {
  if (!evidence) return;
  await appendEvidence(env, SIGNAL_EVIDENCE_KEY, [evidence]);
}

export async function recordHyroDecisionEvidence(env, evidenceArray) {
  await appendEvidence(env, HYRO_EVIDENCE_KEY, evidenceArray || []);
}

export async function getSignalDecisionEvidence(env, limit = 20) {
  try {
    const v = await env.TRADING_STATE?.get(SIGNAL_EVIDENCE_KEY, "json");
    return (Array.isArray(v?.rows) ? v.rows : []).slice(0, limit);
  } catch { return []; }
}

export async function getHyroDecisionEvidence(env, limit = 20) {
  try {
    const v = await env.TRADING_STATE?.get(HYRO_EVIDENCE_KEY, "json");
    return (Array.isArray(v?.rows) ? v.rows : []).slice(0, limit);
  } catch { return []; }
}
