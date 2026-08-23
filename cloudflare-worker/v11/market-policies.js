import {getSymbolScalpPolicy} from './symbol-scalp-policy.js';
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null};
function geometry(c){const e=num(c.entry),s=num(c.sl),t=num(c.tp);if(!e||!s||!t)return false;return c.side==='LONG'?s<e&&t>e:c.side==='SHORT'?s>e&&t<e:false;}
function room(c){const e=num(c.entry),s=num(c.sl),t=num(c.tp);return e&&s&&t?Math.abs(t-e)/Math.abs(e-s):0;}
const common=(c,m)=>{
 const p=getSymbolScalpPolicy(c.symbol,m),reasons=[],soft=[];
 if(!geometry(c))reasons.push('INVALID_GEOMETRY');
 const r=room(c),lockedRR=p.backtestEligible&&[1,2].includes(Number(p.targetRR))?Number(p.targetRR):null;
 const preferredRoom=lockedRR||Number(p.minRR||1.05),hardRoom=lockedRR?lockedRR:Math.max(.95,preferredRoom-.10);
 if(lockedRR&&Math.abs(r-lockedRR)>.02)reasons.push(`BACKTEST_RR_MISMATCH_${lockedRR}R`);
 else if(r<hardRoom)reasons.push('INSUFFICIENT_EXECUTION_ROOM');
 else if(!lockedRR&&r<preferredRoom)soft.push('ROOM_BELOW_PREFERRED');
 const q=num(c.qualityScore),hardQuality=Math.max(42,Number(p.qualityFloor||52)-8);
 if(q===null)soft.push('QUALITY_UNKNOWN');else if(q<hardQuality)reasons.push(`QUALITY_HARD_FLOOR_${hardQuality}`);else if(q<Number(p.qualityFloor||52))soft.push(`QUALITY_BELOW_PREFERRED_${p.qualityFloor}`);
 return {p,reasons,soft,metrics:{room:r,preferredRoom,hardRoom,lockedRR,quality:q,hardQuality}};
};
function result(x,families){return {pass:!x.reasons.length,reasons:x.reasons,softWarnings:x.soft,families,symbolPolicy:x.p,metrics:x.metrics};}
export function evaluateCrypto(c){const x=common(c,'crypto');if(c.liquidityOk===false)x.soft.push('LIQUIDITY_BELOW_IDEAL');if(String(c.chaseRisk||'').toUpperCase()==='HIGH')x.reasons.push('EXTREME_CHASE');if(c.priceSourceDivergence===true)x.reasons.push('PRICE_SOURCE_DIVERGENCE');return result(x,x.p.preferredSetups?.length?x.p.preferredSetups:['MOMENTUM_PULLBACK','BREAKOUT_RETEST','SWEEP_RECLAIM','RELATIVE_STRENGTH']);}
export function evaluateForex(c){const x=common(c,'forex');if(c.sessionLiquid===false)x.soft.push('SESSION_LIQUIDITY_BELOW_IDEAL');if(c.highImpactBlocked===true)x.reasons.push('HARD_NEWS_BLACKOUT');if(c.currencyStrengthConflict===true)x.soft.push('CURRENCY_STRENGTH_CONFLICT');return result(x,x.p.preferredSetups?.length?x.p.preferredSetups:['SESSION_SWEEP_MSS','TREND_PULLBACK','POST_NEWS_RETEST','CURRENCY_STRENGTH']);}
export function evaluateMetal(c){const x=common(c,'metal');if(c.usEventBlocked===true)x.reasons.push('HARD_NEWS_BLACKOUT');if(c.volatilityShock===true)x.reasons.push('VOLATILITY_SHOCK');if(c.sessionLiquid===false)x.soft.push('SESSION_LIQUIDITY_BELOW_IDEAL');return result(x,x.p.preferredSetups?.length?x.p.preferredSetups:['SESSION_SWEEP_RECLAIM','IMPULSE_PULLBACK','BREAKOUT_RETEST']);}
export function evaluateIndex(c){const x=common(c,'index');if(c.cashSessionActive===false&&c.allowExtended!==true)x.soft.push('CASH_SESSION_INACTIVE');if(c.relativeEvidenceStale===true)x.soft.push('RELATIVE_EVIDENCE_STALE');if(c.volatilityShock===true)x.reasons.push('VOLATILITY_SHOCK');return result(x,x.p.preferredSetups?.length?x.p.preferredSetups:['OPENING_RANGE_RETEST','VWAP_RECLAIM','TREND_PULLBACK','RELATIVE_SMT']);}
export function evaluateMarketCandidate(m,c){return ({crypto:evaluateCrypto,forex:evaluateForex,metal:evaluateMetal,index:evaluateIndex}[m]||(()=>({pass:false,reasons:['UNKNOWN_MARKET'],softWarnings:[]})))(c);}
