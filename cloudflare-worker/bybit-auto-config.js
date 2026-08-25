export const BYBIT_AUTO_VERSION="BYBIT-AUTO-1.2.0";
export const BYBIT_AUTO_CONFIG={
  startingCapitalUsd:50,
  leverage:3,
  maxLeverage:5,
  scanEverySec:60,
  maxOpenPositions:3,
  maxTradesPerDay:1000000000,
  risk:{
    mode:"BALANCE_DOLLAR_LADDER",
    baseBalanceUsd:50,
    balanceStepUsd:10,
    baseRiskUsd:5,
    baseRewardUsd:10,
    riskStepUsd:1,
    rewardStepUsd:1,
    maxRiskPctOfEquity:25,
    maxTotalOpenRiskPct:30,
    marginUsePct:80,
    minRR:1,
    preferredRR:2,
    maxRR:3,
    maxLossStreak:3,
    pauseMinutes:30,
    maxSameDirectionPositions:2
  },
  filters:{minScore:70,maxSpreadBps:9,maxChaseAtr:.60,minAtrPct:.08,maxAtrPct:2.8},
  execution:{recvWindow:5000,cooldownSec:180,positionIdx:0}
};
const n=(env,k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
export function bybitAutoConfig(env={}){
  const c=structuredClone(BYBIT_AUTO_CONFIG);
  c.startingCapitalUsd=Math.max(10,n(env,"BYBIT_STARTING_CAPITAL_USD",c.startingCapitalUsd));
  c.leverage=Math.max(1,Math.min(c.maxLeverage,Math.round(n(env,"BYBIT_AUTO_LEVERAGE",c.leverage))));
  c.risk.baseBalanceUsd=Math.max(10,n(env,"BYBIT_BASE_BALANCE_USD",c.risk.baseBalanceUsd));
  c.risk.balanceStepUsd=Math.max(1,n(env,"BYBIT_BALANCE_STEP_USD",c.risk.balanceStepUsd));
  c.risk.baseRiskUsd=Math.max(1,n(env,"BYBIT_BASE_RISK_USD",c.risk.baseRiskUsd));
  c.risk.baseRewardUsd=Math.max(1,n(env,"BYBIT_BASE_REWARD_USD",c.risk.baseRewardUsd));
  c.risk.riskStepUsd=Math.max(.1,n(env,"BYBIT_RISK_STEP_USD",c.risk.riskStepUsd));
  c.risk.rewardStepUsd=Math.max(.1,n(env,"BYBIT_REWARD_STEP_USD",c.risk.rewardStepUsd));
  c.risk.maxRiskPctOfEquity=Math.max(5,Math.min(50,n(env,"BYBIT_MAX_RISK_PCT_OF_EQUITY",c.risk.maxRiskPctOfEquity)));
  c.risk.maxTotalOpenRiskPct=Math.max(5,Math.min(60,n(env,"BYBIT_MAX_TOTAL_OPEN_RISK_PCT",c.risk.maxTotalOpenRiskPct)));
  c.risk.marginUsePct=Math.max(30,Math.min(85,n(env,"BYBIT_MARGIN_USE_PCT",c.risk.marginUsePct)));
  c.risk.minRR=Math.max(1,Math.min(2,n(env,"BYBIT_MIN_RR",c.risk.minRR)));
  c.risk.preferredRR=Math.max(c.risk.minRR,Math.min(4,n(env,"BYBIT_PREFERRED_RR",c.risk.preferredRR)));
  c.risk.maxRR=Math.max(c.risk.preferredRR,Math.min(5,n(env,"BYBIT_MAX_RR",c.risk.maxRR)));
  c.maxOpenPositions=Math.max(1,Math.min(3,Math.round(n(env,"BYBIT_MAX_OPEN_POSITIONS",c.maxOpenPositions))));
  c.maxTradesPerDay=1000000000;
  c.risk.maxLossStreak=Math.max(3,Math.round(n(env,"BYBIT_MAX_LOSS_STREAK_INTERNAL",c.risk.maxLossStreak)));
  c.risk.pauseMinutes=Math.max(30,Math.round(n(env,"BYBIT_LOSS_PAUSE_MINUTES_INTERNAL",c.risk.pauseMinutes)));
  c.execution.cooldownSec=Math.max(180,Math.round(n(env,"BYBIT_ENTRY_COOLDOWN_SEC",c.execution.cooldownSec)));
  return c;
}
export function bybitExecutionMode(env={}){
  if(String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true")return "LIVE";
  return "PAPER";
}
export function bybitCredentials(env={}){
  return {
    apiKey:env.BYBIT_AUTO_API_KEY||env.HYRO_BYBIT_LIVE_API_KEY||"",
    apiSecret:env.BYBIT_AUTO_API_SECRET||env.HYRO_BYBIT_LIVE_API_SECRET||"",
    source:env.BYBIT_AUTO_API_KEY&&env.BYBIT_AUTO_API_SECRET?"BYBIT_AUTO":"HYRO_BYBIT_LIVE_FALLBACK"
  };
}
