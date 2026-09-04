export const BYBIT_UI_SCHEMA_VERSION='BYBIT_UI_SCHEMA_V1';
export const BYBIT_UI_ROUTES=Object.freeze({
  bootstrap:'/bybit/ui/bootstrap',
  snapshot:'/bybit/ui/snapshot',
  health:'/bybit/health',
  entryHealth:'/bybit/entry-health',
  runtimeContract:'/runtime/contract'
});
export const BYBIT_UI_CAPABILITIES=Object.freeze({
  readOnlyBootstrap:true,
  authenticatedReadOnlySnapshot:true,
  liveAccountSummary:true,
  activePositions:true,
  protectedRiskSlots:true,
  candidateRanking:true,
  candidateDecisions:true,
  profitObjective:true,
  leveragePolicy:true,
  riskPolicy:true,
  executionWriteControlsExposedToUi:false,
  realizedProfitGuaranteed:false
});
