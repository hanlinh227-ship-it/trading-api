export const BYBIT_ANDROID_MONITOR_SCHEMA_VERSION='BYBIT_ANDROID_MONITOR_V1';
export const BYBIT_ANDROID_MONITOR_ROUTES=Object.freeze({
  bootstrap:'/bybit/monitor/bootstrap',
  pair:'/bybit/monitor/pair',
  pairCodeAdmin:'/bybit/monitor/pair-code',
  authHealth:'/bybit/monitor/auth/health',
  snapshot:'/bybit/monitor/snapshot',
  websocket:'/bybit/monitor/ws'
});
export const BYBIT_ANDROID_MONITOR_CAPABILITIES=Object.freeze({
  readOnly:true,
  tradingControls:false,
  sourceOfTruth:'BOT_VPS',
  monitorTokenSeparate:true,
  tokenInQueryString:false,
  bybitApiSecretExposedToAndroid:false,
  monitorUsesPrivateBybitCredentials:false,
  accountSource:'BOT_CONTROLLER_RECONCILED_STATE_PLUS_VPS_WS_MARK_TO_MARKET',
  scannerSource:'BYBIT_PUBLIC_MARKET_PLUS_BOT_UNIVERSE_RULES',
  snapshotApi:true,
  realtimeWebSocket:true,
  accountTelemetry:true,
  performanceTelemetry:true,
  scannerTelemetry:true,
  allOpenPositions:true,
  bybitWsTelemetry:true,
  latencyTelemetry:true,
  dataAgeTelemetry:true,
  darkMonospaceUiContract:true,
  defaultStreamIntervalMs:750,
  minStreamIntervalMs:500,
  maxStreamIntervalMs:10000
});
