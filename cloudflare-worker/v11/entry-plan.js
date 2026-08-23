import {getInstrumentProfile,canonicalInstrument} from './instrument-profiles.js';
import {getSymbolScalpPolicy} from './symbol-scalp-policy.js';
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const sideSign=s=>String(s).toUpperCase()==='LONG'?1:String(s).toUpperCase()==='SHORT'?-1:0;
function nearestForward(side,entry,levels=[]){const sg=sideSign(side);return levels.map(n).filter(Number.isFinite).filter(x=>sg>0?x>entry:x<entry).sort((a,b)=>sg>0?a-b:b-a)[0]??null;}
function nearestInvalidation(side,entry,levels=[]){const sg=sideSign(side);return levels.map(n).filter(Number.isFinite).filter(x=>sg>0?x<entry:x>entry).sort((a,b)=>sg>0?b-a:a-b)[0]??null;}
function chooseSetup(p,c,sp){if(sp?.backtestEligible&&sp.backtestFamily)return sp.backtestFamily;const tags=new Set((c.confirmations||[]).map(x=>String(x).toUpperCase()));const f=p.families;if(p.entryRouter==='PB')return 'TREND_PULLBACK';if(p.entryRouter==='DUAL_FADE')return p.regimePrior==='MEAN_REVERSION'?'SWEEP_RECLAIM':'TREND_PULLBACK';if(tags.has('VWAP_RECLAIM')&&f.includes('VWAP_RECLAIM'))return 'VWAP_RECLAIM';if(tags.has('OPENING_RANGE_RETEST')&&f.includes('OPENING_RANGE_RETEST'))return 'OPENING_RANGE_RETEST';if(tags.has('SWEEP')||tags.has('LIQUIDITY_SWEEP'))return f.find(x=>x.includes('SWEEP'))||'SWEEP_RECLAIM';if(tags.has('BREAKOUT_RETEST'))return f.find(x=>x.includes('BREAKOUT'))||'BREAKOUT_RETEST';if(tags.has('PULLBACK'))return f.find(x=>x.includes('PULLBACK'))||'TREND_PULLBACK';return f[0]||'STRUCTURE_ROUTER';}
export function buildEntryPlan(market,c={}){
 const symbol=canonicalInstrument(c.symbol),p=getInstrumentProfile(symbol),sp=getSymbolScalpPolicy(symbol,market);
 if(!p||p.market!==market)return {ok:false,reason:'NO_INSTRUMENT_PROFILE',symbol};
 const side=String(c.side||'').toUpperCase(),sg=sideSign(side),entry=n(c.entry??c.price??c.quote),atr=n(c.atr);
 if(!sg||!entry||!atr||atr<=0)return {ok:false,reason:'MISSING_SIDE_ENTRY_ATR',symbol};
 const structureLevels=c.structureLevels||[],liquidityLevels=c.liquidityLevels||[],invalid=nearestInvalidation(side,entry,[c.structureInvalidation,c.swingInvalidation,...structureLevels]);
 const volatilityFloor=atr*Math.max(sp.stopAtr,sp.riskAtr),structRisk=invalid?Math.abs(entry-invalid):null,minStop=atr*.65,maxStop=atr*2.00;
 let risk=structRisk&&structRisk>=minStop&&structRisk<=maxStop?Math.max(structRisk,volatilityFloor):volatilityFloor;
 risk=clamp(risk,minStop,maxStop);const sl=entry-sg*risk;
 const forward=nearestForward(side,entry,[c.forwardLiquidity,c.targetStructure,...liquidityLevels,...structureLevels]),naturalRoom=forward?Math.abs(forward-entry)/risk:0;
 const lockedRR=sp.backtestEligible&&[1,2].includes(Number(sp.targetRR))?Number(sp.targetRR):null;
 let tp=null,room=0,reason,targetMode,executionRoom,preferredRoom;
 if(lockedRR){
  preferredRoom=lockedRR;executionRoom=lockedRR;tp=entry+sg*risk*lockedRR;room=lockedRR;reason=`BACKTEST_LOCKED_${lockedRR}R`;targetMode='BACKTEST_FIXED_RR';
 }else{
  preferredRoom=Number(sp.minRR||1.05);executionRoom=Math.max(.95,preferredRoom-.10);
  const fallbackTarget=Math.max(atr*sp.targetAtr,risk*executionRoom),maxTarget=atr*2.60;reason='WIDE_SCALP_ATR_FALLBACK';targetMode='ATR_FALLBACK';
  if(forward){const d=Math.abs(forward-entry);if(d>=risk*executionRoom&&d<=maxTarget){tp=forward;reason=d>=risk*preferredRoom?'WIDE_SCALP_FORWARD_STRUCTURE':'WIDE_SCALP_FORWARD_STRUCTURE_SOFT_ROOM';targetMode='STRUCTURE';}}
  if(!tp&&fallbackTarget<=maxTarget)tp=entry+sg*fallbackTarget;
  room=tp?Math.abs(tp-entry)/risk:0;
 }
 const executable=Boolean(tp&&room>=executionRoom-1e-9);
 return {ok:true,executable,status:executable?'READY':'WATCH',symbol,market,side,setup:chooseSetup(p,c,sp),entry,sl,tp,rr:Number(room.toFixed(3)),naturalRR:Number(naturalRoom.toFixed(3)),riskDistance:risk,riskAtr:Number((risk/atr).toFixed(3)),minRR:executionRoom,preferredRR:preferredRoom,targetMode,exitStyle:sp.exitStyle,symbolPolicy:sp,profile:{regimePrior:p.regimePrior,families:p.families,entryRouter:p.entryRouter,riskAtrPrior:p.riskAtrPrior,backtestFamily:sp.backtestFamily,backtestSession:sp.backtestSession},policies:{sl:'STRUCTURE_INVALIDATION_WITH_BACKTEST_ATR_FLOOR',tp:lockedRR?'EXACT_BACKTEST_RR_1_OR_2':'FORWARD_LIQUIDITY_OR_WIDE_ATR_TARGET'},reason:executable?reason:'NO_WIDE_SCALP_ROOM'};
}
