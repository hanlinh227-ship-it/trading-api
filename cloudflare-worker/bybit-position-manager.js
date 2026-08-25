import {roundTick} from "./bybit-v5-client.js";

const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const now=()=>Date.now();
const envBool=(v,d=false)=>v===undefined||v===null||v===""?d:String(v).toLowerCase()==="true";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

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
  if(rows.length<10||!(initialRisk>0))return {available:false,aligned:null,adverseTrend:false,adverseBars:0,momentumR:0,structureBroken:false};
  const closes=rows.map(x=>x.close),last=closes.at(-1),anchor=closes.at(-4),fast=avg(closes.slice(-3)),slow=avg(closes.slice(-7));
  const prevFast=avg(closes.slice(-6,-3)),prevSlow=avg(closes.slice(-10,-3));
  const aligned=side==="Buy"?fast>=slow:fast<=slow;
  const momentumR=(side==="Buy"?(last-anchor):(anchor-last))/initialRisk;
  const fastSlopeR=(side==="Buy"?(fast-prevFast):(prevFast-fast))/initialRisk;
  const slowSlopeR=(side==="Buy"?(slow-prevSlow):(prevSlow-slow))/initialRisk;
  const last4=rows.slice(-4),adverseBars=last4.reduce((n,x)=>n+((side==="Buy"?x.close<x.open:x.close>x.open)?1:0),0);
  const adverseBodyR=last4.reduce((s,x)=>{const body=side==="Buy"?Math.max(0,x.open-x.close):Math.max(0,x.close-x.open);return s+body/initialRisk;},0);
  const recentVol=avg(rows.slice(-4).map(x=>x.volume)),baseVol=avg(rows.slice(-10,-4).map(x=>x.volume)),volumeRatio=baseVol>0?recentVol/baseVol:1;
  const prior=rows.slice(-7,-1),structureBroken=side==="Buy"?last<Math.min(...prior.map(x=>x.low)):last>Math.max(...prior.map(x=>x.high));
  const lastRange=rows.at(-1).high-rows.at(-1).low,avgRange=avg(rows.slice(-7,-1).map(x=>x.high-x.low)),rangeExpansion=avgRange>0?lastRange/avgRange:1;
  return {available:true,aligned,adverseTrend:!aligned,adverseBars,momentumR,fastSlopeR,slowSlopeR,adverseBodyR,volumeRatio,structureBroken,rangeExpansion,fast,slow,last};
}
function adaptiveTrailDistanceR(r,base){
  if(r>=2.4)return Math.min(base,.30);
  if(r>=1.8)return Math.min(base,.36);
  if(r>=1.4)return Math.min(base,.44);
  return base;
}
function dynamicCutThresholdR(ageSec,env){
  const early=Math.abs(clamp(Number(env.BYBIT_SMART_CUT_EARLY_R||.72),.62,.85));
  const mature=Math.abs(clamp(Number(env.BYBIT_SMART_CUT_MATURE_R||.62),.52,.78));
  const stale=Math.abs(clamp(Number(env.BYBIT_SMART_CUT_STALE_R||.56),.48,.72));
  if(ageSec<300)return -early;
  if(ageSec<600)return -mature;
  return -stale;
}
function smartCutAssessment({env,cfg,r,ageSec,momentum,plan}){
  const enabled=envBool(env.BYBIT_DISCRETIONARY_CUT_ENABLED,cfg?.risk?.smartCutEnabled===true);
  if(!enabled||!momentum.available)return {enabled,eligible:false,score:0,reason:"SMART_CUT_DISABLED_OR_NO_DATA"};
  const minAge=Math.max(180,Number(env.BYBIT_CUT_MIN_AGE_SEC||cfg?.risk?.smartCutMinAgeSec||180));
  const thresholdR=dynamicCutThresholdR(ageSec,env),scoreNeed=Math.max(6,Math.min(9,Number(env.BYBIT_SMART_CUT_SCORE||cfg?.risk?.smartCutScore||7)));
  let score=0;const signals=[];
  const add=(pts,name,ok)=>{if(ok){score+=pts;signals.push(name);}};
  add(2,"LOSS_DEPTH",r<=thresholdR);
  add(1,"DEEP_LOSS",r<=thresholdR-.12);
  add(2,"ADVERSE_TREND",momentum.adverseTrend);
  add(1,"ADVERSE_BARS_3",momentum.adverseBars>=3);
  add(1,"ADVERSE_BARS_4",momentum.adverseBars>=4);
  add(2,"MOMENTUM_BREAK",momentum.momentumR<=-.18);
  add(1,"FAST_SLOPE_BREAK",momentum.fastSlopeR<=-.08);
  add(1,"SLOW_SLOPE_BREAK",momentum.slowSlopeR<=-.04);
  add(2,"STRUCTURE_BREAK",momentum.structureBroken);
  add(1,"ADVERSE_BODY_EXPANSION",momentum.adverseBodyR>=.35);
  add(1,"VOLUME_CONFIRM",momentum.volumeRatio>=1.20);
  add(1,"RANGE_EXPANSION",momentum.rangeExpansion>=1.25);
  const hardGate=ageSec>=minAge&&r<=thresholdR&&momentum.adverseTrend&&momentum.momentumR<=-.12&&(momentum.structureBroken||momentum.adverseBars>=3);
  const emergency=ageSec>=minAge&&r<=-.88&&momentum.adverseTrend&&momentum.momentumR<=-.28&&(momentum.structureBroken||momentum.adverseBars>=4)&&score>=scoreNeed;
  const candidate=hardGate&&score>=scoreNeed;
  const previous=Number(plan?.smartCutCandidateCount||0),confirmations=candidate?previous+1:0,required=Math.max(2,Math.min(3,Number(env.BYBIT_SMART_CUT_CONFIRMATIONS||cfg?.risk?.smartCutConfirmations||2)));
  return {enabled,eligible:emergency||(candidate&&confirmations>=required),candidate,emergency,score,scoreNeed,signals,thresholdR,minAge,confirmations,required};
}
function pendingCut(plan,cfg,env){
  const ts=Date.parse(String(plan?.cutRequestedAt||""));if(!Number.isFinite(ts)||ts<=0)return null;
  const waitSec=Math.max(60,Math.min(300,Number(env.BYBIT_SMART_CUT_REISSUE_SEC||cfg?.risk?.smartCutReissueSec||120))),ageSec=(now()-ts)/1000;
  if(ageSec<waitSec)return {pending:true,ageSec,waitSec,orderId:plan?.cutOrderId||null,reason:plan?.cutReason||"SMART_CUT_PENDING_FILL"};
  return null;
}
async function verifyCloseFill(api,symbol,orderId){
  if(!orderId)return {ok:false,status:"NO_ORDER_ID"};
  for(let i=0;i<5;i++){
    try{const p=await api.orderStatus(symbol,orderId),x=p?.result?.list?.[0],status=String(x?.orderStatus||"");if(["Filled","PartiallyFilled"].includes(status)&&Number(x?.cumExecQty||0)>0)return {ok:true,status,executedQty:Number(x.cumExecQty||0),avgPrice:Number(x.avgPrice||0)};if(["Cancelled","Rejected","Deactivated"].includes(status))return {ok:false,status};}catch{}
    await sleep(200);
  }
  return {ok:false,status:"PENDING_OR_UNKNOWN"};
}

export async function manageBybitScalpPosition(env,api,plan,position,cfg){
  const side=String(position?.side||plan?.side||""),entry=num(position?.avgPrice||position?.entryPrice||plan?.entry),mark=num(position?.markPrice),tick=num(plan?.filters?.tickSize||plan?.tickSize),initialSl=num(plan?.initialSl||plan?.sl),currentSl=num(position?.stopLoss||plan?.managedSl||plan?.sl),currentTrailing=num(position?.trailingStop),tp=num(position?.takeProfit||plan?.tp),qty=Math.abs(num(position?.size||plan?.qty));
  const initialRisk=Math.abs(entry-initialSl);
  if(!(entry>0&&mark>0&&initialRisk>0&&qty>0))return {managed:false,verdict:"HOLD",reason:"POSITION_DATA_INVALID"};

  const r=favorableR(side,entry,mark,initialRisk),peakR=Math.max(num(plan?.peakR),r),createdAtMs=num(plan?.createdAtMs)||now(),ageSec=Math.max(0,(now()-createdAtMs)/1000);
  plan.peakR=peakR;
  const pending=pendingCut(plan,cfg,env);
  if(pending){plan.lastReview={at:new Date().toISOString(),verdict:"CUT_PENDING",reason:"SMART_CUT_ORDER_PENDING",r,peakR,ageSec,pending};return {managed:false,verdict:"CUT_PENDING",reason:"SMART_CUT_ORDER_PENDING",r,peakR,ageSec,markPrice:mark,pending};}
  let momentum={available:false,aligned:null,adverseTrend:false,adverseBars:0,momentumR:0,structureBroken:false};
  try{momentum=momentumReview(side,parseKlines(await api.kline(plan.symbol,"1",14)),initialRisk);}catch{}

  const cut=smartCutAssessment({env,cfg,r,ageSec,momentum,plan});
  plan.smartCutCandidateCount=cut.candidate?cut.confirmations:0;
  plan.lastSmartCutAssessment={at:new Date().toISOString(),...cut,r,ageSec,momentum};
  if(cut.eligible){
    const closeSide=side==="Buy"?"Sell":"Buy",positionIdx=Number(position?.positionIdx??cfg.execution.positionIdx??0);
    const order=await api.order({symbol:plan.symbol,side:closeSide,orderType:"Market",qty:String(qty),reduceOnly:true,positionIdx,timeInForce:"IOC"});
    const orderId=String(order?.result?.orderId||"");
    const cutReason=cut.emergency?"SMART_CUT_EMERGENCY_INVALIDATION":"SMART_CUT_CONFIRMED_INVALIDATION";
    plan.cutRequestedAt=new Date().toISOString();plan.cutReason=cutReason;plan.cutOrderId=orderId||null;plan.smartCutCandidateCount=0;
    const fill=await verifyCloseFill(api,plan.symbol,orderId);
    plan.cutFillVerification={at:new Date().toISOString(),...fill};
    plan.lastReview={at:plan.cutRequestedAt,verdict:fill.ok?"CUT":"CUT_PENDING",reason:fill.ok?cutReason:"SMART_CUT_ORDER_PENDING",r,peakR,ageSec,momentum,smartCut:cut,closeFill:fill,discretionaryCutEnabled:true};
    return {managed:true,verdict:fill.ok?"CUT":"CUT_PENDING",cutExecuted:fill.ok,cutRequested:true,reason:fill.ok?cutReason:"SMART_CUT_ORDER_PENDING",r,peakR,ageSec,markPrice:mark,orderId,momentum,smartCut:cut,closeFill:fill};
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
  const reason=shouldTighten?(trailTighter?"ADAPTIVE_TRAILING":"PROTECTIVE_STOP_ADVANCE"):(phase==="TRAIL"&&currentTrailing>0?"TRAIL_ALREADY_TIGHT":cut.candidate?"SMART_CUT_CONFIRMING":momentum.adverseTrend?"HOLD_NO_CUT_CONFIRMATION":"HOLD_THESIS_INTACT");
  plan.lastReview={at:new Date().toISOString(),verdict,reason,r,peakR,ageSec,phase,currentSl,nextSl:stopTighter?nextSl:currentSl,currentTrailing,trailingStop:trailTighter?trailingStop:currentTrailing||null,momentum,smartCut:cut,discretionaryCutEnabled:cut.enabled,thresholds:{beAt,lockAt,trailAt,lockR,trailDistanceR}};
  if(!shouldTighten)return {managed:false,verdict,reason,phase,r,peakR,ageSec,currentSl,currentTrailing,markPrice:mark,momentum,smartCut:cut,thresholds:{beAt,lockAt,trailAt,lockR,trailDistanceR}};

  const body={symbol:plan.symbol,tpslMode:"Full",positionIdx:Number(position?.positionIdx??cfg.execution.positionIdx??0),stopLoss:String(stopTighter?nextSl:currentSl),slTriggerBy:"MarkPrice"};
  if(tp>0){body.takeProfit=String(tp);body.tpTriggerBy="MarkPrice";}
  if(trailTighter)body.trailingStop=String(trailingStop);
  await api.tradingStop(body);
  return {managed:true,verdict,reason,phase,r,peakR,ageSec,previousSl:currentSl,nextSl:Number(body.stopLoss),previousTrailing:currentTrailing||null,trailingStop:trailTighter?trailingStop:currentTrailing||null,trailDistanceR:phase==="TRAIL"?trailDistanceR:null,markPrice:mark,momentum,smartCut:cut,thresholds:{beAt,lockAt,trailAt,lockR,trailDistanceR}};
}
