// ============================================================================
// NON_PRODUCTION / QUARANTINED — see docs/ai-coengineer/DECISIONS.md DECISION-005
// ============================================================================

export const BINANCE20_VERSION="BF20-1.2.0";
export const BINANCE20_CONFIG={
  startingCapitalUsd:50,
  symbols:["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"],
  leverage:3,maxLeverage:5,
  scanEverySec:60,maxOpenPositions:3,maxTradesPerDay:24,
  risk:{
    perTradePct:1.00,
    minRiskUsd:.25,
    maxRiskPct:1.25,
    dailyStopPct:5.00,
    maxLossStreak:3,
    pauseMinutes:30,
    minRR:1.20,
    targetRR:1.55,
    maxSameDirectionPositions:2
  },
  filters:{minScore:72,maxSpreadBps:8,maxChaseAtr:.55,minAtrPct:.08,maxAtrPct:2.8},
  execution:{liveDefault:false,recvWindow:5000,cooldownSec:90,marginType:"ISOLATED"}
};
export function binance20Config(env={}){
  const c=structuredClone(BINANCE20_CONFIG),n=(k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
  c.startingCapitalUsd=Math.max(10,n("BINANCE_STARTING_CAPITAL_USD",c.startingCapitalUsd));
  c.leverage=Math.max(1,Math.min(c.maxLeverage,Math.round(n("BINANCE20_LEVERAGE",c.leverage))));
  c.risk.perTradePct=Math.max(.25,Math.min(c.risk.maxRiskPct,n("BINANCE_RISK_PER_TRADE_PCT",c.risk.perTradePct)));
  c.risk.minRiskUsd=Math.max(.05,n("BINANCE_MIN_RISK_USD",c.risk.minRiskUsd));
  c.risk.dailyStopPct=Math.max(1,Math.min(15,n("BINANCE_DAILY_STOP_PCT",c.risk.dailyStopPct)));
  c.maxOpenPositions=Math.max(1,Math.min(3,Math.round(n("BINANCE_MAX_OPEN_POSITIONS",c.maxOpenPositions))));
  c.risk.maxSameDirectionPositions=Math.max(1,Math.min(2,Math.round(n("BINANCE_MAX_SAME_DIRECTION_POSITIONS",c.risk.maxSameDirectionPositions))));
  c.execution.liveDefault=String(env.BINANCE20_AUTO_EXECUTE||"").toLowerCase()==="true";
  c.symbols=String(env.BINANCE20_SYMBOLS||c.symbols.join(",")).split(",").map(x=>x.trim().toUpperCase()).filter(Boolean).slice(0,8);
  return c;
}
