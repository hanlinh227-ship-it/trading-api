import {roundTick} from "./bybit-v5-client.js";

const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const now=()=>Date.now();

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
function cutDecision({env,r,peakR,ageSec,momentum}){
  if(!momentum.available)return null;
  const minAge=Math.max(60,Number(env.BYBIT_CUT_MIN_AGE_SEC||90));
  const hardCutR=-Math.abs(clamp(Number(env.BYBIT_EARLY_CUT_R||.50),.30,.80));
  const adverseMomentum=-Math.abs(clamp(Number(env.BYBIT_EARLY_CUT_MOMENTUM_R||.12),.05,.35));
  const staleAge=Math.max(360,Number(env.BYBIT_STALE_CUT_AGE_SEC||720));
  const staleMaxR=clamp(Number(env.BYBIT_STALE_CUT_MAX_R||.10),-.10,.30);
  const givebackPeak=Math.max(.8,Number(env.BYBIT_GIVEBACK_PEAK_R||1.05));
  const givebackFloor=clamp(Number(env.BYBIT_GIVEBACK_FLOOR_R||.25),0,.60);
  if(ageSec>=minAge&&r<=hardCutR&&momentum.adverseTrend&&momentum.adverseBars>=2&&momentum.momentumR<=adverseMomentum)return "EARLY_THESIS_INVALIDATION";
  if(ageSec>=staleAge&&r<staleMaxR&&momentum.adverseTrend&&momentum.momentumR<0)return "STALE_SCALP_NO_FOLLOW_THROUGH";
  if(peakR>=givebackPeak&&r<=givebackFloor&&momentum.adverseTrend&&momentum.adverseBars>=2)return "PROFIT_GIVEBACK_REVERSAL";
  return null;
}

export async function manageBybitScalpPosition(env,api,plan,position,cfg){
  const side=String(position?.side||plan?.side||""),entry=num(position?.avgPrice||position?.entryPrice||plan?.entry),mark=num(position?.markPrice),tick=num(plan?.filters?.tickSize||plan?.tickSize),initialSl=num(plan?.initialSl||plan?.sl),currentSl=num(position?.stopLoss||plan?.managedSl||plan?.sl),tp=num(position?.takeProfit||plan?.tp),qty=Math.abs(num(position?.size||plan?.qty));
  const initialRisk=Math.abs(entry-initialSl);
  if(!(entry>0&&mark>0&&initialRisk>0&&qty>0))return {managed:false,verdict:"HOLD",reason:"POSITION_DATA_INVALID"};

  const r=favorableR(side,entry,mark,initialRisk),peakR=Math.max(num(plan?.peakR),r),createdAtMs=num(plan?.createdAtMs)||now(),ageSec=Math.max(0,(now()-createdAtMs)/1000);
  plan.peakR=peakR;
  let momentum={available:false,aligned:null,adverseTrend:false,adverseBars:0,momentumR:0};
  try{momentum=momentumReview(side,parseKlines(await api.kline(plan.symbol,"1",12)),initialRisk);}catch{}

  const cutReason=cutDecision({env,r,peakR,ageSec,momentum});
  if(cutReason){
    const closeSide=side==="Buy"?"Sell":"Buy",positionIdx=Number(position?.positionIdx??cfg.execution.positionIdx??0);
    const order=await api.order({symbol:plan.symbol,side:closeSide,orderType:"Market",qty:String(qty),reduceOnly:true,positionIdx,timeInForce:"IOC"});
    const orderId=String(order?.result?.orderId||"");
    plan.cutRequestedAt=new Date().toISOString();plan.cutReason=cutReason;
    plan.lastReview={at:plan.cutRequestedAt,verdict:"CUT",reason:cutReason,r,peakR,ageSec,momentum};
    return {managed:true,verdict:"CUT",cutExecuted:true,reason:cutReason,r,peakR,ageSec,markPrice:mark,orderId,momentum};
  }

  const beAt=Math.max(.45,Number(env.BYBIT_BE_TRIGGER_R||.60));
  const lockAt=Math.max(beAt+.15,Number(env.BYBIT_PROFIT_LOCK_TRIGGER_R||.90));
  const trailAt=Math.max(lockAt+.15,Number(env.BYBIT_TRAIL_TRIGGER_R||1.15));
  const beOffsetR=clamp(Number(env.BYBIT_BE_OFFSET_R||.05),0,.20);
  const lockR=clamp(Number(env.BYBIT_PROFIT_LOCK_R||.35),.10,.85);
  const baseTrailR=clamp(Number(env.BYBIT_TRAIL_DISTANCE_R||.50),.25,1.0);
  const trailDistanceR=adaptiveTrailDistanceR(r,baseTrailR);
  let phase="INITIAL",nextSl=currentSl,trailingStop=0;

  if(r>=beAt){phase="BREAKEVEN";nextSl=side==="Buy"?entry+initialRisk*beOffsetR:entry-initialRisk*beOffsetR;}
  if(r>=lockAt){phase="PROFIT_LOCK";let dynamicLock=lockR;if(r>=1.5)dynamicLock=Math.max(dynamicLock,.65);if(r>=2)dynamicLock=Math.max(dynamicLock,1.0);const lock=side==="Buy"?entry+initialRisk*dynamicLock:entry-initialRisk*dynamicLock;if(betterStop(side,lock,nextSl))nextSl=lock;}
  if(r>=trailAt){phase="TRAIL";trailingStop=initialRisk*trailDistanceR;}

  nextSl=roundTick(nextSl,tick);trailingStop=roundTick(trailingStop,tick);
  const shouldTighten=betterStop(side,nextSl,currentSl)||phase==="TRAIL";
  const verdict=shouldTighten?"TIGHTEN":"HOLD";
  const reason=shouldTighten?(phase==="TRAIL"?"ADAPTIVE_TRAILING":"PROTECTIVE_STOP_ADVANCE"):(momentum.adverseTrend?"HOLD_NO_CUT_CONFIRMATION":"HOLD_THESIS_INTACT");
  plan.lastReview={at:new Date().toISOString(),verdict,reason,r,peakR,ageSec,phase,currentSl,nextSl:shouldTighten?nextSl:currentSl,trailingStop:trailingStop||null,momentum};
  if(!shouldTighten)return {managed:false,verdict,reason,phase,r,peakR,ageSec,currentSl,markPrice:mark,momentum};

  const body={symbol:plan.symbol,tpslMode:"Full",positionIdx:Number(position?.positionIdx??cfg.execution.positionIdx??0),stopLoss:String(betterStop(side,nextSl,currentSl)?nextSl:currentSl),slTriggerBy:"MarkPrice"};
  if(tp>0){body.takeProfit=String(tp);body.tpTriggerBy="MarkPrice";}
  if(phase==="TRAIL"&&trailingStop>0)body.trailingStop=String(trailingStop);
  await api.tradingStop(body);
  return {managed:true,verdict,reason,phase,r,peakR,ageSec,previousSl:currentSl,nextSl:Number(body.stopLoss),trailingStop:trailingStop||null,trailDistanceR:phase==="TRAIL"?trailDistanceR:null,markPrice:mark,momentum};
}
