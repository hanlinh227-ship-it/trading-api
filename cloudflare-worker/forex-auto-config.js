export const FOREX_AUTO_VERSION="FOREX-AUTO-0.1.0-PAPER";
export const FOREX_AUTO_MODE="PAPER_ONLY";

export const FOREX_AUTO_CONFIG={
  brokerProfile:"THE5ERS_HIGH_STAKES",
  executionTerminal:"MT5_WINDOWS",
  aiProviders:["chatgpt","claude","deepseek"],
  universe:["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURJPY","GBPJPY","EURGBP","XAUUSD"],
  scanEverySec:60,
  maxOpenPositions:3,
  maxSameCurrencyExposure:2,
  rules:{
    maxDailyLossPct:5,
    maxTotalLossPct:10,
    internalDailyStopPct:1.25,
    emergencyDailyStopPct:1.75,
    profitableDayPct:.5,
    minProfitableDays:3,
    maxInactivityDays:30,
    newsBlockBeforeSec:180,
    newsBlockAfterSec:180,
    prohibitNewsBracketing:true,
    prohibitHft:true,
    prohibitArbitrage:true,
    prohibitMartingale:true,
    prohibitGridRecovery:true,
    prohibitCopyTrading:true,
    requireOwnedSource:true
  },
  risk:{
    normalRiskPct:.30,
    premiumRiskPct:.45,
    hardMaxRiskPct:.50,
    maxTotalOpenRiskPct:1.00,
    minRR:1.5,
    preferredRR:2.0,
    minStopAtr:1.20,
    normalStopAtr:1.60,
    maxStopAtr:3.20,
    structureBufferAtr:.20,
    maxSpreadPips:{FX:2.2,JPY:2.5,XAU:35},
    maxLossStreak:3,
    lossPauseMinutes:60,
    noAveragingDown:true,
    noMartingale:true
  },
  management:{
    breakEvenAtR:1.0,
    profitLockAtR:1.35,
    trailAtR:1.60,
    requireStructureConfirmation:true,
    smartCutEnabled:true,
    smartCutMinAgeSec:300
  },
  ai:{
    requireAllThree:true,
    finalDecisionProvider:"chatgpt",
    minFinalConfidence:72,
    claudeRole:"MARKET_CONTEXT_AND_RISK_CRITIC",
    deepseekRole:"TECHNICAL_EXECUTION_CRITIC",
    chatgptRole:"LEAD_TRADER_FINAL_DECISION",
    noAiOverrideOfHardRules:true
  },
  execution:{
    liveEnabled:false,
    requireBridgeToken:true,
    decisionTtlSec:75,
    maxClockSkewSec:30,
    duplicateCooldownSec:300,
    defaultSlippagePoints:20,
    magicNumber:560501
  }
};

export function forexAutoConfig(env={}){
  const c=structuredClone(FOREX_AUTO_CONFIG);
  c.execution.liveEnabled=String(env.FOREX_AUTO_LIVE||"").toLowerCase()==="true";
  c.risk.normalRiskPct=Math.max(.1,Math.min(.5,Number(env.FOREX_NORMAL_RISK_PCT||c.risk.normalRiskPct)));
  c.risk.premiumRiskPct=Math.max(c.risk.normalRiskPct,Math.min(.5,Number(env.FOREX_PREMIUM_RISK_PCT||c.risk.premiumRiskPct)));
  c.risk.hardMaxRiskPct=.5;
  c.risk.maxTotalOpenRiskPct=Math.max(.5,Math.min(1.25,Number(env.FOREX_MAX_OPEN_RISK_PCT||c.risk.maxTotalOpenRiskPct)));
  c.ai.minFinalConfidence=Math.max(65,Math.min(90,Number(env.FOREX_MIN_AI_CONFIDENCE||c.ai.minFinalConfidence)));
  return c;
}
