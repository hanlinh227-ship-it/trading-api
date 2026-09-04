export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_BTC_RUNTIME_CONTRACT_V10_ADAPTIVE_CAPITAL_CONTROL';
export const BYBIT_AUTO_VERSION='BYBIT-BTC-STATEFLOW-2.5';
export const BYBIT_EXECUTION_AUTHORITY='BYBIT_BTC_ONLY';
export const BYBIT_PRIVATE_TRANSPORT='VPS_BYBIT_PRIVATE_PROXY';
export const BYBIT_MARKET_TRANSPORT='VPS_BYBIT_MARKET_PROXY';
export const BYBIT_HEALTH_ROUTE='/bybit/health';
export const TELEGRAM_HUB_ID='BTC_ONLY_TRADING_HUB';
export const LEGACY_SIGNAL_RUNTIME_DISABLED=true;
export const LEGACY_BYBIT_MULTI_COIN_DISABLED=true;
export const LEGACY_FOREX_DISABLED=true;
export const LEGACY_MEME_DISABLED=true;
export const LEGACY_AI_COUNCIL_DISABLED=true;

export const BYBIT_RUNTIME_CONTRACT={
  version:BYBIT_RUNTIME_CONTRACT_VERSION,autoVersion:BYBIT_AUTO_VERSION,executionAuthority:BYBIT_EXECUTION_AUTHORITY,
  privateTransport:BYBIT_PRIVATE_TRANSPORT,marketTransport:BYBIT_MARKET_TRANSPORT,healthRoute:BYBIT_HEALTH_ROUTE,telegramHub:TELEGRAM_HUB_ID,
  legacySignalRuntimeDisabled:LEGACY_SIGNAL_RUNTIME_DISABLED,legacyBybitMultiCoinDisabled:LEGACY_BYBIT_MULTI_COIN_DISABLED,legacyForexDisabled:LEGACY_FOREX_DISABLED,legacyMemeDisabled:LEGACY_MEME_DISABLED,legacyAiCouncilDisabled:LEGACY_AI_COUNCIL_DISABLED,
  symbol:'BTCUSDT',market:'LINEAR_PERPETUAL',strategyAuthority:'STATE_FIRST_STRUCTURE_FLOW_LIQUIDITY_DERIVATIVES',migrationState:'BTC_ONLY_COMPLETE',
  autonomous:true,eventDriven:true,decisionAuthority:'VPS_WS_MARKET_STATE_CHANGE',entryTriggerAuthority:'VPS_BRIDGE_SECRET_ONLY',marketScanAuthority:'CONTINUOUS_EVENT_DRIVEN',openPositionManagement:'EVERY_MARKET_STATE_CHANGE',managementAuthority:'EVERY_MARKET_STATE_CHANGE',cronRole:'NONE_EVENT_DRIVER_ONLY',scheduledExecution:false,
  timeGate:false,sessionGate:false,cooldownGate:false,timedPause:false,lossStreakTimeGate:false,strategyCooldown:'NONE',dailyTradeQuota:'NONE',
  riskAuthority:'CONTINUOUS_FULL_ACCOUNT_BALANCE_EQUITY_SCALE',continuousScale:true,balanceAuthority:'BYBIT_WALLET_PLUS_TRANSACTION_LOG',depositWithdrawalAware:true,unrealizedScaleCreditPct:25,
  leverageAuthority:'EQUITY_TAPERED_CLUSTER_LEVERAGE',smallCapitalHigherLeverage:true,largeCapitalLowerLeverage:true,leverageLockedInsideOpenCluster:true,
  positionExitAuthority:'STRUCTURE_FLOW_STABILITY_EXIT',instabilityExit:true,reentryAuthority:'FRESH_THESIS_ONLY',recoveryMartingale:false,recoveryAddToLoser:false,
  runtimeSwitchDeploymentPolicy:'PRESERVE_EXISTING',liveAckDeploymentPolicy:'PRESERVE_EXISTING'
};
