// Shared symbol profiles used by Bybit Auto. V1.9.6 frequency-balance patch keeps 5m execution structure + 15m context while easing candidate starvation.
// M1 has zero signal authority: it cannot be returned as tfFast or tfContext by this module.
export const BYBIT_SIGNAL_TIMEFRAME="5m";
export const BYBIT_CONTEXT_TIMEFRAME="15m";
export const BYBIT_M1_SIGNAL_DISABLED=true;

const withAuthority=profile=>({...profile,tfFast:BYBIT_SIGNAL_TIMEFRAME,tfContext:BYBIT_CONTEXT_TIMEFRAME,signalAuthority:BYBIT_SIGNAL_TIMEFRAME,contextAuthority:BYBIT_CONTEXT_TIMEFRAME,m1SignalDisabled:BYBIT_M1_SIGNAL_DISABLED});

export const BINANCE_SYMBOL_PROFILES={
  BTCUSDT:withAuthority({family:"TREND_BREAKOUT",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.85,rr:1.60,minScore:72,maxSpreadBps:5,maxChaseAtr:0.66,riskWeight:1.00}),
  ETHUSDT:withAuthority({family:"TREND_BREAKOUT",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.90,rr:1.65,minScore:72,maxSpreadBps:6,maxChaseAtr:0.68,riskWeight:0.95}),
  SOLUSDT:withAuthority({family:"MOMENTUM_PULLBACK",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.70,minScore:73,maxSpreadBps:8,maxChaseAtr:0.72,riskWeight:0.85}),
  XRPUSDT:withAuthority({family:"BREAKOUT_MEANREV",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.95,rr:1.55,minScore:73,maxSpreadBps:8,maxChaseAtr:0.70,riskWeight:0.80})
};

function liquidProfile(metrics={}){
  const q=Number(metrics.quoteVolume||0),s=Number(metrics.spreadBps||99);
  if(q>=500_000_000&&s<=4)return withAuthority({family:"CORE_LIQUID_TREND",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:.90,rr:1.60,minScore:72,maxSpreadBps:6,maxChaseAtr:.68,riskWeight:.95});
  if(q>=100_000_000&&s<=7)return withAuthority({family:"HIGH_LIQUID_MOMENTUM",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.65,minScore:73,maxSpreadBps:9,maxChaseAtr:.72,riskWeight:.85});
  return withAuthority({family:"LIQUID_FILTERED_BREAKOUT",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.10,rr:1.55,minScore:74,maxSpreadBps:12,maxChaseAtr:.70,riskWeight:.70});
}

export function symbolProfile(symbol,metrics={}){
  const key=String(symbol||"").toUpperCase();
  const profile=BINANCE_SYMBOL_PROFILES[key]||liquidProfile(metrics);
  if(profile.tfFast!==BYBIT_SIGNAL_TIMEFRAME||profile.tfContext!==BYBIT_CONTEXT_TIMEFRAME||profile.tfFast==="1m"||profile.tfContext==="1m")throw new Error("BYBIT_TIMEFRAME_AUTHORITY_VIOLATION");
  return profile;
}
