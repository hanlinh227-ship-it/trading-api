import {getInstrumentProfile,canonicalInstrument} from './instrument-profiles.js';
import {getSymbolScalpPolicy} from './symbol-scalp-policy.js';
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const sideSign=s=>String(s).toUpperCase()==='LONG'?1:String(s).toUpperCase()==='SHORT'?-1:0;
function nearestForward(side,entry,levels=[]){const sg=sideSign(side);return levels.map(n).filter(Number.isFinite).filter(x=>sg>0?x>entry:x<entry).sort((a,b)=>sg>0?a-b:b-a)[0]??null;}
function nearestInvalidation(side,entry,levels=[]){const sg=sideSign(side);return levels.map(n).filter(Number.isFinite).filter(x=>sg>0?x<entry:x>entry).sort((a,b)=>sg>0?b-a:a-b)[0]??null;}
function chooseSetup(p,c){const tags=new Set((c.confirmations||[]).map(x=>String(x).toUpperCase()));const f=p.families;if(p.entryRouter==='PB')return 'TREND_PULLBACK';if(p.entryRouter==='DUAL_FADE')return p.regimePrior==='MEAN_REVERSION'?'SWEEP_RECLAIM':'TREND_PULLBACK';if(tags.has('VWAP_RECLAIM')&&f.includes('VWAP_RECLAIM'))return 'VWAP_RECLAIM';if(tags.has('OPENING_RANGE_RETEST')&&f.includes('OPENING_RANGE_RETEST'))return 'OPENING_RANGE_RETEST';if(tags.has('SWEEP')||tags.has('LIQUIDITY_SWEEP'))return f.find(x=>x.includes('SWEEP'))||'SWEEP_RECLAIM';if(tags.has('BREAKOUT_RETEST'))return f.find(x=>x.includes('BREAKOUT'))||'BREAKOUT_RETEST';if(tags.has('PULLBACK'))return f.find(x=>x.includes('PULLBACK'))||'TREND_PULLBACK';return f[0]||'STRUCTURE_ROUTER';}
export function buildEntryPlan(market,c={}){const symbol=canonicalInstrument(c.symbol),p=getInstrumentProfile(symbol),sp=getSymbolScalpPolicy(symbol,market);if(!p||p.market!==market)return {ok:false,reason:'NO_INSTRUMENT_PROFILE',symbol};const side=String(c.side||'').toUpperCase(),sg=sideSign(side),entry=n(c.entry??c.price??c.quote),atr=n(c.atr);if(!sg||!entry||!atr||atr<=0)return {ok:false,reason:'MISSING_SIDE_ENTRY_ATR',symbol};
 const structureLevels=c.structureLevels||[],liquidityLevels=c.liquidityLevels||[],invalid=nearestInvalidation(side,entry,[c.structureInvalidation,c.swingInvalidation,...structureLevels]);
 // Wide-scalp geometry: scalp refers to holding horizon, not a tiny stop.
 // Put the stop outside normal M5 noise and accept a wider real structure invalidation.
 const volatilityFloor=atr*Math.max(sp.stopAtr,sp.riskAtr),structRisk=invalid?Math.abs(entry-invalid):null,minStop=atr*.65,maxStop=atr*2.00;
 let risk=structRisk&&structRisk>=minStop&&structRisk<=maxStop?Math.max(structRisk,volatilityFloor):volatilityFloor;
 risk=clamp(risk,minStop,maxStop);const sl=entry-sg*risk;
 const forward=nearestForward(side,entry,[c.forwardLiquidity,c.targetStructure,...liquidityLevels,...structureLevels]),floor=sp.minRR,naturalRR=forward?Math.abs(forward-entry)/risk:0;
 // Prefer real liquidity/structure. If none is usable, use a wider ATR target instead of a tiny quick-hit target.
 const fallbackTarget=Math.max(atr*sp.targetAtr,risk*floor),maxTarget=atr*2.60;let tp=null,reason='WIDE_SCALP_ATR_FALLBACK',targetMode='ATR_FALLBACK';
 if(forward){const d=Math.abs(forward-entry);if(d>=risk*floor&&d<=maxTarget){tp=forward;reason='WIDE_SCALP_FORWARD_STRUCTURE';targetMode='STRUCTURE';}}
 if(!tp&&fallbackTarget<=maxTarget)tp=entry+sg*fallbackTarget;
 const rr=tp?Math.abs(tp-entry)/risk:0,executable=Boolean(tp&&rr>=floor);
 return {ok:true,executable,status:executable?'READY':'WATCH',symbol,market,side,setup:chooseSetup(p,c),entry,sl,tp,rr:Number(rr.toFixed(3)),naturalRR:Number(naturalRR.toFixed(3)),riskDistance:risk,riskAtr:Number((risk/atr).toFixed(3)),minRR:floor,targetMode,exitStyle:sp.exitStyle,symbolPolicy:sp,profile:{regimePrior:p.regimePrior,families:p.families,entryRouter:p.entryRouter,riskAtrPrior:p.riskAtrPrior},policies:{sl:'WIDE_STRUCTURE_INVALIDATION_WITH_ATR_FLOOR',tp:'FORWARD_LIQUIDITY_OR_WIDE_ATR_TARGET'},reason:executable?reason:'NO_WIDE_SCALP_ROOM'};
}
