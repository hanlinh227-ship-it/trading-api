// BYBIT-AUTO-1.9.6: 5m/15m anti-noise entry + anti-sweep management + market-entry reasoning hard-lock.
import {BYBIT_AUTO_VERSION} from "./bybit-runtime-contract.js";
export {BYBIT_AUTO_VERSION};
export const BYBIT_AUTO_CONFIG={
  startingCapitalUsd:50,
  leverage:15,
  maxLeverage:15,
  scanEverySec:60,
  maxOpenPositions:6,
  maxTradesPerDay:1000000000,
  risk:{
    mode:"CONTINUOUS_EQUITY_CURVE_FULL_CAPITAL_ALLOCATOR",
    baseBalanceUsd:50,
    balanceStepUsd:10,
    baseRiskUsd:5,
    baseMinEffectiveRiskUsd:0,
    effectiveRiskStepUsd:0,
    netProfitFloorUsd:0,
    executionCostBufferUsd:0,
    baseMinRewardUsd:0,
    baseRewardUsd:8,
    riskStepUsd:1,
    minRewardStepUsd:0,
    rewardStepUsd:1,
    maxRewardUsd:10,
    minRiskUsd:0,
    minRewardUsd:0,
    minRiskUtilizationPct:40,
    microAccountMinRiskUtilizationPct:20,
    smallAccountMinRiskUtilizationPct:30,
    riskCurveAnchorEquityUsd:25,
    riskCurveSmallPct:4,
    riskCurveLargeFloorPct:.75,
    riskCurveDecayPerDecade:1.0,
    slotMarginAnchorEquityUsd:5,
    slotMarginMaxPct:100,
    slotMarginFloorPct:20,
    slotMarginDecayPerDecade:1.25,
    targetRiskPctOfEquity:4,
    maxRiskPctOfEquity:4.5,
    maxRewardPctOfEquity:20,
    minNetEdgePctOfEquity:.15,
    minNetEdgeCostMultiple:1.50,
    takerFeeRate:.00055,
    slippageBps:2,
    fixedDollarFloorAuthority:false,
    maxTotalOpenRiskPct:18,
    maxMarginPerPositionPct:40,
    minFreeReservePct:15,
    maxPortfolioMarginPct:75,
    dailyLossCircuitPct:8,
    maxSameDirectionPositions:3,
    maxLossStreak:3,
    pauseMinutes:30,
    minRR:1.5,
    preferredRR:2,
    maxRR:3
  },
  filters:{
    minScore:66,
    minAtrPct:0,
    maxAtrPct:3.5
  },
  adaptive:{
    enabled:true,
    baseScore:70,
    minScore:66,
    maxScore:84,
    correlationSoft:.84,
    correlationHard:.94,
    autoPromote:false
  },
  management:{
    smartCutEnabled:true,
    smartCutMinAgeSec:900,
    smartCutPositiveMinAgeSec:1200
  }
};

const n=(env,k,d)=>{const v=Number(env?.[k]);return Number.isFinite(v)?v:d};
const b=(env,k,d)=>{const v=String(env?.[k]??"").trim().toLowerCase();if(!v)return d;return ["1","true","yes","on"].includes(v)};
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
export function bybitAutoConfig(env={}){
  const c=structuredClone(BYBIT_AUTO_CONFIG);
  c.startingCapitalUsd=Math.max(1,n(env,"BYBIT_STARTING_CAPITAL_USD",c.startingCapitalUsd));
  c.leverage=clamp(n(env,"BYBIT_AUTO_LEVERAGE",c.leverage),1,15);
  c.maxLeverage=clamp(n(env,"BYBIT_AUTO_MAX_LEVERAGE",c.maxLeverage),1,15);
  c.scanEverySec=Math.max(15,n(env,"BYBIT_AUTO_SCAN_EVERY_SEC",c.scanEverySec));
  c.maxOpenPositions=clamp(Math.round(n(env,"BYBIT_AUTO_MAX_OPEN_POSITIONS",c.maxOpenPositions)),2,10);
  c.maxTradesPerDay=Math.max(1,Math.round(n(env,"BYBIT_AUTO_MAX_TRADES_PER_DAY",c.maxTradesPerDay)));
  c.risk.targetRiskPctOfEquity=clamp(n(env,"BYBIT_AUTO_TARGET_RISK_PCT",c.risk.targetRiskPctOfEquity),.25,4.5);
  c.risk.maxRiskPctOfEquity=clamp(n(env,"BYBIT_AUTO_MAX_RISK_PCT",c.risk.maxRiskPctOfEquity),.5,4.5);
  c.risk.maxRewardPctOfEquity=clamp(n(env,"BYBIT_AUTO_MAX_REWARD_PCT",c.risk.maxRewardPctOfEquity),1,30);
  c.risk.maxTotalOpenRiskPct=clamp(n(env,"BYBIT_AUTO_MAX_TOTAL_OPEN_RISK_PCT",c.risk.maxTotalOpenRiskPct),8,24);
  c.risk.maxMarginPerPositionPct=clamp(n(env,"BYBIT_AUTO_MAX_MARGIN_PER_POSITION_PCT",c.risk.maxMarginPerPositionPct),20,50);
  c.risk.minFreeReservePct=clamp(n(env,"BYBIT_AUTO_MIN_FREE_RESERVE_PCT",c.risk.minFreeReservePct),10,30);
  c.risk.maxPortfolioMarginPct=clamp(n(env,"BYBIT_AUTO_MAX_PORTFOLIO_MARGIN_PCT",c.risk.maxPortfolioMarginPct),60,85);
  c.risk.dailyLossCircuitPct=clamp(n(env,"BYBIT_AUTO_DAILY_LOSS_CIRCUIT_PCT",c.risk.dailyLossCircuitPct),4,12);
  c.risk.maxSameDirectionPositions=clamp(Math.round(n(env,"BYBIT_AUTO_MAX_SAME_DIRECTION_POSITIONS",c.risk.maxSameDirectionPositions)),1,5);
  c.risk.minRiskUtilizationPct=clamp(n(env,"BYBIT_AUTO_MIN_RISK_UTILIZATION_PCT",c.risk.minRiskUtilizationPct),30,65);
  c.risk.microAccountMinRiskUtilizationPct=clamp(n(env,"BYBIT_AUTO_MICRO_MIN_RISK_UTILIZATION_PCT",c.risk.microAccountMinRiskUtilizationPct),15,c.risk.minRiskUtilizationPct);
  c.risk.smallAccountMinRiskUtilizationPct=clamp(n(env,"BYBIT_AUTO_SMALL_MIN_RISK_UTILIZATION_PCT",c.risk.smallAccountMinRiskUtilizationPct),c.risk.microAccountMinRiskUtilizationPct,c.risk.minRiskUtilizationPct);
  c.risk.minRR=clamp(n(env,"BYBIT_AUTO_MIN_RR",c.risk.minRR),1.5,3);
  c.risk.preferredRR=clamp(n(env,"BYBIT_AUTO_PREFERRED_RR",c.risk.preferredRR),c.risk.minRR,4);
  c.risk.maxRR=clamp(n(env,"BYBIT_AUTO_MAX_RR",c.risk.maxRR),c.risk.preferredRR,5);
  c.risk.maxLossStreak=clamp(Math.round(n(env,"BYBIT_AUTO_MAX_LOSS_STREAK",c.risk.maxLossStreak)),3,8);
  c.risk.pauseMinutes=clamp(n(env,"BYBIT_AUTO_LOSS_PAUSE_MINUTES",c.risk.pauseMinutes),5,240);
  c.filters.minScore=clamp(n(env,"BYBIT_AUTO_MIN_SCORE",c.filters.minScore),66,84);
  c.filters.minAtrPct=Math.max(0,n(env,"BYBIT_AUTO_MIN_ATR_PCT",c.filters.minAtrPct));
  c.filters.maxAtrPct=clamp(n(env,"BYBIT_AUTO_MAX_ATR_PCT",c.filters.maxAtrPct),.5,8);
  c.adaptive.enabled=b(env,"BYBIT_AUTO_ADAPTIVE_ENABLED",c.adaptive.enabled);
  c.adaptive.baseScore=clamp(n(env,"BYBIT_AUTO_ADAPTIVE_BASE_SCORE",c.adaptive.baseScore),66,84);
  c.adaptive.minScore=66;c.adaptive.maxScore=84;
  c.adaptive.correlationSoft=clamp(n(env,"BYBIT_AUTO_CORRELATION_SOFT",c.adaptive.correlationSoft),.5,.93);
  c.adaptive.correlationHard=clamp(n(env,"BYBIT_AUTO_CORRELATION_HARD",c.adaptive.correlationHard),Math.max(.85,c.adaptive.correlationSoft+.01),.99);
  c.adaptive.autoPromote=false;
  c.management.smartCutEnabled=b(env,"BYBIT_AUTO_SMART_CUT_ENABLED",c.management.smartCutEnabled);
  c.management.smartCutMinAgeSec=Math.max(900,n(env,"BYBIT_AUTO_SMART_CUT_MIN_AGE_SEC",c.management.smartCutMinAgeSec));
  c.management.smartCutPositiveMinAgeSec=Math.max(1200,n(env,"BYBIT_AUTO_SMART_CUT_POSITIVE_MIN_AGE_SEC",c.management.smartCutPositiveMinAgeSec));
  c.risk.fixedDollarFloorAuthority=false;
  return c;
}

export function bybitExecutionMode(env={}){
  if(String(env.BYBIT_AUTO_DEMO||"").toLowerCase()==="true")return "LIVE";
  return String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER";
}
