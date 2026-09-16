export const BYBIT_EXECUTION_AUTHORITY='BYBIT-BTC-STATEFLOW-2.1';
export const BYBIT_EXECUTION_SYMBOL='BTCUSDT';
export const BYBIT_EXECUTION_UNIVERSE=Object.freeze([BYBIT_EXECUTION_SYMBOL]);
export const BYBIT_NON_BTC_EXECUTION_ERROR='BYBIT_NON_BTC_EXECUTION_RETIRED';

export function normalizeBybitExecutionSymbol(symbol=BYBIT_EXECUTION_SYMBOL){
  return String(symbol||BYBIT_EXECUTION_SYMBOL).trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
}

export function isBybitExecutionSymbol(symbol){
  return normalizeBybitExecutionSymbol(symbol)===BYBIT_EXECUTION_SYMBOL;
}

export function assertBybitExecutionSymbol(symbol){
  const normalized=normalizeBybitExecutionSymbol(symbol);
  if(normalized!==BYBIT_EXECUTION_SYMBOL){
    const error=new Error(BYBIT_NON_BTC_EXECUTION_ERROR);
    error.code=BYBIT_NON_BTC_EXECUTION_ERROR;
    error.symbol=normalized;
    throw error;
  }
  return normalized;
}
