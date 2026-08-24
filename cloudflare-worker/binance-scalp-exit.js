// Binance Futures scalp exit planning: structure + Fibonacci + BE + positive trailing.

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const num=v=>Number(v);
function recentSwing(rows,lookback=24){
  const xs=(rows||[]).slice(-lookback);
  if(!xs.length)return null;
  return {high:Math.max(...xs.map(x=>num(x[2]))),low:Math.min(...xs.map(x=>num(x[3])))};
}
function fibLevels(low,high){
  const d=high-low;
  return {
    r382:high-d*.382,r5:high-d*.5,r618:high-d*.618,
    e1272:high+d*.272,e1618:high+d*.618,
    s1272:low-d*.272,s1618:low-d*.618
  };
}
export function buildScalpExitPlan({side,entry,atr,r1=[],rrFloor=1.15,rrCap=2.0}){
  const sw=recentSwing(r1,24);if(!sw||!(atr>0)||!(entry>0))return null;
  const fib=fibLevels(sw.low,sw.high);
  const long=side==="BUY";
  const structureSl=long?Math.min(sw.low,entry-atr*.75):Math.max(sw.high,entry+atr*.75);
  let risk=Math.abs(entry-structureSl);if(!(risk>0))return null;
  const nearestResistance=long?Math.max(entry+atr*.9,sw.high):Math.min(entry-atr*.9,sw.low);
  const fibExtension=long?Math.max(fib.e1272,entry+risk*rrFloor):Math.min(fib.s1272,entry-risk*rrFloor);
  let tp=long?Math.min(nearestResistance>entry?nearestResistance:Infinity,fibExtension):Math.max(nearestResistance<entry?nearestResistance:-Infinity,fibExtension);
  if(!Number.isFinite(tp))tp=long?entry+risk*1.35:entry-risk*1.35;
  let rr=Math.abs(tp-entry)/risk;
  rr=clamp(rr,rrFloor,rrCap);
  tp=long?entry+risk*rr:entry-risk*rr;
  return {
    sl:structureSl,tp,rr,
    breakEvenTriggerR:.65,
    positiveTrailTriggerR:1.0,
    positiveTrailLockR:.25,
    trailAtr:.55,
    structure:{swingHigh:sw.high,swingLow:sw.low,fib}
  };
}

export function nextManagedStop({side,entry,current,initialSl,currentSl,atr,plan}){
  const long=side==="BUY",risk=Math.abs(entry-initialSl);if(!(risk>0)||!(atr>0))return currentSl;
  const rNow=(long?(current-entry):(entry-current))/risk;
  let next=currentSl;
  if(rNow>=plan.breakEvenTriggerR){const be=entry;next=long?Math.max(next,be):Math.min(next,be);}
  if(rNow>=plan.positiveTrailTriggerR){
    const locked=long?entry+risk*plan.positiveTrailLockR:entry-risk*plan.positiveTrailLockR;
    const atrTrail=long?current-atr*plan.trailAtr:current+atr*plan.trailAtr;
    const cand=long?Math.max(locked,atrTrail):Math.min(locked,atrTrail);
    next=long?Math.max(next,cand):Math.min(next,cand);
  }
  return next;
}
