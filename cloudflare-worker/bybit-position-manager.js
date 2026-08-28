import {roundTick} from "./bybit-v5-client.js";

const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const now=()=>Date.now();
const envBool=(v,d=false)=>v===undefined||v===null||v===""?d:String(v).toLowerCase()==="true";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const SIGNAL_INTERVAL="5",CONTEXT_INTERVAL="15";

function favorableR(side,entry,mark,initialRisk){if(!(initialRisk>0))return 0;return side==="Buy"?(mark-entry)/initialRisk:(entry-mark)/initialRisk;}
function betterStop(side,next,current){if(!(next>0))return false;if(!(current>0))return true;return side==="Buy"?next>current:next<current;}
function parseKlines(payload){const rows=payload?.result?.list||[];return [...rows].reverse().map(x=>({ts:num(x[0]),open:num(x[1]),high:num(x[2]),low:num(x[3]),close:num(x[4]),volume:num(x[5])})).filter(x=>x.close>0);}
function closedBars(rows,minutes){const ms=minutes*60000,t=now();return rows.filter(x=>x.ts+ms<=t);}
function momentumReview(side,rows,initialRisk){
  if(rows.length<10||!(initialRisk>0))return {available:false,aligned:null,adverseTrend:false,adverseBars:0,momentumR:0,structureBroken:false};
  const closes=rows.map(x=>x.close),last=closes.at(-1),anchor=closes.at(-4),fast=avg(closes.slice(-3)),slow=avg(closes.slice(-7)),prevFast=avg(closes.slice(-6,-3)),prevSlow=avg(closes.slice(-10,-3));
  const aligned=side==="Buy"?fast>=slow:fast<=slow,momentumR=(side==="Buy"?(last-anchor):(anchor-last))/initialRisk,fastSlopeR=(side==="Buy"?(fast-prevFast):(prevFast-fast))/initialRisk,slowSlopeR=(side==="Buy"?(slow-prevSlow):(prevSlow-slow))/initialRisk;
  const last4=rows.slice(-4),adverseBars=last4.reduce((n,x)=>n+((side==="Buy"?x.close<x.open:x.close>x.open)?1:0),0),adverseBodyR=last4.reduce((s,x)=>{const body=side==="Buy"?Math.max(0,x.open-x.close):Math.max(0,x.close-x.open);return s+body/initialRisk;},0);
  const recentVol=avg(rows.slice(-4).map(x=>x.volume)),baseVol=avg(rows.slice(-10,-4).map(x=>x.volume)),volumeRatio=baseVol>0?recentVol/baseVol:1,prior=rows.slice(-7,-1),structureBroken=side==="Buy"?last<Math.min(...prior.map(x=>x.low)):last>Math.max(...prior.map(x=>x.high));
  const lastRange=rows.at(-1).high-rows.at(-1).low,avgRange=avg(rows.slice(-7,-1).map(x=>x.high-x.low)),rangeExpansion=avgRange>0?lastRange/avgRange:1;
  return {available:true,aligned,adverseTrend:!aligned,adverseBars,momentumR,fastSlopeR,slowSlopeR,adverseBodyR,volumeRatio,structureBroken,rangeExpansion,fast,slow,last};
}
function excursionFromRows(side,entry,initialRisk,rows,createdAtMs){
  const live=rows.filter(x=>x.ts>=createdAtMs-5*60000);if(!live.length)return null;
  const hi=Math.max(...live.map(x=>x.high)),lo=Math.min(...live.map(x=>x.low));
  const best=side==="Buy"?(hi-entry)/initialRisk:(entry-lo)/initialRisk,worst=side==="Buy"?(lo-entry)/initialRisk:(entry-hi)/initialRisk;
  return {bestR:best,worstR:worst};
}
function adaptiveTrailDistanceR(r,base){if(r>=3)return clamp(base*.82,.60,.95);if(r>=2.4)return clamp(base*.90,.65,1.00);return base;}
function dynamicCutThresholdR(ageSec,env){const early=Math.abs(clamp(Number(env.BYBIT_SMART_CUT_EARLY_R||.78),.68,.90)),mature=Math.abs(clamp(Number(env.BYBIT_SMART_CUT_MATURE_R||.68),.58,.82)),stale=Math.abs(clamp(Number(env.BYBIT_SMART_CUT_STALE_R||.60),.52,.76));if(ageSec<900)return -early;if(ageSec<1800)return -mature;return -stale;}
function smartCutAssessment({env,cfg,r,ageSec,momentum,context,plan}){
  const enabled=envBool(env.BYBIT_DISCRETIONARY_CUT_ENABLED,cfg?.risk?.smartCutEnabled===true);if(!enabled||!momentum.available)return {enabled,eligible:false,score:0,reason:"SMART_CUT_DISABLED_OR_NO_5M_DATA"};
  const minAge=Math.max(600,Number(env.BYBIT_CUT_MIN_AGE_SEC||cfg?.risk?.smartCutMinAgeSec||900)),thresholdR=dynamicCutThresholdR(ageSec,env),scoreNeed=Math.max(6,Math.min(9,Number(env.BYBIT_SMART_CUT_SCORE||cfg?.risk?.smartCutScore||7))),positiveEnabled=envBool(env.BYBIT_POSITIVE_SMART_CUT_ENABLED,cfg?.risk?.smartCutPositiveEnabled!==false),positiveMinAge=Math.max(900,Number(env.BYBIT_POSITIVE_CUT_MIN_AGE_SEC||cfg?.risk?.smartCutPositiveMinAgeSec||1200)),positiveMinR=clamp(Number(env.BYBIT_POSITIVE_CUT_MIN_R||cfg?.risk?.smartCutPositiveMinR||.05),.01,.50),positiveMinPeakR=clamp(Number(env.BYBIT_POSITIVE_CUT_MIN_PEAK_R||cfg?.risk?.smartCutPositiveMinPeakR||.30),.15,1.20),positiveGivebackR=clamp(Number(env.BYBIT_POSITIVE_CUT_GIVEBACK_R||cfg?.risk?.smartCutPositiveGivebackR||.30),.10,.80),peakR=Math.max(Number(plan?.peakR||0),r),givebackR=Math.max(0,peakR-r),contextAdverse=context.available&&(context.adverseTrend||context.structureBroken);let score=0;const signals=[];const add=(pts,name,ok)=>{if(ok){score+=pts;signals.push(name);}};
  add(2,"LOSS_DEPTH",r<=thresholdR);add(1,"DEEP_LOSS",r<=thresholdR-.12);add(2,"5M_ADVERSE_TREND",momentum.adverseTrend);add(1,"5M_ADVERSE_BARS_3",momentum.adverseBars>=3);add(2,"5M_STRUCTURE_BREAK",momentum.structureBroken);add(2,"15M_CONTEXT_ADVERSE",contextAdverse);add(1,"5M_VOLUME_CONFIRM",momentum.volumeRatio>=1.20);add(1,"5M_RANGE_EXPANSION",momentum.rangeExpansion>=1.25);add(2,"PROFIT_GIVEBACK",positiveEnabled&&r>=positiveMinR&&peakR>=positiveMinPeakR&&givebackR>=positiveGivebackR);
  const fastBreak=momentum.adverseTrend&&momentum.momentumR<=-.12&&(momentum.structureBroken||momentum.adverseBars>=3),thesisConfirmed=contextAdverse||(momentum.structureBroken&&momentum.adverseBars>=4&&r<=-.82),lossGate=ageSec>=minAge&&r<=thresholdR&&fastBreak&&thesisConfirmed,positiveGate=positiveEnabled&&ageSec>=positiveMinAge&&r>=positiveMinR&&peakR>=positiveMinPeakR&&givebackR>=positiveGivebackR&&fastBreak&&contextAdverse,emergency=ageSec>=minAge&&r<=-.92&&momentum.structureBroken&&momentum.adverseBars>=4&&contextAdverse&&score>=scoreNeed,candidate=(lossGate||positiveGate)&&score>=scoreNeed,previous=Number(plan?.smartCutCandidateCount||0),confirmations=candidate?previous+1:0,required=Math.max(2,Math.min(3,Number(env.BYBIT_SMART_CUT_CONFIRMATIONS||cfg?.risk?.smartCutConfirmations||2))),mode=positiveGate?"POSITIVE_THESIS_INVALIDATION":lossGate?"LOSS_THESIS_INVALIDATION":"NONE";
  return {enabled,eligible:emergency||(candidate&&confirmations>=required),candidate,emergency,mode,score,scoreNeed,signals,thresholdR,minAge,positiveEnabled,positiveMinAge,positiveMinR,positiveMinPeakR,positiveGivebackR,peakR,givebackR,confirmations,required,signalTimeframe:"5m",contextTimeframe:"15m",m1Authority:false,contextAdverse};
}
function pendingCut(plan,cfg,env){
  const ts=Date.parse(String(plan?.cutRequestedAt||""));if(!Number.isFinite(ts)||ts<=0)return null;const status=String(plan?.cutFillVerification?.status||"");
  const ageSec=(now()-ts)/1000,baseWait=Math.max(120,Math.min(600,Number(env.BYBIT_SMART_CUT_REISSUE_SEC||cfg?.risk?.smartCutReissueSec||180)));
  if(["Cancelled","Rejected","Deactivated","NO_ORDER_ID"].includes(status))return null;
  const waitSec=status==="PartiallyFilled"?Math.min(baseWait,30):baseWait;
  if(ageSec<waitSec)return {pending:true,ageSec,waitSec,orderId:plan?.cutOrderId||null,status:status||"PENDING_OR_UNKNOWN",reason:plan?.cutReason||"SMART_CUT_PENDING_FILL"};
  return null;
}
async function verifyCloseFill(api,symbol,orderId){
  if(!orderId)return {ok:false,status:"NO_ORDER_ID",partial:false};let partial=null;
  for(let i=0;i<5;i++){
    try{const p=await api.orderStatus(symbol,orderId),x=p?.result?.list?.[0],status=String(x?.orderStatus||""),executedQty=Number(x?.cumExecQty||0),avgPrice=Number(x?.avgPrice||0);if(status==="Filled"&&executedQty>0)return {ok:true,status,partial:false,executedQty,avgPrice};if(status==="PartiallyFilled"&&executedQty>0)partial={ok:false,status,partial:true,executedQty,avgPrice};if(["Cancelled","Rejected","Deactivated"].includes(status))return {ok:false,status,partial:!!partial,executedQty:partial?.executedQty||executedQty,avgPrice:partial?.avgPrice||avgPrice};}catch{}
    await sleep(200);
  }
  return partial||{ok:false,status:"PENDING_OR_UNKNOWN",partial:false};
}

export async function manageBybitScalpPosition(env,api,plan,position,cfg){
  const side=String(position?.side||plan?.side||""),entry=num(position?.avgPrice||position?.entryPrice||plan?.entry),mark=num(position?.markPrice),tick=num(plan?.filters?.tickSize||plan?.tickSize),initialSl=num(plan?.initialSl||plan?.sl),currentSl=num(position?.stopLoss||plan?.managedSl||plan?.sl),currentTrailing=num(position?.trailingStop),tp=num(position?.takeProfit||plan?.tp),qty=Math.abs(num(position?.size||plan?.qty));
  const initialRisk=Math.abs(entry-initialSl);if(!(entry>0&&mark>0&&initialRisk>0&&qty>0))return {managed:false,verdict:"HOLD",reason:"POSITION_DATA_INVALID"};
  const createdAtMs=num(plan?.createdAtMs)||now(),ageSec=Math.max(0,(now()-createdAtMs)/1000),r=favorableR(side,entry,mark,initialRisk);
  let raw5=[],signalRows=[],contextRows=[];try{const [k5,k15]=await Promise.all([api.kline(plan.symbol,SIGNAL_INTERVAL,36),api.kline(plan.symbol,CONTEXT_INTERVAL,24)]);raw5=parseKlines(k5);signalRows=closedBars(raw5,5);contextRows=closedBars(parseKlines(k15),15);}catch{}
  const excursion=excursionFromRows(side,entry,initialRisk,raw5,createdAtMs),peakR=Math.max(num(plan?.peakR),r,num(excursion?.bestR)),worstR=Math.min(Number.isFinite(Number(plan?.worstR))?Number(plan.worstR):0,r,num(excursion?.worstR));plan.peakR=peakR;plan.worstR=worstR;plan.mfeR=Math.max(0,peakR);plan.maeR=Math.max(0,-worstR);
  const pending=pendingCut(plan,cfg,env);if(pending){plan.lastReview={at:new Date().toISOString(),verdict:"CUT_PENDING",reason:"SMART_CUT_ORDER_PENDING",r,peakR,worstR,ageSec,pending};return {managed:false,verdict:"CUT_PENDING",reason:"SMART_CUT_ORDER_PENDING",r,peakR,worstR,mfeR:plan.mfeR,maeR:plan.maeR,ageSec,markPrice:mark,pending};}
  const momentum=momentumReview(side,signalRows,initialRisk),context=momentumReview(side,contextRows,initialRisk),cut=smartCutAssessment({env,cfg,r,ageSec,momentum,context,plan});plan.smartCutCandidateCount=cut.candidate?cut.confirmations:0;plan.lastSmartCutAssessment={at:new Date().toISOString(),...cut,r,ageSec,momentum,context,mfeR:plan.mfeR,maeR:plan.maeR};
  if(cut.eligible){
    const closeSide=side==="Buy"?"Sell":"Buy",positionIdx=Number(position?.positionIdx??cfg.execution.positionIdx??0),order=await api.order({symbol:plan.symbol,side:closeSide,orderType:"Market",qty:String(qty),reduceOnly:true,positionIdx,timeInForce:"IOC"}),orderId=String(order?.result?.orderId||""),cutReason=cut.emergency?"SMART_CUT_EMERGENCY_INVALIDATION":cut.mode==="POSITIVE_THESIS_INVALIDATION"?"SMART_CUT_POSITIVE_THESIS_INVALIDATION":"SMART_CUT_CONFIRMED_INVALIDATION";
    plan.cutRequestedAt=new Date().toISOString();plan.cutReason=cutReason;plan.cutOrderId=orderId||null;plan.smartCutCandidateCount=0;const fill=await verifyCloseFill(api,plan.symbol,orderId);plan.cutFillVerification={at:new Date().toISOString(),...fill};
    plan.lastReview={at:plan.cutRequestedAt,verdict:fill.ok?"CUT":"CUT_PENDING",reason:fill.ok?cutReason:(fill.partial?"SMART_CUT_PARTIAL_FILL":"SMART_CUT_ORDER_PENDING"),r,peakR,worstR,ageSec,momentum,context,smartCut:cut,closeFill:fill,discretionaryCutEnabled:true};
    return {managed:true,verdict:fill.ok?"CUT":"CUT_PENDING",cutExecuted:fill.ok,cutRequested:true,reason:fill.ok?cutReason:(fill.partial?"SMART_CUT_PARTIAL_FILL":"SMART_CUT_ORDER_PENDING"),r,peakR,worstR,mfeR:plan.mfeR,maeR:plan.maeR,ageSec,markPrice:mark,orderId,momentum,context,smartCut:cut,closeFill:fill};
  }
  const plannedBe=num(plan?.exitPlan?.breakEvenTriggerR),plannedTrailAt=num(plan?.exitPlan?.positiveTrailTriggerR),plannedLockR=num(plan?.exitPlan?.positiveTrailLockR),plannedTrailAtr=num(plan?.exitPlan?.trailAtr),atr1=num(plan?.atr1),warmupSec=Math.max(600,Number(env.BYBIT_PROTECTION_WARMUP_SEC||600));
  if(ageSec<warmupSec){plan.lastReview={at:new Date().toISOString(),verdict:"HOLD",reason:"PROTECTION_WARMUP",r,peakR,worstR,ageSec,warmupSec,momentum,context,smartCut:cut};return {managed:false,verdict:"HOLD",reason:"PROTECTION_WARMUP",phase:"INITIAL",r,peakR,worstR,mfeR:plan.mfeR,maeR:plan.maeR,ageSec,warmupSec,currentSl,currentTrailing,markPrice:mark,momentum,context,smartCut:cut};}
  const beAt=Math.max(1.40,Number(env.BYBIT_BE_TRIGGER_R||plannedBe||1.40)),trailAt=Math.max(beAt+.45,Number(env.BYBIT_TRAIL_TRIGGER_R||plannedTrailAt||1.95)),defaultLockAt=Math.max(beAt+.25,Math.min(trailAt-.15,(beAt+trailAt)/2)),lockAt=Math.max(beAt+.25,Number(env.BYBIT_PROFIT_LOCK_TRIGGER_R||defaultLockAt)),beOffsetR=clamp(Number(env.BYBIT_BE_OFFSET_R||.02),0,.10),lockR=clamp(Number(env.BYBIT_PROFIT_LOCK_R||plannedLockR||.30),.15,.70),plannedTrailR=plannedTrailAtr>0&&atr1>0?plannedTrailAtr*atr1/initialRisk:.75,baseTrailR=clamp(Number(env.BYBIT_TRAIL_DISTANCE_R||plannedTrailR||.75),.50,1.15),trailDistanceR=adaptiveTrailDistanceR(r,baseTrailR),protectionConfirmed=momentum.available&&momentum.aligned&&momentum.momentumR>=-.02&&(!context.available||context.aligned||!context.structureBroken);let phase="INITIAL",nextSl=currentSl,trailingStop=0;
  if(r>=beAt&&protectionConfirmed){phase="BREAKEVEN";nextSl=side==="Buy"?entry+initialRisk*beOffsetR:entry-initialRisk*beOffsetR;}if(r>=lockAt&&protectionConfirmed){phase="PROFIT_LOCK";let dynamicLock=lockR;if(r>=2)dynamicLock=Math.max(dynamicLock,.50);if(r>=2.8)dynamicLock=Math.max(dynamicLock,.75);const lock=side==="Buy"?entry+initialRisk*dynamicLock:entry-initialRisk*dynamicLock;if(betterStop(side,lock,nextSl))nextSl=lock;}if(r>=trailAt&&protectionConfirmed){phase="TRAIL";trailingStop=initialRisk*trailDistanceR;}
  nextSl=roundTick(nextSl,tick);trailingStop=roundTick(trailingStop,tick);const stopTighter=betterStop(side,nextSl,currentSl),trailTighter=phase==="TRAIL"&&trailingStop>0&&(!(currentTrailing>0)||trailingStop<currentTrailing-Math.max(tick/2,1e-12)),shouldTighten=stopTighter||trailTighter,verdict=shouldTighten?"TIGHTEN":"HOLD",reason=shouldTighten?(trailTighter?"ADAPTIVE_TRAILING":"PROTECTIVE_STOP_ADVANCE"):(!protectionConfirmed&&r>=beAt?"WAIT_PROTECTION_CONFIRMATION":phase==="TRAIL"&&currentTrailing>0?"TRAIL_ALREADY_TIGHT":cut.candidate?"SMART_CUT_CONFIRMING":momentum.adverseTrend?"HOLD_NO_CUT_CONFIRMATION":"HOLD_THESIS_INTACT");
  plan.lastReview={at:new Date().toISOString(),verdict,reason,r,peakR,worstR,ageSec,phase,currentSl,nextSl:stopTighter?nextSl:currentSl,currentTrailing,trailingStop:trailTighter?trailingStop:currentTrailing||null,momentum,context,smartCut:cut,discretionaryCutEnabled:cut.enabled,protectionConfirmed,signalAuthority:"5m",contextAuthority:"15m",m1Authority:false,thresholds:{warmupSec,beAt,lockAt,trailAt,lockR,trailDistanceR}};
  if(!shouldTighten)return {managed:false,verdict,reason,phase,r,peakR,worstR,mfeR:plan.mfeR,maeR:plan.maeR,ageSec,currentSl,currentTrailing,markPrice:mark,momentum,context,smartCut:cut,protectionConfirmed,thresholds:{warmupSec,beAt,lockAt,trailAt,lockR,trailDistanceR}};
  const body={symbol:plan.symbol,tpslMode:"Full",positionIdx:Number(position?.positionIdx??cfg.execution.positionIdx??0),stopLoss:String(stopTighter?nextSl:currentSl),slTriggerBy:"MarkPrice"};if(tp>0){body.takeProfit=String(tp);body.tpTriggerBy="MarkPrice";}if(trailTighter)body.trailingStop=String(trailingStop);await api.tradingStop(body);
  return {managed:true,verdict,reason,phase,r,peakR,worstR,mfeR:plan.mfeR,maeR:plan.maeR,ageSec,previousSl:currentSl,nextSl:Number(body.stopLoss),previousTrailing:currentTrailing||null,trailingStop:trailTighter?trailingStop:currentTrailing||null,trailDistanceR:phase==="TRAIL"?trailDistanceR:null,markPrice:mark,momentum,context,smartCut:cut,protectionConfirmed,thresholds:{warmupSec,beAt,lockAt,trailAt,lockR,trailDistanceR}};
}
