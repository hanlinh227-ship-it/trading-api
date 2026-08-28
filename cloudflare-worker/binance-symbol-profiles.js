// Shared symbol profiles used by Bybit Auto. V1.9.3 uses 5m execution structure + 15m context to reduce microstructure noise while preserving scalp responsiveness.
// 1m is retired from decision authority. 3m is no longer the primary trigger because the current objective is cleaner, less noisy scalp entries.
export const BINANCE_SYMBOL_PROFILES={
  BTCUSDT:{family:"TREND_BREAKOUT",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.85,rr:1.60,minScore:74,maxSpreadBps:5,maxChaseAtr:0.52,riskWeight:1.00},
  ETHUSDT:{family:"TREND_BREAKOUT",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.90,rr:1.65,minScore:74,maxSpreadBps:6,maxChaseAtr:0.54,riskWeight:0.95},
  SOLUSDT:{family:"MOMENTUM_PULLBACK",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.70,minScore:75,maxSpreadBps:8,maxChaseAtr:0.58,riskWeight:0.85},
  XRPUSDT:{family:"BREAKOUT_MEANREV",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.95,rr:1.55,minScore:75,maxSpreadBps:8,maxChaseAtr:0.56,riskWeight:0.80}
};

function liquidProfile(metrics={}){
  const q=Number(metrics.quoteVolume||0),s=Number(metrics.spreadBps||99);
  if(q>=500_000_000&&s<=4)return {family:"CORE_LIQUID_TREND",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:.90,rr:1.60,minScore:74,maxSpreadBps:6,maxChaseAtr:.54,riskWeight:.95};
  if(q>=100_000_000&&s<=7)return {family:"HIGH_LIQUID_MOMENTUM",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.65,minScore:75,maxSpreadBps:9,maxChaseAtr:.58,riskWeight:.85};
  return {family:"LIQUID_FILTERED_BREAKOUT",tfFast:"5m",tfContext:"15m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.10,rr:1.55,minScore:76,maxSpreadBps:12,maxChaseAtr:.55,riskWeight:.70};
}

export function symbolProfile(symbol,metrics={}){
  const key=String(symbol||"").toUpperCase();
  return BINANCE_SYMBOL_PROFILES[key]||liquidProfile(metrics);
}
