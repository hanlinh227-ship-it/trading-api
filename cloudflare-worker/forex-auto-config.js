export const FOREX_AUTO_VERSION="FOREX-AUTO-0.6.1-PURE-AI-FAST";
export const FOREX_AUTO_MODE="AUTONOMOUS_2AI_PAPER";

export const FOREX_AUTO_CONFIG={
  branchId:"FOREX_THE5ERS_PURE_AI",
  brokerProfile:"THE5ERS_HIGH_STAKES",
  executionTerminal:"MT5_WINDOWS",
  tradingStyle:"PURE_AI_DISCRETIONARY_INTRADAY_FAST_LOOP",
  aiProviders:["chatgpt","claude"],
  universe:["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURJPY","GBPJPY","EURGBP","XAUUSD"],
  scanEverySec:5,
  mt5SnapshotEverySec:3,
  positionManagementEverySec:5,
  maxOpenPositions:null,
  rules:{
    maxDailyLossPct:5,maxTotalLossPct:10,internalDailyStopPct:4.0,projectedDailyStopPct:4.0,
    officialNewsBlockBeforeSec:120,officialNewsBlockAfterSec:120,newsCalendarFailClosed:true,
    prohibitNewsBracketing:true,prohibitHft:true,prohibitTickScalping:true,prohibitArbitrage:true,
    prohibitLatencyArbitrage:true,prohibitReverseArbitrage:true,prohibitHedgeArbitrage:true,
    prohibitEmulators:true,prohibitMartingale:true,prohibitGridRecovery:true,prohibitCopyTrading:true,
    requireVisibleBrokerStop:true,requireOwnedSource:true,
    alternateTradeSide:true,alternationScope:"ACCOUNT_FILLED_ENTRY_SEQUENCE",alternationNoForceEntry:true
  },
  dailyObjective:{enabled:true,minProfitPct:.50,measurement:"BROKER_DAY_START_EQUITY",requireAboveThreshold:true,continueScanningAfterReached:true,neverForceEntry:true,neverIncreaseRiskToChase:true,reportMissAtDayClose:true},
  target:{enabled:false,mode:"USER_SET_RUNTIME_TARGET_ONLY",requiredForLive:false,targetUsd:null,targetPct:null,targetDays:null,cycleId:"USER_SET",stopNewEntriesWhenReached:false,neverIncreaseRiskToChaseTarget:true,deadlineIsSoft:true,userAuthorityRequired:true,allowHardcodedTarget:false},
  risk:{aiChoosesRequestedRiskPct:true,defaultRequestedRiskPct:.35,minExecutableRiskPct:.10,hardMaxRiskPct:1.00,maxTotalOpenRiskPct:3.75,minRR:1.5,preferredRR:2.0,noAveragingDown:true,noMartingale:true},
  margin:{minFreeMarginPctOfEquity:20,maxUsedMarginPctOfEquity:80,minMarginLevelPct:200,requireBrokerMarginMetrics:true,preTradeMarginCheck:true},
  marketData:{maxQuoteAgeSec:12,requireH4:true,requireM5:true,requireM15:true,requireH1:true,refreshBrokerQuoteBeforeExecution:true,rejectStaleDecision:true},
  management:{authority:"AI_ONLY",deterministicBreakEven:false,deterministicProfitLock:false,deterministicTrailing:false,deterministicSmartCut:false,aiMayHold:true,aiMayClose:true,aiMayModifySlTp:true,hardProtectionCannotBeRemoved:true},
  ai:{authority:"PURE_AI_ENTRY_AND_POSITION_MANAGEMENT",requireAllTwo:true,consensusPassesRequired:2,claudeRole:"INDEPENDENT_DISCRETIONARY_TECHNICAL_AND_MACRO_TRADER",chatgptRole:"INDEPENDENT_DISCRETIONARY_TECHNICAL_AND_MACRO_TRADER",chatgptWebResearch:true,claudeWebResearch:true,requireCurrentEconomicContext:true,requireTechnicalReasoning:true,economicResearchIsContextOnly:true,brokerQuoteRemainsExecutionAuthority:true,rawMt5CandlesArePrimaryEvidence:true,ruleBasedSignalAuthority:false,precomputedScoreAuthority:false,indicatorGateAuthority:false,confidenceGateAuthority:false,automatedSetupRankingAuthority:false,requireIndependentReviews:true,noAiOverrideOfHardRules:true,noForcedTrade:true,enforceAlternatingFilledSide:true,learningIsContextOnly:true,maximizeReasoningBudget:true,quotaCooldownHours:5,openAiMaxOutputTokens:12000,claudeMaxOutputTokens:12000},
  learning:{enabled:true,mode:"MEMORY_CONTEXT_ONLY",perSymbol:true,perSetup:true,learnFromClosedTradesOnly:true,recentWindow:12,mayAutoChangeRisk:false,mayAutoChangeScore:false,mayAutoRejectSetup:false,mayChangeHardRules:false,mayChangeDailyLossLimit:false,mayChangeNewsRules:false,mayChangeMinRR:false,autoModifySourceCode:false},
  execution:{liveEnabled:false,requireBridgeToken:true,decisionTtlSec:12,maxClockSkewSec:8,duplicateCooldownSec:20,defaultSlippagePoints:20,maxEntryDriftAtr:.20,magicNumber:560601}
};

export function forexAutoConfig(env={}){
  const c=structuredClone(FOREX_AUTO_CONFIG);
  c.execution.liveEnabled=String(env.FOREX_AUTO_LIVE||"").toLowerCase()==="true";
  c.risk.hardMaxRiskPct=1.0;
  c.risk.maxTotalOpenRiskPct=Math.max(2.0,Math.min(3.9,Number(env.FOREX_MAX_OPEN_RISK_PCT||c.risk.maxTotalOpenRiskPct)));
  c.margin.minFreeMarginPctOfEquity=Math.max(15,Math.min(40,Number(env.FOREX_MIN_FREE_MARGIN_PCT||c.margin.minFreeMarginPctOfEquity)));
  c.margin.minMarginLevelPct=Math.max(150,Math.min(500,Number(env.FOREX_MIN_MARGIN_LEVEL_PCT||c.margin.minMarginLevelPct)));
  c.ai.quotaCooldownHours=Math.max(1,Math.min(12,Number(env.FOREX_AI_QUOTA_COOLDOWN_HOURS||5)));
  c.ai.openAiMaxOutputTokens=Math.max(1000,Math.min(32000,Number(env.FOREX_OPENAI_MAX_OUTPUT_TOKENS||12000)));
  c.ai.claudeMaxOutputTokens=Math.max(1000,Math.min(32000,Number(env.FOREX_CLAUDE_MAX_OUTPUT_TOKENS||12000)));
  c.dailyObjective.enabled=true;c.dailyObjective.minProfitPct=.50;
  c.target.enabled=false;c.target.requiredForLive=false;c.target.stopNewEntriesWhenReached=false;
  const enabled=String(env.FOREX_USER_TARGET_ENABLED||"").toLowerCase()==="true";
  if(enabled){const targetUsd=Number(env.FOREX_USER_TARGET_USD||0),targetPct=Number(env.FOREX_USER_TARGET_PCT||0),targetDays=Number(env.FOREX_USER_TARGET_DAYS||0),cycleId=String(env.FOREX_USER_TARGET_CYCLE_ID||"USER_SET");if((targetUsd>0||targetPct>0)&&targetDays>0){c.target.enabled=true;c.target.targetUsd=targetUsd>0?targetUsd:null;c.target.targetPct=targetPct>0?targetPct:null;c.target.targetDays=targetDays;c.target.cycleId=cycleId;}}
  return c;
}
