export const BYBIT_MARKET_ENTRY_REASONING_VERSION="BYBIT_MARKET_ENTRY_REASONING_V1";
export const BYBIT_MARKET_ENTRY_REASONING_CHECKPOINT="docs/checkpoints/BYBIT_GPT_MARKET_ENTRY_REASONING_20260828.md";

export const BYBIT_MARKET_ENTRY_REASONING={
  provenance:"CLAUDE_COARCHITECT_GPT_PRIMARY_ENGINEER_FUSION",
  authority:"SOURCE_FIRST_NO_BEAUTIFY",
  signalTimeframe:"5m",
  contextTimeframe:"15m",
  closedCandlesOnly:true,
  m1DecisionAuthority:false,
  liveQuoteRequired:true,
  staleQuoteAllowed:false,
  frequencyPreservation:{
    noNewEntryFilters:true,
    noHiddenSizingRejects:true,
    spreadDoublePenalty:false,
    softCorrelationPolicy:"SIZE_ONLY",
    hardCorrelationPolicy:"REJECT",
    candidateFallbackSameCycle:true
  },
  correlation:{soft:0.84,hard:0.94,minSizeMultiplier:0.5},
  execution:{
    sameDirectionPreflight:true,
    duplicateResistantEntryIds:true,
    protectionRequired:true,
    postAiQuoteRevalidation:true
  },
  designPriorities:["REAL_EDGE","TAIL_RISK_REDUCTION","FREQUENCY_PRESERVATION","EXECUTION_ROBUSTNESS"],
  rejectComplexityWithoutEdge:true,
  riskAuthority:"bybit-auto-config.js",
  decisionOutputs:["MARKET_LONG","MARKET_SHORT","NO_MARKET_ENTRY"],
  noFabricatedPrice:true,
  noFabricatedBacktest:true,
  autoPromoteLearning:false
};
