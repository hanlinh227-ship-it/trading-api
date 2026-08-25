// BYBIT-AUTO-1.6.3: balanced effective-risk sizing + complete trade-action notification policy.
export const BYBIT_AUTO_VERSION="BYBIT-AUTO-1.6.3";
export const BYBIT_AUTO_CONFIG={
  startingCapitalUsd:50,
  leverage:10,
  maxLeverage:10,
  scanEverySec:60,
  maxOpenPositions:3,
  maxTradesPerDay:1000000000,
  risk:{
    mode:"BALANCED_EFFECTIVE_RISK_BAND_ALLOCATOR",
    baseBalanceUsd:50,
    balanceStepUsd:10,
    baseRiskUsd:5,
    baseMinEffectiveRiskUsd:2,
    effectiveRiskStepUsd:.5,
    baseMinRewardUsd:1,
    baseRewardUsd:5,
    riskStepUsd:1,
    minRewardStepUsd:.5,
    rewardStepUsd:1,
    minRiskUsd:.5,
    minRewardUsd:.5,
    maxRiskPctOfEquity:10,
    maxTotalOpenRiskPct:20,
    maxMarginPerPositionPct:40,
    minFreeReservePct:20,
    feeBufferPct:5,
    maxPortfolioMarginPct:80,
    minRR:1,
    preferredRR:2,
    maxRR:5,
    maxLossStreak:3,
    pauseMinutes:30,
    maxSameDirectionPositions:2,
    smartCutEnabled:true,
    smartCutMinAgeSec:180,
    smartCutScore:7,
    smartCutConfirmations:2
  },
  adaptive:{
    enabled:true,
    baseScore:70,
    minScore:68,
    maxScore:85,
    minLearningSamples:10,
    fullLearningSamples:80,
    correlationSoft:0.80,
    correlationHard:0.90,
    regimeGate:true,
    perSymbolEdge:true,
    netExpectancy:true,
    exitProfiles:["DEFENSIVE","BALANCED","TREND_RUNNER"],
    autoPromote:false
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
  c.risk.baseRiskUsd=Math.max(.5,n(env,"BYBIT_BASE_RISK_USD",c.risk.baseRiskUsd));
  c.risk.baseMinEffectiveRiskUsd=Math.max(.5,n(env,"BYBIT_BASE_MIN_EFFECTIVE_RISK_USD",c.risk.baseMinEffectiveRiskUsd));
  c.risk.effectiveRiskStepUsd=Math.max(.1,n(env,"BYBIT_EFFECTIVE_RISK_STEP_USD",c.risk.effectiveRiskStepUsd));
  c.risk.baseMinRewardUsd=Math.max(.5,n(env,"BYBIT_BASE_MIN_REWARD_USD",c.risk.baseMinRewardUsd));
  c.risk.baseRewardUsd=Math.max(c.risk.baseMinRewardUsd,n(env,"BYBIT_BASE_REWARD_USD",c.risk.baseRewardUsd));
  c.risk.riskStepUsd=Math.max(.1,n(env,"BYBIT_RISK_STEP_USD",c.risk.riskStepUsd));
  c.risk.minRewardStepUsd=Math.max(.1,n(env,"BYBIT_MIN_REWARD_STEP_USD",c.risk.minRewardStepUsd));
  c.risk.rewardStepUsd=Math.max(.1,n(env,"BYBIT_REWARD_STEP_USD",c.risk.rewardStepUsd));
  c.risk.minRiskUsd=Math.max(.25,n(env,"BYBIT_MIN_RISK_USD",c.risk.minRiskUsd));
  c.risk.minRewardUsd=Math.max(.25,n(env,"BYBIT_MIN_REWARD_USD",c.risk.minRewardUsd));
  c.risk.maxRiskPctOfEquity=Math.max(4,Math.min(12,n(env,"BYBIT_MAX_RISK_PCT_OF_EQUITY",c.risk.maxRiskPctOfEquity)));
  c.risk.maxTotalOpenRiskPct=Math.max(10,Math.min(25,n(env,"BYBIT_MAX_TOTAL_OPEN_RISK_PCT",c.risk.maxTotalOpenRiskPct)));
  c.risk.maxMarginPerPositionPct=Math.max(15,Math.min(45,n(env,"BYBIT_MAX_MARGIN_PER_POSITION_PCT",c.risk.maxMarginPerPositionPct)));
  c.risk.minFreeReservePct=Math.max(15,Math.min(40,n(env,"BYBIT_MIN_FREE_RESERVE_PCT",c.risk.minFreeReservePct)));
  c.risk.feeBufferPct=Math.max(2,Math.min(12,n(env,"BYBIT_FEE_BUFFER_PCT",c.risk.feeBufferPct)));
  c.risk.maxPortfolioMarginPct=Math.max(55,Math.min(85,n(env,"BYBIT_MAX_PORTFOLIO_MARGIN_PCT",c.risk.maxPortfolioMarginPct)));
  c.risk.minRR=Math.max(1,Math.min(2,n(env,"BYBIT_MIN_RR",c.risk.minRR)));
  c.risk.preferredRR=Math.max(c.risk.minRR,Math.min(5,n(env,"BYBIT_PREFERRED_RR",c.risk.preferredRR)));
  c.risk.maxRR=Math.max(c.risk.preferredRR,Math.min(6,n(env,"BYBIT_MAX_RR",c.risk.maxRR)));
  c.maxOpenPositions=Math.max(1,Math.min(3,Math.round(n(env,"BYBIT_MAX_OPEN_POSITIONS",c.maxOpenPositions))));
  c.maxTradesPerDay=1000000000;
  c.risk.maxLossStreak=Math.max(3,Math.round(n(env,"BYBIT_MAX_LOSS_STREAK_INTERNAL",c.risk.maxLossStreak)));
  c.risk.pauseMinutes=Math.max(30,Math.round(n(env,"BYBIT_LOSS_PAUSE_MINUTES_INTERNAL",c.risk.pauseMinutes)));
  c.risk.smartCutEnabled=String(env.BYBIT_DISCRETIONARY_CUT_ENABLED??String(c.risk.smartCutEnabled)).toLowerCase()==="true";
  c.risk.smartCutMinAgeSec=Math.max(180,Math.round(n(env,"BYBIT_CUT_MIN_AGE_SEC",c.risk.smartCutMinAgeSec)));
  c.risk.smartCutScore=Math.max(6,Math.min(9,Math.round(n(env,"BYBIT_SMART_CUT_SCORE",c.risk.smartCutScore))));
  c.risk.smartCutConfirmations=Math.max(2,Math.min(3,Math.round(n(env,"BYBIT_SMART_CUT_CONFIRMATIONS",c.risk.smartCutConfirmations))));
  c.adaptive.enabled=String(env.BYBIT_ADAPTIVE_EDGE_ENABLED??String(c.adaptive.enabled)).toLowerCase()==="true";
  c.adaptive.baseScore=Math.max(68,Math.min(78,Math.round(n(env,"BYBIT_ADAPTIVE_BASE_SCORE",c.adaptive.baseScore))));
  c.adaptive.correlationSoft=Math.max(.70,Math.min(.90,n(env,"BYBIT_CORRELATION_SOFT",c.adaptive.correlationSoft)));
  c.adaptive.correlationHard=Math.max(c.adaptive.correlationSoft+.05,Math.min(.97,n(env,"BYBIT_CORRELATION_HARD",c.adaptive.correlationHard)));
  c.adaptive.autoPromote=false;
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
