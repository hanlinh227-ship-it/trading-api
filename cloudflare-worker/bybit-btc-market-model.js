// BTCUSDT non-indicator-first market model.
// Produces deterministic evidence objects consumed by the strategy router.
// No direct order placement is allowed from this module.

const n=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

export function structureState({swings=[],price=0}={}){
  const s=swings.filter(x=>Number.isFinite(Number(x?.high))&&Number.isFinite(Number(x?.low))).slice(-6);
  if(s.length<4)return {state:"UNKNOWN",score:0};
  const highs=s.map(x=>n(x.high)),lows=s.map(x=>n(x.low));
  const hh=highs[highs.length-1]>highs[highs.length-2]&&highs[highs.length-2]>highs[highs.length-3];
  const hl=lows[lows.length-1]>lows[lows.length-2]&&lows[lows.length-2]>=lows[lows.length-3];
  const lh=highs[highs.length-1]<highs[highs.length-2]&&highs[highs.length-2]<=highs[highs.length-3];
  const ll=lows[lows.length-1]<lows[lows.length-2]&&lows[lows.length-2]<lows[lows.length-3];
  if(hh&&hl)return {state:"TREND_UP",score:1,price:n(price)};
  if(lh&&ll)return {state:"TREND_DOWN",score:1,price:n(price)};
  return {state:"RANGE_OR_TRANSITION",score:.5,price:n(price)};
}

export function orderflowState({bids=[],asks=[],trades=[]}={}){
  const bidDepth=bids.slice(0,20).reduce((s,x)=>s+n(x?.[1]),0),askDepth=asks.slice(0,20).reduce((s,x)=>s+n(x?.[1]),0),den=Math.max(1e-12,bidDepth+askDepth);
  const imbalance=(bidDepth-askDepth)/den;
  let buy=0,sell=0;
  for(const t of trades.slice(-300)){
    const q=Math.abs(n(t?.size??t?.qty)),side=String(t?.side||"").toLowerCase();
    if(side==="buy")buy+=q;else if(side==="sell")sell+=q;
  }
  const flowDen=Math.max(1e-12,buy+sell),delta=(buy-sell)/flowDen;
  return {bidDepth,askDepth,imbalance:clamp(imbalance,-1,1),buyVolume:buy,sellVolume:sell,tradeDelta:clamp(delta,-1,1)};
}

export function liquidityState({recentHigh=0,recentLow=0,price=0,spreadBps=0,depthVacuumScore=0}={}){
  const p=n(price),hi=n(recentHigh),lo=n(recentLow);
  return {
    sweepHigh:hi>0&&p>hi,
    sweepLow:lo>0&&p<lo,
    insideRange:hi>lo&&p<=hi&&p>=lo,
    spreadBps:Math.max(0,n(spreadBps)),
    depthVacuumScore:clamp(n(depthVacuumScore),0,1)
  };
}

export function volatilityState({shortRange=0,longRange=0,realizedVol=0}={}){
  const s=Math.max(0,n(shortRange)),l=Math.max(1e-12,n(longRange)),ratio=s/l,rv=Math.max(0,n(realizedVol));
  if(ratio<.55)return {state:"SQUEEZE",ratio,realizedVol:rv};
  if(ratio>1.7)return {state:"EXPANSION",ratio,realizedVol:rv};
  return {state:"NORMAL",ratio,realizedVol:rv};
}

export function classifyBtcRegime({structure,orderflow,liquidity,volatility}={}){
  const st=structure?.state||"UNKNOWN",of=orderflow||{},liq=liquidity||{},vol=volatility||{};
  if(vol.state==="EXPANSION"&&Math.abs(n(of.tradeDelta))>.55&&Math.abs(n(of.imbalance))>.45)return {regime:"HIGH_VOL_SHOCK",confidence:.85};
  if(vol.state==="SQUEEZE")return {regime:"SQUEEZE",confidence:.75};
  if(st==="TREND_UP"&&n(of.tradeDelta)>.10)return {regime:"TREND_UP",confidence:clamp(.65+n(of.tradeDelta)*.2,0,1)};
  if(st==="TREND_DOWN"&&n(of.tradeDelta)<-.10)return {regime:"TREND_DOWN",confidence:clamp(.65+Math.abs(n(of.tradeDelta))*.2,0,1)};
  if(liq.sweepHigh&&n(of.tradeDelta)>.20)return {regime:"BREAKOUT_UP",confidence:.75};
  if(liq.sweepLow&&n(of.tradeDelta)<-.20)return {regime:"BREAKOUT_DOWN",confidence:.75};
  if(st==="RANGE_OR_TRANSITION"&&liq.insideRange)return {regime:"RANGE",confidence:.65};
  return {regime:"TRANSITION",confidence:.45};
}

export function buildBtcMarketEvidence(input={}){
  const structure=structureState(input),orderflow=orderflowState(input),liquidity=liquidityState(input),volatility=volatilityState(input),regime=classifyBtcRegime({structure,orderflow,liquidity,volatility});
  return {structure,orderflow,liquidity,volatility,regime,indicatorAuthority:false};
}
