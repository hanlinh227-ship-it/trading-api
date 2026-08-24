export const BINANCE_SYMBOL_PROFILES={
  BTCUSDT:{family:"TREND_BREAKOUT",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.85,rr:1.60,minScore:80,maxSpreadBps:4,maxChaseAtr:0.45,riskWeight:1.00},
  ETHUSDT:{family:"TREND_BREAKOUT",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.90,rr:1.65,minScore:80,maxSpreadBps:5,maxChaseAtr:0.48,riskWeight:0.95},
  SOLUSDT:{family:"MOMENTUM_PULLBACK",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:1.00,rr:1.70,minScore:82,maxSpreadBps:7,maxChaseAtr:0.52,riskWeight:0.85},
  XRPUSDT:{family:"BREAKOUT_MEANREV",tfFast:"1m",tfContext:"5m",emaFast:9,emaSlow:21,ctxFast:20,ctxSlow:50,atrPeriod:14,slAtr:0.95,rr:1.55,minScore:81,maxSpreadBps:7,maxChaseAtr:0.50,riskWeight:0.80}
};
export function symbolProfile(symbol){return BINANCE_SYMBOL_PROFILES[String(symbol||"").toUpperCase()]||null;}
