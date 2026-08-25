import {roundTick} from "./bybit-v5-client.js";

const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const now=()=>Date.now();
const envBool=v=>String(v||"").toLowerCase()==="true";

function favorableR(side,entry,mark,initialRisk){
  if(!(initialRisk>0))return 0;
  return side==="Buy"?(mark-entry)/initialRisk:(entry-mark)/initialRisk;
}
function betterStop(side,next,current){
  if(!(next>0))return false;
  if(!(current>0))return true;
  return side==="Buy"?next>current:next<current;
}
function parseKlines(payload){
  const rows=payload?.result?.list||[];
  return [...rows].reverse().map(x=>({ts:num(x[0]),open:num(x[1]),high:num(x[2]),low:num(x[3]),close:num(x[4]),volume:num(x[5])})).filter(x=>x.close>0);
}
function momentumReview(side,rows,initialRisk){
  if(rows.length<8||!(initialRisk>0))return {available:false,aligned:null,adverseTrend:false,adverseBars:0,momentumR:0};
  const closes=rows.map(x=>x.close),last=closes.at(-1),anchor=closes.at(-4),fast=avg(closes.slice(-3)),slow=avg(closes.slice(-7));
  const aligned=side==="Buy"?fast>=slow:fast<=slow;
  const momentumR=(side==="Buy"?(last-anchor):(anchor-last))/initialRisk;
  const last3=rows.slice(-3),adverseBars=last3.reduce((n,x)=>n+((side==="Buy"?x.close<x.open:x.close>x.open)?1:0),0);
  return {available:true,aligned,adverseTrend:!aligned,adverseBars,momentumR,fast,slow,last};
}
function adaptiveTrailDistanceR(r,base){
  if(r>=2.4)return Math.min(base,.30);
  if(r>=1.8)return Math.min(base,.36);
  if(r>=1.4)return Math.min(base,.44);
  return base;
}
function cutDecision({env,r,ageSec,momentum}){
  // Discretionary market-close is intentionally OFF by default. TP/SL/BE/lock/trailing
  // remain the normal exit path. Enabling CUT requires an explicit runtime flag and a
  // materially invalidated thesis; stale-time or profit-giveback alone never market-close.
  if(!envBool(env.BYBIT_DISCRETIONARY_CUT_ENABLED)||!momentum.available)return null;
  const minAge=Math.max(180,Number(env.BYBIT_CUT_MIN_AGE_SEC||180));
  const hardCutR=-Math.abs(clamp(Number(env.BYBIT_EARLY_CUT_R||.70),.60,.90));
  const adverseMomentum=-Math.abs(clamp(Number(env.BYBIT_EARLY_CUT_MOMENTUM_R||.20),.15,.50));
  if(ageSec>=minAge&&r<=hardCutR&&momentum.adverseTrend&&momentum.adverseBars>=3&&momentum.momentumR<=adverseMomentum)return "CONFIRMED_THESIS_INVALIDATION";
  return null;
}

export async function manageBybitScalpPosition(env,api,plan,position,cfg){
  const side=String(position?.side||plan?.side||""),entry=num(position?.avgPrice||position?.entryPrice||plan?.entry),mark=num(position?.markPrice),tick=num(plan?.filters?.tickSize||plan?.tickSize),initialSl=num(plan?.initialSl||plan?.sl),currentSl=num(position?.stopLoss||plan?.managedSl||plan?.sl),currentTrailing=num(position?.trailingStop),tp=num(position?.takeProfit||plan?.tp),qty=Math.abs(num(position?.size||plan?.qty));
  const initialRisk=Math.abs(entry-initialSl);
  if(!(entry>0&&mark>0&&initialRisk>0&&qty>0))return {managed:false,verdict:"HOLD",reason:"POSITION_DATA_INVALID"};

  const r=favorableR(side,entry,mark,initialRisk),peakR=Math.max(num(plan?.peakR),r),createdAtMs=num(plan?.createdAtMs)||now(),ageSec=Math.max(0,(now()-createdAtMs)/1000);
  plan.peakR=peakR;
  let momentum={available:false,aligned:null,adverseTrend:false,adverseBars:0,momentumR:0};
  try{momentum=momentumReview(side,parseKlines(await api.kline(plan.symbol,"1",12)),initialRisk);}catch{}

  const cutReason=cutDecision({env,r,ageSec,momentum});
  if(cutReason){
    const closeSide=side==="Buy"?"Sell":"Buy",positionIdx=Number(position?.positionIdx??cfg.execution.positionIdx??0);
    const order=await api.order({symbol:plan.symbol,side:closeSide,orderType:"Market",qty:String(qty),reduceOnly:true,positionIdx,timeInForce:"IOC"});
    const orderId=String(order?.result?.orderId||"");
    plan.cutRequestedAt=new Date().toISOString();plan.cutReason=cutReason;
    plan.lastReview={at:plan.cutRequestedAt,verdict:"CUT",reason:cutReason,r,peakR,ageSec,momentum,discretionaryCutEnabled:true};
    return {managed:true,verdict:"CUT",cutExecuted:true,reason:cutReason,r,peakR,ageSec,markPrice:mark,orderId,momentum};
  }

  const plannedBe=num(plan?.exitPlan?.breakEvenTriggerR),plannedTrailAt=num(plan?.exitPlan?.positiveTrailTriggerR),plannedLockR=num(plan?.exitPlan?.positiveTrailLockR),plannedTrailAtr=num(plan?.exitPlan?.trailAtr),atr1=num(plan?.atr1);
  const beAt=Math.max(.45,Number(env.BYBIT_BE_TRIGGER_R||plannedBe||.60));
  const trailAt=Math.max(beAt+.20,Number(env.BYBIT_TRAIL_TRIGGER_R||plannedTrailAt||1.15));
  const defaultLockAt=Math.max(beAt+.15,Math.min(trailAt-.05,(beAt+trailAt)/2)),lockAt=Math.max(beAt+.15,Number(env.BYBIT_PROFIT_LOCK_TRIGGER_R||defaultLockAt));
  const beOffsetR=clamp(Number(env.BYBIT_BE_OFFSET_R||.05),0,.20);
  const lockR=clamp(Number(env.BYBIT_PROFIT_LOCK_R||plannedLockR||.35),.10,.85);
  const plannedTrailR=plannedTrailAtr>0&&atr1>0?plannedTrailAtr*atr1/initialRisk:.50,baseTrailR=clamp(Number(env.BYBIT_TRAIL_DISTANCE_R||plannedTrailR||.50),.25,1.0),trailDistanceR=adaptiveTrailDistanceR(r,baseTrailR);
  let phase="INITIAL",nextSl=currentSl,trailingStop=0;

  if(r>=beAt){phase="BREAKEVEN";nextSl=side==="Buy"?entry+initialRisk*beOffsetR:entry-initialRisk*beOffsetR;}
  if(r>=lockAt){phase="PROFIT_LOCK";let dynamicLock=lockR;if(r>=1.5)dynamicLock=Math.max(dynamicLock,.65);if(r>=2)dynamicLock=Math.max(dynamicLock,1.0);const lock=side==="Buy"?entry+initialRisk*dynamicLock:entry-initialRisk*dynamicLock;if(betterStop(side,lock,nextSl))nextSl=lock;}
  if(r>=trailAt){phase="TRAIL";trailingStop=initialRisk*trailDistanceR;}

  nextSl=roundTick(nextSl,tick);trailingStop=roundTick(trailingStop,tick);
  const stopTighter=betterStop(side,nextSl,currentSl),trailTighter=phase==="TRAIL"&&trailingStop>0&&(!(currentTrailing>0)||trailingStop<currentTrailing-Math.max(tick/2,1e-12)),shouldTighten=stopTighter||trailTighter;
  const verdict=shouldTighten?"TIGHTEN":"HOLD";
  const reason=shouldTighten?(trailTighter?"ADAPTIVE_TRAILING":"PROTECTIVE_STOP_ADVANCE"):(phase==="TRAIL"&&currentTrailing>0?"TRAIL_ALREADY_TIGHT":momentum.adverseTrend?"HOLD_NO_CUT_CONFIRMATION":"HOLD_THESIS_INTACT");
  plan.lastReview={at:new Date().toISOString(),verdict,reason,r,peakR,ageSec,phase,currentSl,nextSl:stopTighter?nextSl:currentSl,currentTrailing,trailingStop:trailTighter?trailingStop:currentTrailing||null,momentum,discretionaryCutEnabled:envBool(env.BYBIT_DISCRETIONARY_CUT_ENABLED),thresholds:{beAt,lockAt,trailAt,lockR,trailDistanceR}};
  if(!shouldTighten)return {managed:false,verdict,reason,phase,r,peakR,ageSec,currentSl,currentTrailing,markPrice:mark,momentum,thresholds:{beAt,lockAt,trailAt,lockR,trailDistanceR}};

  const body={symbol:plan.symbol,tpslMode:"Full",positionIdx:Number(position?.positionIdx??cfg.execution.positionIdx??0),stopLoss:String(stopTighter?nextSl:currentSl),slTriggerBy:"MarkPrice"};
  if(tp>0){body.takeProfit=String(tp);body.tpTriggerBy="MarkPrice";}
  if(trailTighter)body.trailingStop=String(trailingStop);
  await api.tradingStop(body);
  return {managed:true,verdict,reason,phase,r,peakR,ageSec,previousSl:currentSl,nextSl:Number(body.stopLoss),previousTrailing:currentTrailing||null,trailingStop:trailTighter?trailingStop:currentTrailing||null,trailDistanceR:phase==="TRAIL"?trailDistanceR:null,markPrice:mark,momentum,thresholds:{beAt,lockAt,trailAt,lockR,trailDistanceR}};
}
