// ============================================================================
// NON_PRODUCTION / QUARANTINED — see docs/ai-coengineer/DECISIONS.md DECISION-005
// ============================================================================

export const BINANCE20_VERSION="BF20-1.4.0";
export const BINANCE20_CONFIG={
  startingCapitalUsd:50,
  symbols:["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"],
  leverage:3,maxLeverage:5,
  scanEverySec:60,maxOpenPositions:3,maxTradesPerDay:24,
  risk:{
    mode:"EQUITY_LADDER",
    baseRiskUsd:10.00,
    equityStepUsd:50.00,
    riskStepUsd:10.00,
    maxRiskPctOfEquity:25.00,
    dailyStopPct:20.00,
    maxLossStreak:3,
    pauseMinutes:30,
    minRR:1.00,
    preferredRR:2.00,
    maxRR:3.00,
    targetRR:2.00,
    maxSameDirectionPositions:2
  },
  filters:{minScore:72,maxSpreadBps:8,maxChaseAtr:.55,minAtrPct:.08,maxAtrPct:2.8},
  execution:{liveDefault:false,recvWindow:5000,cooldownSec:90,marginType:"ISOLATED"}
};
export function binance20Config(env={}){
  const c=structuredClone(BINANCE20_CONFIG),n=(k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
  c.startingCapitalUsd=Math.max(10,n("BINANCE_STARTING_CAPITAL_USD",c.startingCapitalUsd));
  c.leverage=Math.max(1,Math.min(c.maxLeverage,Math.round(n("BINANCE20_LEVERAGE",c.leverage))));
  c.risk.baseRiskUsd=Math.max(1,n("BINANCE_BASE_RISK_USD",c.risk.baseRiskUsd));
  c.risk.equityStepUsd=Math.max(10,n("BINANCE_EQUITY_STEP_USD",c.risk.equityStepUsd));
  c.risk.riskStepUsd=Math.max(1,n("BINANCE_RISK_STEP_USD",c.risk.riskStepUsd));
  c.risk.maxRiskPctOfEquity=Math.max(5,Math.min(50,n("BINANCE_MAX_RISK_PCT_OF_EQUITY",c.risk.maxRiskPctOfEquity)));
  c.risk.dailyStopPct=Math.max(5,Math.min(50,n("BINANCE_DAILY_STOP_PCT",c.risk.dailyStopPct)));
  c.risk.minRR=Math.max(1,Math.min(2,n("BINANCE_MIN_RR",c.risk.minRR)));
  c.risk.preferredRR=Math.max(c.risk.minRR,Math.min(4,n("BINANCE_PREFERRED_RR",c.risk.preferredRR)));
  c.risk.maxRR=Math.max(c.risk.preferredRR,Math.min(5,n("BINANCE_MAX_RR",c.risk.maxRR)));
  c.maxOpenPositions=Math.max(1,Math.min(3,Math.round(n("BINANCE_MAX_OPEN_POSITIONS",c.maxOpenPositions))));
  c.risk.maxSameDirectionPositions=Math.max(1,Math.min(2,Math.round(n("BINANCE_MAX_SAME_DIRECTION_POSITIONS",c.risk.maxSameDirectionPositions))));
  c.execution.liveDefault=String(env.BINANCE20_AUTO_EXECUTE||"").toLowerCase()==="true";
  c.symbols=String(env.BINANCE20_SYMBOLS||c.symbols.join(",")).split(",").map(x=>x.trim().toUpperCase()).filter(Boolean).slice(0,8);
  return c;
}
