export const BINANCE_SYMBOL_PROFILES={
  BTCUSDT:{family:"TREND_BREAKOUT",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.85,rr:1.60,minScore:74,maxSpreadBps:5,maxChaseAtr:0.60,riskWeight:1.00},
  ETHUSDT:{family:"TREND_BREAKOUT",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.90,rr:1.65,minScore:74,maxSpreadBps:6,maxChaseAtr:0.62,riskWeight:0.95},
  SOLUSDT:{family:"MOMENTUM_PULLBACK",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.70,minScore:75,maxSpreadBps:8,maxChaseAtr:0.68,riskWeight:0.85},
  XRPUSDT:{family:"BREAKOUT_MEANREV",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.95,rr:1.55,minScore:75,maxSpreadBps:8,maxChaseAtr:0.65,riskWeight:0.80}
};

function liquidProfile(metrics={}){
  const q=Number(metrics.quoteVolume||0),s=Number(metrics.spreadBps||99);
  if(q>=500_000_000&&s<=4)return {family:"CORE_LIQUID_TREND",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:.90,rr:1.60,minScore:74,maxSpreadBps:6,maxChaseAtr:.62,riskWeight:.95};
  if(q>=100_000_000&&s<=7)return {family:"HIGH_LIQUID_MOMENTUM",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.65,minScore:75,maxSpreadBps:9,maxChaseAtr:.66,riskWeight:.85};
  return {family:"LIQUID_FILTERED_BREAKOUT",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.10,rr:1.55,minScore:76,maxSpreadBps:12,maxChaseAtr:.62,riskWeight:.70};
}

export function symbolProfile(symbol,metrics={}){
  const key=String(symbol||"").toUpperCase();
  return BINANCE_SYMBOL_PROFILES[key]||liquidProfile(metrics);
}
