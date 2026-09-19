export const BYBIT_EXECUTION_AUTHORITY='BYBIT-TOP100-STATEFLOW-3.0';
export const BYBIT_EXECUTION_SYMBOL='BTCUSDT';
export const BYBIT_EXECUTION_UNIVERSE=Object.freeze(['DYNAMIC_TOP100_MARKET_CAP_USDT_LINEAR']);
export const BYBIT_NON_BTC_EXECUTION_ERROR='BYBIT_SYMBOL_OUTSIDE_TOP100_EXECUTION_AUTHORITY';

export function normalizeBybitExecutionSymbol(symbol=BYBIT_EXECUTION_SYMBOL){
  return String(symbol||BYBIT_EXECUTION_SYMBOL).trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
}

export function isBybitExecutionSymbol(symbol){
  const s=normalizeBybitExecutionSymbol(symbol);
  return /^[A-Z0-9]{2,28}USDT$/.test(s);
}

export function assertBybitExecutionSymbol(symbol){
  const normalized=normalizeBybitExecutionSymbol(symbol);
  if(!isBybitExecutionSymbol(normalized)){
    const error=new Error(BYBIT_NON_BTC_EXECUTION_ERROR);
    error.code=BYBIT_NON_BTC_EXECUTION_ERROR;
    error.symbol=normalized;
    throw error;
  }
  return normalized;
}
