export const PERSONAL_GOLD_VERSION="PGOLD-1.0.0";

export const GOLD_CONFIG={
  symbol:"XAU/USD",
  brokerSymbol:"XAUUSD",
  scanIntervalSec:60,
  maxQuoteAgeSec:75,
  candles:{m1:180,m5:180},
  risk:{
    perTradePct:0.15,
    reducedRiskPct:0.08,
    dailyStopPct:1.50,
    sessionStopPct:0.75,
    maxConsecutiveLosses:3,
    lossPauseMinutes:30,
    maxTradesPerDay:18,
    maxOpenPositions:1,
    minRR:1.25,
    targetRR:1.65,
  },
  execution:{
    defaultLive:false,
    maxSlippageUsd:0.35,
    entryCooldownSec:120,
    duplicateSetupTtlSec:300,
  },
  filters:{
    minAtrPct:0.018,
    maxAtrPct:0.45,
    maxSpreadUsd:0.45,
    chaseAtr:0.48,
    m1ImpulseAtr:0.22,
  },
  strategyWeights:{
    TREND_CONTINUATION:1.00,
    BREAKOUT_RETEST:0.96,
    LIQUIDITY_SWEEP:0.92,
  },
};

export function personalGoldConfig(env={}){
  const cfg=structuredClone(GOLD_CONFIG);
  const num=(k,d)=>{const n=Number(env[k]);return Number.isFinite(n)?n:d;};
  cfg.risk.perTradePct=num("PERSONAL_GOLD_RISK_PCT",cfg.risk.perTradePct);
  cfg.risk.dailyStopPct=num("PERSONAL_GOLD_DAILY_STOP_PCT",cfg.risk.dailyStopPct);
  cfg.risk.maxTradesPerDay=Math.max(1,Math.round(num("PERSONAL_GOLD_MAX_TRADES",cfg.risk.maxTradesPerDay)));
  cfg.filters.maxSpreadUsd=num("PERSONAL_GOLD_MAX_SPREAD_USD",cfg.filters.maxSpreadUsd);
  cfg.execution.defaultLive=String(env.PERSONAL_GOLD_AUTO_EXECUTE||"").toLowerCase()==="true";
  return cfg;
}
