// BYBIT BTC-ONLY DESIGN AUTHORITY
// This file is intentionally dependency-light and serves as the canonical strategy/risk contract
// for the BTCUSDT-only migration. Live execution continues to use the existing Bybit V5 clients.

export const BYBIT_BTC_ONLY_VERSION = "BYBIT-BTC-ONLY-2.0.0-DESIGN";
export const BYBIT_BTC_SYMBOL = "BTCUSDT";

export const BYBIT_BTC_ONLY_CONFIG = Object.freeze({
  symbol: BYBIT_BTC_SYMBOL,
  category: "linear",
  settleCoin: "USDT",
  liveApiPreserved: true,
  strategyDailyTradeQuota: null,
  leverage: { min: 3, target: 8, max: 15 },
  risk: {
    baseEntryRiskPct: 0.75,
    strongEntryRiskPct: 1.0,
    maxInitialEntryRiskPct: 1.5,
    maxActiveRiskPct: 6.0,
    temporaryAPlusActiveRiskPct: 8.0,
    maxPortfolioMarginPct: 65,
    minFreeReservePct: 25,
    addToLoser: false,
    winnerPyramiding: true,
    martingale: false,
    gridRescue: false,
    continuousEquityCompounding: true,
    drawdownGovernor: [
      { ddPct: 5, riskMultiplier: 0.80 },
      { ddPct: 10, riskMultiplier: 0.55 },
      { ddPct: 15, riskMultiplier: 0.30 },
      { ddPct: 20, riskMultiplier: 0.00 }
    ]
  },
  marketModel: {
    regimes: [
      "TREND_UP","TREND_DOWN","RANGE","SQUEEZE",
      "BREAKOUT_UP","BREAKOUT_DOWN","REVERSAL","HIGH_VOL_SHOCK","TRANSITION"
    ],
    primaryInputs: [
      "market_structure","swing_liquidity","session_liquidity",
      "orderbook_imbalance","trade_flow_delta","absorption",
      "liquidity_vacuum","volatility_expansion","volatility_contraction",
      "price_action","spread","slippage","funding_context","open_interest_context"
    ],
    indicatorsAreAuthority: false
  },
  execution: {
    signalContext: ["H1","M15","M5"],
    timing: "M1_AND_LIVE_FLOW",
    requireFreshQuote: true,
    requirePostDecisionRevalidation: true,
    requireOrderReconciliation: true,
    requireProtectionValidation: true,
    preferMakerOnPullback: true,
    allowMarketOnBreakout: true
  }
});

export function drawdownRiskMultiplier(ddPct = 0) {
  const dd = Math.max(0, Number(ddPct) || 0);
  let m = 1;
  for (const row of BYBIT_BTC_ONLY_CONFIG.risk.drawdownGovernor) {
    if (dd >= row.ddPct) m = row.riskMultiplier;
  }
  return m;
}

export function equityRiskUsd({ equityUsd, setupQuality = "BASE", ddPct = 0 } = {}) {
  const equity = Math.max(0, Number(equityUsd) || 0);
  if (!(equity > 0)) return 0;
  const r = BYBIT_BTC_ONLY_CONFIG.risk;
  const pct = setupQuality === "A_PLUS" ? r.maxInitialEntryRiskPct :
    setupQuality === "STRONG" ? r.strongEntryRiskPct : r.baseEntryRiskPct;
  return equity * (pct / 100) * drawdownRiskMultiplier(ddPct);
}

export function canAllocateRisk({ equityUsd, activeRiskUsd = 0, candidateRiskUsd = 0, aPlus = false, ddPct = 0 } = {}) {
  const equity = Math.max(0, Number(equityUsd) || 0);
  if (!(equity > 0)) return { ok: false, reason: "EQUITY_INVALID" };
  const mult = drawdownRiskMultiplier(ddPct);
  if (mult <= 0) return { ok: false, reason: "DRAWDOWN_NEW_RISK_LOCK" };
  const capPct = aPlus ? BYBIT_BTC_ONLY_CONFIG.risk.temporaryAPlusActiveRiskPct : BYBIT_BTC_ONLY_CONFIG.risk.maxActiveRiskPct;
  const capUsd = equity * capPct / 100;
  const projected = Math.max(0, Number(activeRiskUsd) || 0) + Math.max(0, Number(candidateRiskUsd) || 0);
  return projected <= capUsd + 1e-9
    ? { ok: true, capUsd, projectedRiskUsd: projected }
    : { ok: false, reason: "ACTIVE_RISK_BUDGET", capUsd, projectedRiskUsd: projected };
}
