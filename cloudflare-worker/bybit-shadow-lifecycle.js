import {bybitV5} from "./bybit-v5-client.js";
import {recordBybitLearningEvent} from "./bybit-learning-engine.js";

const num=v=>Number.isFinite(Number(v))?Number(v):null;
const now=()=>Date.now();
function parseRows(p){return (p?.result?.list||[]).map(r=>({ts:Number(r[0]),open:Number(r[1]),high:Number(r[2]),low:Number(r[3]),close:Number(r[4])})).filter(x=>[x.ts,x.open,x.high,x.low,x.close].every(Number.isFinite)).sort((a,b)=>a.ts-b.ts);}
function evaluate(plan,rows){
  const entry=num(plan.entry),sl=num(plan.sl),tp=num(plan.tp),risk=Math.abs(entry-sl);if(!(entry>0&&sl>0&&tp>0&&risk>0))return {status:"INVALID_PLAN"};
  let mfe=0,mae=0;
  for(const c of rows){
    const tpHit=plan.side==="Buy"?c.high>=tp:c.low<=tp,slHit=plan.side==="Buy"?c.low<=sl:c.high>=sl;
    const fav=plan.side==="Buy"?(c.high-entry):(entry-c.low),adv=plan.side==="Buy"?(entry-c.low):(c.high-entry);mfe=Math.max(mfe,fav/risk);mae=Math.max(mae,adv/risk);
    if(tpHit&&slHit)return {status:"AMBIGUOUS_SAME_CANDLE",closedAt:c.ts,mfeR:mfe,maeR:mae};
    if(tpHit)return {status:"TP",closedAt:c.ts,rMultiple:Math.abs(tp-entry)/risk,pnlUsd:num(plan.rewardUsd),mfeR:mfe,maeR:mae};
    if(slHit)return {status:"SL",closedAt:c.ts,rMultiple:-1,pnlUsd:-Math.abs(num(plan.riskUsd)||0),mfeR:mfe,maeR:mae};
  }
  return {status:"OPEN",mfeR:mfe,maeR:mae};
}
export async function reconcileBybitPaperPlans(env,state){
  const plans={...(state?.openPlans||{})},api=bybitV5(env),closed=[];for(const [symbol,plan] of Object.entries(plans)){
    if(plan?.mode&&plan.mode!=="PAPER")continue;const created=Date.parse(plan.createdAt||"")||Number(plan.createdAtMs||0);if(!(created>0))continue;
    const age=now()-created;if(age<60000)continue;const start=Math.max(created-60000,now()-12*60*60*1000);let rows=[];
    try{rows=parseRows(await api.klineRange(symbol,{interval:"1",start,end:now(),limit:720}));}catch{continue;}
    const out=evaluate(plan,rows);if(out.status==="OPEN"||out.status==="INVALID_PLAN")continue;
    const holdSec=Math.max(0,Math.round(((out.closedAt||now())-created)/1000));await recordBybitLearningEvent(env,{stage:"OUTCOME",mode:"PAPER",symbol,side:plan.side,strategy:plan.strategy,score:plan.score,rr:plan.rr,riskUsd:plan.riskUsd,rewardUsd:plan.rewardUsd,entry:plan.entry,sl:plan.sl,tp:plan.tp,ai:plan.ai,postAi:plan.postAiQuote,outcome:{...out,holdSec},reason:out.status});
    delete plans[symbol];closed.push({symbol,...out,holdSec});
  }
  return {plans,closed};
}
