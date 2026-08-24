// ============================================================================
// BINANCE FUTURES SCALP ENGINE V3
// Structure + EMA + VWAP + RSI + volume + liquidity + adaptive exits.
// Production execution remains controlled by the separate Binance Auto runtime.
// ============================================================================

import {binance20Config,BINANCE20_VERSION} from "./binance-futures20-config.js";
import {binanceUsdm,symbolFilters,floorStep} from "./binance-usdm-client.js";
import {symbolProfile} from "./binance-symbol-profiles.js";
import {buildBinanceLiquidUniverse} from "./binance-universe.js";
import {buildScalpExitPlan} from "./binance-scalp-exit.js";
import {scalpContext,scalpConfluence} from "./binance-scalp-context.js";

const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0,last=a=>a[a.length-1],clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function ema(a,n){if(!a.length)return 0;const k=2/(n+1);let e=a[0];for(let i=1;i<a.length;i++)e=a[i]*k+e*(1-k);return e;}
function atr(r,n=14){if(r.length<n+1)return 0;const t=[];for(let i=r.length-n;i<r.length;i++){const p=r[i-1][4];t.push(Math.max(r[i][2]-r[i][3],Math.abs(r[i][2]-p),Math.abs(r[i][3]-p)));}return avg(t);}
function parseK(rows){return rows.map(x=>[Number(x[0]),Number(x[1]),Number(x[2]),Number(x[3]),Number(x[4]),Number(x[5])]).filter(x=>x.slice(1).every(Number.isFinite));}
function analyze(symbol,r1,r5,bid,ask,cfg,metrics){
  const profile=symbolProfile(symbol,metrics),c1=r1.map(x=>x[4]),c5=r5.map(x=>x[4]),p=(bid+ask)/2,a1=atr(r1,profile.atrPeriod),a5=atr(r5,profile.atrPeriod),eFast=ema(c1,profile.emaFast),eSlow=ema(c1,profile.emaSlow),ctxFast=ema(c5,profile.ctxFast),ctxSlow=ema(c5,profile.ctxSlow),spreadBps=(ask-bid)/p*10000,atrPct=a1/p*100;
  if(!(a1>0)||atrPct<cfg.filters.minAtrPct||atrPct>cfg.filters.maxAtrPct||spreadBps>profile.maxSpreadBps)return null;
  const c=last(r1),pr=r1[r1.length-2],trend=ctxFast>ctxSlow?1:ctxFast<ctxSlow?-1:0,impUp=c[4]>c[1]&&c[4]>pr[2],impDn=c[4]<c[1]&&c[4]<pr[3],near=Math.min(Math.abs(p-eFast),Math.abs(p-eSlow))<=a1*.60;
  const look=r1.slice(-26,-3),hi=Math.max(...look.map(x=>x[2])),lo=Math.min(...look.map(x=>x[3]));
  let side=null,strategy=null,score=0,breakout=false;
  if(trend>0&&near&&impUp){side="BUY";strategy=`SCALP:${profile.family}:TREND_PULLBACK`;score=78;}
  else if(trend<0&&near&&impDn){side="SELL";strategy=`SCALP:${profile.family}:TREND_PULLBACK`;score=78;}
  else if(c[4]>hi&&c[4]-hi<=a1*profile.maxChaseAtr){side="BUY";strategy=`SCALP:${profile.family}:BREAKOUT`;score=75;breakout=true;}
  else if(c[4]<lo&&lo-c[4]<=a1*profile.maxChaseAtr){side="SELL";strategy=`SCALP:${profile.family}:BREAKOUT`;score=75;breakout=true;}
  if(!side)return null;

  const ctx=scalpContext(r1,p,a1),conf=scalpConfluence(side,ctx,{breakout});
  const vwapAligned=ctx.vwap>0&&(side==="BUY"?p>=ctx.vwap:p<=ctx.vwap);
  if(vwapAligned)score+=4;else if(ctx.distanceFromVwapAtr>1.6)score-=3;
  score+=conf.score;
  score+=clamp(Math.abs(ctxFast-ctxSlow)/Math.max(a5,1e-9)*8,0,10);
  if(breakout&&ctx.volumeRatio<1.05)return null;
  if(ctx.distanceFromVwapAtr>2.4)return null;
  if(score<profile.minScore)return null;

  const entry=side==="BUY"?ask:bid,exitPlan=buildScalpExitPlan({side,entry,atr:a1,r1,rrFloor:Math.max(1.2,Number(cfg.risk.minRR||1.2)),rrCap:Math.min(2.0,Number(profile.rr||1.6)+.25)});if(!exitPlan)return null;
  return {symbol,side,strategy,profile:profile.family,score:Math.round(score),entry,sl:exitPlan.sl,tp:exitPlan.tp,rr:exitPlan.rr,atr1:a1,spreadBps,riskWeight:profile.riskWeight,exitPlan,context:{...ctx,vwapAligned,confluence:conf.reasons},liquidity:{quoteVolume:Number(metrics?.quoteVolume||0),universeSpreadBps:Number(metrics?.spreadBps||spreadBps)}};
}

export async function scanBinance20(env){
  const cfg=binance20Config(env),api=binanceUsdm(env),[info,universe]=await Promise.all([api.exchangeInfo(),buildBinanceLiquidUniverse(env,{minCount:50,minQuoteVolumeUsd:Number(env.BINANCE_MIN_QUOTE_VOLUME_USD||5_000_000),maxSpreadBps:Number(env.BINANCE_MAX_UNIVERSE_SPREAD_BPS||12)})]);
  if(!universe.ok)return {version:BINANCE20_VERSION,best:null,candidates:[],universe,reason:universe.reason,scannedAt:Date.now()};
  const metricsMap=new Map(universe.metrics.map(x=>[x.symbol,x])),out=[],errors=[];
  const concurrency=Math.max(4,Math.min(16,Number(env.BINANCE_SCAN_CONCURRENCY||8)));
  for(let i=0;i<universe.symbols.length;i+=concurrency){
    const batch=universe.symbols.slice(i,i+concurrency);
    const rows=await Promise.all(batch.map(async symbol=>{
      const f=symbolFilters(info,symbol);if(!f||f.status!=="TRADING"||f.contractType!=="PERPETUAL")return null;
      const metrics=metricsMap.get(symbol)||{},profile=symbolProfile(symbol,metrics);
      try{const [k1,k5,b]=await Promise.all([api.klines(symbol,profile.tfFast,160),api.klines(symbol,profile.tfContext,160),api.bookTicker(symbol)]),setup=analyze(symbol,parseK(k1),parseK(k5),Number(b.bidPrice),Number(b.askPrice),cfg,metrics);return setup?{...setup,filters:f}:null;}catch(e){errors.push({symbol,error:String(e?.message||e).slice(0,120)});return null;}
    }));
    for(const r of rows)if(r)out.push(r);
  }
  out.sort((a,b)=>b.score-a.score||b.rr-a.rr||b.liquidity.quoteVolume-a.liquidity.quoteVolume);
  return {version:BINANCE20_VERSION,capitalUsd:cfg.startingCapitalUsd,best:out[0]||null,candidates:out,universe:{...universe,metrics:undefined},analyzed:universe.symbols.length,qualified:out.length,errors:errors.slice(0,20),scannedAt:Date.now()};
}

export function sizeBinance20(setup,filters,cfg,equityUsd=20){const baseRisk=Math.min(cfg.risk.perTradeUsd,Math.max(.05,equityUsd*.01)),riskUsd=baseRisk*Math.max(.25,Math.min(1,Number(setup.riskWeight||1))),dist=Math.abs(setup.entry-setup.sl),raw=riskUsd/dist,step=filters.marketStepSize||filters.stepSize,qty=floorStep(raw,step),notional=qty*setup.entry,minNotional=Math.max(5,filters.minNotional||5);if(!(qty>=filters.minQty)||notional<minNotional)return {ok:false,reason:"MIN_NOTIONAL_OR_QTY",qty,notional,minNotional};return {ok:true,qty,notional,riskUsd,leverage:cfg.leverage};}
