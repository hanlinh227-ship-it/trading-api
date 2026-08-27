// Scalp exit planning V5: structure-first + wider anti-sweep floor + delayed BE/lock/trailing.

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const num=v=>Number(v);
function recentSwing(rows,lookback=28,excludeLast=2){
  const src=(rows||[]).slice(0,Math.max(0,(rows||[]).length-excludeLast));
  const xs=src.slice(-lookback);
  if(!xs.length)return null;
  return {high:Math.max(...xs.map(x=>num(x[2]))),low:Math.min(...xs.map(x=>num(x[3])))};
}
function recentWickNoise(rows,lookback=18){
  const xs=(rows||[]).slice(-lookback);
  if(!xs.length)return 0;
  const w=xs.map(x=>Math.max(Math.abs(num(x[2])-Math.max(num(x[1]),num(x[4]))),Math.abs(Math.min(num(x[1]),num(x[4]))-num(x[3])))).filter(Number.isFinite).sort((a,b)=>a-b);
  return w.length?w[Math.min(w.length-1,Math.floor(w.length*.8))]:0;
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
  const sw=recentSwing(r1,34,2);if(!sw||!(atr>0)||!(entry>0))return null;
  const fib=fibLevels(sw.low,sw.high),long=side==="BUY",vol=volatilityClass(atr,entry),wickNoise=recentWickNoise(r1,24);

  // Anti-sweep V5: stop sits beyond confirmed 1m structure and outside ordinary wick/ATR noise.
  // Dollar risk stays controlled by position sizing; widening price distance must reduce quantity, never increase loss budget.
  const minStopAtr=vol==="HIGH"?2.05:vol==="MEDIUM"?1.85:1.70;
  const structureBufferAtr=vol==="HIGH"?.82:vol==="MEDIUM"?.68:.55;
  const noiseBuffer=Math.max(atr*structureBufferAtr,wickNoise*.85);
  const structureInvalidation=long?sw.low:sw.high;
  const beyondStructure=long?structureInvalidation-noiseBuffer:structureInvalidation+noiseBuffer;
  const atrFloorStop=long?entry-atr*minStopAtr:entry+atr*minStopAtr;
  const structureSl=long?Math.min(beyondStructure,atrFloorStop):Math.max(beyondStructure,atrFloorStop);
  const risk=Math.abs(entry-structureSl);if(!(risk>0))return null;

  // Reject pathological geometry instead of accepting an excessively wide invalidation.
  const maxStopAtr=vol==="HIGH"?4.8:vol==="MEDIUM"?4.4:4.0;
  if(risk>atr*maxStopAtr)return null;

  const levels=[
    {price:long?sw.high:sw.low,source:"STRUCTURE"},
    {price:long?fib.e1272:fib.s1272,source:"FIB_1.272"},
    {price:long?fib.e1618:fib.s1618,source:"FIB_1.618"}
  ].map(x=>({...x,rr:Math.abs(x.price-entry)/risk})).filter(x=>Number.isFinite(x.rr)&&x.rr>=rrFloor);

  const pref=Math.max(rrFloor,preferredRR),cap=Math.max(pref,rrCap);
  const preferred=levels.filter(x=>x.rr>=pref&&x.rr<=cap).sort((a,b)=>a.rr-b.rr)[0];
  const acceptable=levels.filter(x=>x.rr>=rrFloor&&x.rr<=cap).sort((a,b)=>b.rr-a.rr)[0];
  const chosen=preferred||acceptable||{price:long?entry+risk*pref:entry-risk*pref,rr:pref,source:"RR_FALLBACK"};
  const rr=clamp(chosen.rr,rrFloor,cap),tp=long?entry+risk*rr:entry-risk*rr;

  // Management is deliberately late. Price must travel well beyond noise before BE/lock/trailing can activate.
  const breakEvenTriggerR=vol==="HIGH"?1.45:vol==="MEDIUM"?1.35:1.30;
  const positiveTrailTriggerR=vol==="HIGH"?2.10:vol==="MEDIUM"?1.95:1.85;
  const positiveTrailLockR=vol==="HIGH"?.28:vol==="MEDIUM"?.32:.35;
  const trailAtr=vol==="HIGH"?1.70:vol==="MEDIUM"?1.50:1.30;

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
    stopPolicy:"STRUCTURE_ANTI_SWEEP_V5",
    stopDistanceAtr:risk/atr,
    structure:{swingHigh:sw.high,swingLow:sw.low,fib,structureBufferAtr,minStopAtr,maxStopAtr,wickNoise,noiseBuffer}
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
