import {BYBIT_BTC_ONLY_VERSION,BYBIT_BTC_SYMBOL} from "./bybit-btc-only-design.js";

export const BYBIT_BTC_RUNTIME_CONTRACT_VERSION="BYBIT_BTC_RUNTIME_V1";
export const BYBIT_BTC_EXECUTION_AUTHORITY="BTCUSDT_ONLY";
export const BYBIT_BTC_PRIVATE_TRANSPORT="VPS_BYBIT_PRIVATE_PROXY";
export const BYBIT_BTC_MARKET_TRANSPORT="VPS_BYBIT_MARKET_PROXY";
export const BYBIT_BTC_HEALTH_ROUTE="/bybit/health";

export const BYBIT_BTC_RUNTIME_CONTRACT=Object.freeze({
  version:BYBIT_BTC_RUNTIME_CONTRACT_VERSION,
  autoVersion:BYBIT_BTC_ONLY_VERSION,
  symbol:BYBIT_BTC_SYMBOL,
  executionAuthority:BYBIT_BTC_EXECUTION_AUTHORITY,
  privateTransport:BYBIT_BTC_PRIVATE_TRANSPORT,
  marketTransport:BYBIT_BTC_MARKET_TRANSPORT,
  healthRoute:BYBIT_BTC_HEALTH_ROUTE,
  legacyMultiCoinExecutionDisabled:true,
  indicatorAuthority:false,
  liveApiPreserved:true
});
