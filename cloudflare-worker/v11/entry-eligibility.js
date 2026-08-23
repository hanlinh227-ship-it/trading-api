import {getSymbolScalpPolicy} from './symbol-scalp-policy.js';

const DIRECT_MARKET=new Set(['MARKET_SIGNAL','MARKET','MARKET_PLAN']);
const LIMIT_LIKE=new Set(['LIMIT','LIMIT_PLAN']);
const finite=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};

// One authority for NEW-entry eligibility. Native scheduler and manual 5-AI hunter
// must not disagree about whether the same live setup is close enough to enter.
export function evaluateEntryEligibility(symbol,market,status,candidate,quote){
 const sp=getSymbolScalpPolicy(symbol,market),s=String(status||'').toUpperCase();
 const live=finite(quote?.price),planned=finite(candidate?.plannedEntry??candidate?.entry),atr=finite(candidate?.atr);
 if(!(live>0)||quote?.fresh!==true)return {ready:false,reason:'NO_FRESH_LIVE_PRICE',policy:sp};
 const pct=planned>0?Math.abs(live-planned)/planned*100:0;
 if(DIRECT_MARKET.has(s)){
  return pct<=sp.entryDriftMaxPct
   ?{ready:true,mode:'DIRECT_MARKET',pct,policy:sp}
   :{ready:false,reason:'DIRECT_MARKET_CHASE',pct,policy:sp};
 }
 if(LIMIT_LIKE.has(s)){
  if(!(planned>0)||!(atr>0))return {ready:false,reason:'LIMIT_MISSING_ENTRY_OR_ATR',pct,policy:sp};
  const atrDistance=Math.abs(live-planned)/atr;
  // V77/V78-style practical promotion: a resting plan that price has already reached
  // should not remain WATCH merely because upstream still labels it LIMIT.
  const nearAtr=market==='crypto'?.45:market==='metal'||market==='index'?.40:.35;
  const near=atrDistance<=nearAtr&&pct<=sp.entryDriftMaxPct;
  return near
   ?{ready:true,mode:'LIMIT_NEAR_MARKET',pct,atrDistance,nearAtr,policy:sp}
   :{ready:false,reason:'LIMIT_WAIT_PRICE',pct,atrDistance,nearAtr,policy:sp};
 }
 return {ready:false,reason:`UPSTREAM_${s||'UNKNOWN'}_NOT_ENTRY_READY`,pct,policy:sp};
}

// HOLD viability is intentionally different from NEW-entry eligibility.
// An already-open signal must not be marked weak just because a fresh upstream scan
// now prefers LIMIT geometry. HOLD only cares about fresh evidence, side conflict,
// hard invalidation and whether the current structure still supports the original side.
export function evaluateHoldStatus(status,originalSide,newSide,plan,gate){
 const s=String(status||'').toUpperCase(),orig=String(originalSide||'').toUpperCase(),next=String(newSide||'').toUpperCase();
 if(next&&orig&&next!==orig)return {keep:false,reason:`SIDE_CHANGED_${orig}_TO_${next}`};
 if(plan?.ok===false)return {keep:false,reason:`PLAN_${plan.reason||'INVALID'}`};
 if(gate?.pass===false)return {keep:false,reason:`MARKET_GATE_${(gate.reasons||[]).join('|')||'REJECTED'}`};
 if(['REJECTED','NO_TRADE','INVALID','ERROR'].includes(s))return {keep:false,reason:`UPSTREAM_${s}_INVALIDATED`};
 return {keep:true,reason:'STRUCTURE_SIDE_STILL_VALID'};
}
