import {roundTick} from "./bybit-v5-client.js";

const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

function favorableR(side,entry,mark,initialRisk){
  if(!(initialRisk>0))return 0;
  return side==="Buy"?(mark-entry)/initialRisk:(entry-mark)/initialRisk;
}
function betterStop(side,next,current){
  if(!(next>0))return false;
  if(!(current>0))return true;
  return side==="Buy"?next>current:next<current;
}

export async function manageBybitScalpPosition(env,api,plan,position,cfg){
  const side=String(position?.side||plan?.side||""),entry=num(position?.avgPrice||position?.entryPrice||plan?.entry),mark=num(position?.markPrice),tick=num(plan?.filters?.tickSize||plan?.tickSize),initialSl=num(plan?.initialSl||plan?.sl),currentSl=num(position?.stopLoss||plan?.managedSl||plan?.sl),tp=num(position?.takeProfit||plan?.tp);
  const initialRisk=Math.abs(entry-initialSl);
  if(!(entry>0&&mark>0&&initialRisk>0))return {managed:false,reason:"POSITION_DATA_INVALID"};
  const r=favorableR(side,entry,mark,initialRisk);
  const beAt=Math.max(.45,Number(env.BYBIT_BE_TRIGGER_R||0.65));
  const lockAt=Math.max(beAt+.15,Number(env.BYBIT_PROFIT_LOCK_TRIGGER_R||1.0));
  const trailAt=Math.max(lockAt+.15,Number(env.BYBIT_TRAIL_TRIGGER_R||1.25));
  const beOffsetR=clamp(Number(env.BYBIT_BE_OFFSET_R||0.05),0,.20);
  const lockR=clamp(Number(env.BYBIT_PROFIT_LOCK_R||0.35),.10,.80);
  const trailDistanceR=clamp(Number(env.BYBIT_TRAIL_DISTANCE_R||0.55),.25,1.20);
  let phase="INITIAL",nextSl=currentSl,trailingStop=0,activePrice=0;

  if(r>=beAt){phase="BREAKEVEN";nextSl=side==="Buy"?entry+initialRisk*beOffsetR:entry-initialRisk*beOffsetR;}
  if(r>=lockAt){phase="PROFIT_LOCK";const lock=side==="Buy"?entry+initialRisk*lockR:entry-initialRisk*lockR;if(betterStop(side,lock,nextSl))nextSl=lock;}
  if(r>=trailAt){phase="TRAIL";trailingStop=initialRisk*trailDistanceR;activePrice=side==="Buy"?entry+initialRisk*trailAt:entry-initialRisk*trailAt;}

  nextSl=roundTick(nextSl,tick);
  trailingStop=roundTick(trailingStop,tick);
  activePrice=roundTick(activePrice,tick);
  if(!betterStop(side,nextSl,currentSl)&&phase!=="TRAIL")return {managed:false,reason:"NO_TIGHTENING_NEEDED",phase,r,currentSl};

  const body={symbol:plan.symbol,tpslMode:"Full",positionIdx:Number(position?.positionIdx??cfg.execution.positionIdx??0),stopLoss:String(betterStop(side,nextSl,currentSl)?nextSl:currentSl),slTriggerBy:"MarkPrice"};
  if(tp>0){body.takeProfit=String(tp);body.tpTriggerBy="MarkPrice";}
  if(phase==="TRAIL"&&trailingStop>0){body.trailingStop=String(trailingStop);body.activePrice=String(activePrice);}
  await api.tradingStop(body);
  return {managed:true,phase,r,previousSl:currentSl,nextSl:Number(body.stopLoss),trailingStop:trailingStop||null,activePrice:activePrice||null,markPrice:mark};
}
