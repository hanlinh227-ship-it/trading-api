import {getInstrumentProfile,canonicalInstrument} from './instrument-profiles.js';
import {V11_CONFIG} from './config.js';
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const sideSign=s=>String(s).toUpperCase()==='LONG'?1:String(s).toUpperCase()==='SHORT'?-1:0;
function nearestForward(side,entry,levels=[]){const sg=sideSign(side);return levels.map(n).filter(Number.isFinite).filter(x=>sg>0?x>entry:x<entry).sort((a,b)=>sg>0?a-b:b-a)[0]??null;}
function nearestInvalidation(side,entry,levels=[]){const sg=sideSign(side);return levels.map(n).filter(Number.isFinite).filter(x=>sg>0?x<entry:x>entry).sort((a,b)=>sg>0?b-a:a-b)[0]??null;}
function chooseSetup(p,c){const tags=new Set((c.confirmations||[]).map(x=>String(x).toUpperCase()));const f=p.families;
 if(p.entryRouter==='PB')return 'TREND_PULLBACK';
 if(p.entryRouter==='DUAL_FADE')return p.regimePrior==='MEAN_REVERSION'?'SWEEP_RECLAIM':'TREND_PULLBACK';
 if(tags.has('VWAP_RECLAIM')&&f.includes('VWAP_RECLAIM'))return 'VWAP_RECLAIM';
 if(tags.has('OPENING_RANGE_RETEST')&&f.includes('OPENING_RANGE_RETEST'))return 'OPENING_RANGE_RETEST';
 if(tags.has('SWEEP')||tags.has('LIQUIDITY_SWEEP'))return f.find(x=>x.includes('SWEEP'))||'SWEEP_RECLAIM';
 if(tags.has('BREAKOUT_RETEST'))return f.find(x=>x.includes('BREAKOUT'))||'BREAKOUT_RETEST';
 if(tags.has('PULLBACK'))return f.find(x=>x.includes('PULLBACK'))||'TREND_PULLBACK';
 return f[0]||'STRUCTURE_ROUTER';
}
export function buildEntryPlan(market,c={}){const symbol=canonicalInstrument(c.symbol),p=getInstrumentProfile(symbol),cfg=V11_CONFIG.markets[market];if(!p||p.market!==market)return {ok:false,reason:'NO_INSTRUMENT_PROFILE',symbol};const side=String(c.side||'').toUpperCase(),sg=sideSign(side),entry=n(c.entry??c.price??c.quote),atr=n(c.atr);if(!sg||!entry||!atr||atr<=0)return {ok:false,reason:'MISSING_SIDE_ENTRY_ATR',symbol};
 const structureLevels=c.structureLevels||[],liquidityLevels=c.liquidityLevels||[],invalid=nearestInvalidation(side,entry,[c.structureInvalidation,c.swingInvalidation,...structureLevels]),volFloor=atr*p.riskAtrPrior;
 let risk=invalid?Math.max(Math.abs(entry-invalid),volFloor):volFloor;risk=clamp(risk,atr*.22,atr*2.2);const sl=entry-sg*risk;
 const forward=nearestForward(side,entry,[c.forwardLiquidity,c.targetStructure,...liquidityLevels,...structureLevels]),marketFloor=cfg?.minRR??1.05,naturalRR=forward?Math.abs(forward-entry)/risk:0;
 let tp=forward,reason='STRUCTURE_GEOMETRY_VALID',targetMode='STRUCTURE';
 if(!tp||naturalRR<marketFloor){const atrTarget=Math.max(risk*marketFloor,atr*(cfg?.scalpTargetAtr??.65)),maxTarget=atr*1.5;if(atrTarget<=maxTarget){tp=entry+sg*atrTarget;reason=forward?'SCALP_TARGET_REPLACES_LOW_RR_STRUCTURE':'SCALP_VOLATILITY_TARGET';targetMode='SCALP_ATR';}}
 const rr=tp?Math.abs(tp-entry)/risk:0,executable=Boolean(tp&&rr>=marketFloor);
 return {ok:true,executable,status:executable?'READY':'WATCH',symbol,market,side,setup:chooseSetup(p,c),entry,sl,tp,rr:Number(rr.toFixed(3)),naturalRR:Number(naturalRR.toFixed(3)),riskDistance:risk,riskAtr:Number((risk/atr).toFixed(3)),minRR:marketFloor,targetMode,profile:{regimePrior:p.regimePrior,families:p.families,entryRouter:p.entryRouter,riskAtrPrior:p.riskAtrPrior},policies:{sl:p.slPolicy,tp:p.tpPolicy},reason:executable?reason:forward?'FORWARD_TARGET_RR_TOO_LOW':'NO_SCALP_TARGET_WITHIN_ATR_CAP'};
}
