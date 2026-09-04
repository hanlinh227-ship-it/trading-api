export const BYBIT_ANDROID_MONITOR_SCHEMA_VERSION='BYBIT_ANDROID_MONITOR_V1';
export const BYBIT_ANDROID_MONITOR_ROUTES=Object.freeze({
  bootstrap:'/bybit/monitor/bootstrap',
  pair:'/bybit/monitor/pair',
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
  bybitPrivateTelemetrySignedOnVps:true,
  snapshotApi:true,
  realtimeWebSocket:true,
  accountTelemetry:true,
  performanceTelemetry:true,
  scannerTelemetry:true,
  allOpenPositions:true,
  bybitWsTelemetry:true,
  latencyTelemetry:true,
  dataAgeTelemetry:true,
  defaultStreamIntervalMs:1500,
  minStreamIntervalMs:1000,
  maxStreamIntervalMs:10000
});
