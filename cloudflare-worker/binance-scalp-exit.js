// Binance Futures scalp exit planning V3: structure-first + ATR volatility buffer + Fibonacci targets + delayed BE/trailing.

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const num=v=>Number(v);
function recentSwing(rows,lookback=28){
  const xs=(rows||[]).slice(-lookback);
  if(!xs.length)return null;
  return {high:Math.max(...xs.map(x=>num(x[2]))),low:Math.min(...xs.map(x=>num(x[3])))};
}
function fibLevels(low,high){
  const d=high-low;
  return {r382:high-d*.382,r5:high-d*.5,r618:high-d*.618,e1272:high+d*.272,e1618:high+d*.618,s1272:low-d*.272,s1618:low-d*.618};
}
function volatilityClass(atr,entry){
  const pct=entry>0?atr/entry*100:0;
  if(pct>=.55)return "HIGH";
  if(pct>=.22)return "MEDIUM";
  return "LOW";
}
export function buildScalpExitPlan({side,entry,atr,r1=[],rrFloor=1.0,preferredRR=2.0,rrCap=3.0}){
  const sw=recentSwing(r1,28);if(!sw||!(atr>0)||!(entry>0))return null;
  const fib=fibLevels(sw.low,sw.high),long=side==="BUY",vol=volatilityClass(atr,entry);
  const slBufferAtr=vol==="HIGH"?.45:vol==="MEDIUM"?.32:.24;
  const structureInvalidation=long?sw.low:sw.high;
  const structureSl=long?Math.min(structureInvalidation-atr*slBufferAtr,entry-atr*.9):Math.max(structureInvalidation+atr*slBufferAtr,entry+atr*.9);
  const risk=Math.abs(entry-structureSl);if(!(risk>0))return null;

  const levels=[
    {price:long?sw.high:sw.low,source:"STRUCTURE"},
    {price:long?fib.e1272:fib.s1272,source:"FIB_1.272"},
    {price:long?fib.e1618:fib.s1618,source:"FIB_1.618"}
  ].map(x=>({...x,rr:Math.abs(x.price-entry)/risk})).filter(x=>Number.isFinite(x.rr)&&x.rr>=rrFloor);

  const pref=Math.max(rrFloor,preferredRR),cap=Math.max(pref,rrCap);
  const preferred=levels.filter(x=>x.rr>=pref&&x.rr<=cap).sort((a,b)=>a.rr-b.rr)[0];
  const acceptable=levels.filter(x=>x.rr>=rrFloor&&x.rr<=cap).sort((a,b)=>b.rr-a.rr)[0];
  const chosen=preferred||acceptable||{price:long?entry+risk*pref:entry-risk*pref,rr:pref,source:"RR_2R_FALLBACK"};
  const rr=clamp(chosen.rr,rrFloor,cap),tp=long?entry+risk*rr:entry-risk*rr;

  const breakEvenTriggerR=vol==="HIGH"?1.05:vol==="MEDIUM"?.95:.85;
  const positiveTrailTriggerR=vol==="HIGH"?1.45:vol==="MEDIUM"?1.3:1.2;
  const positiveTrailLockR=vol==="HIGH"?.2:.25;
  const trailAtr=vol==="HIGH"?1.15:vol==="MEDIUM"?.95:.8;

  return {
    sl:structureSl,tp,rr,
    targetSource:chosen.source,
    preferredRR:pref,
    minRR:rrFloor,
    volatilityClass:vol,
    breakEvenTriggerR,
    positiveTrailTriggerR,
    positiveTrailLockR,
    trailAtr,
    requireStructureConfirmationForBE:true,
    requireStructureConfirmationForPositiveTrail:true,
    structure:{swingHigh:sw.high,swingLow:sw.low,fib,slBufferAtr}
  };
}

export function nextManagedStop({side,entry,current,initialSl,currentSl,atr,plan,structureConfirmed=false}){
  const long=side==="BUY",risk=Math.abs(entry-initialSl);if(!(risk>0)||!(atr>0))return currentSl;
  const rNow=(long?(current-entry):(entry-current))/risk;
  let next=currentSl;
  if(rNow>=plan.breakEvenTriggerR&&(!plan.requireStructureConfirmationForBE||structureConfirmed)){
    const be=entry;next=long?Math.max(next,be):Math.min(next,be);
  }
  if(rNow>=plan.positiveTrailTriggerR&&(!plan.requireStructureConfirmationForPositiveTrail||structureConfirmed)){
    const locked=long?entry+risk*plan.positiveTrailLockR:entry-risk*plan.positiveTrailLockR;
    const atrTrail=long?current-atr*plan.trailAtr:current+atr*plan.trailAtr;
    const cand=long?Math.max(locked,atrTrail):Math.min(locked,atrTrail);
    next=long?Math.max(next,cand):Math.min(next,cand);
  }
  return next;
}
