import {bybitV5} from "./bybit-v5-client.js";
import {recordBybitLearningEvent} from "./bybit-learning-engine.js";

const KEY="bybit:learning:v2:recovery";
const DAY=86400000;
const now=()=>Date.now(),iso=()=>new Date().toISOString();
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
const closedAt=x=>Number(x?.updatedTime||x?.createdTime||0);
const closedKey=x=>String(x?.orderId||x?.execId||`${x?.symbol||""}:${closedAt(x)}:${x?.closedPnl||""}:${x?.closedSize||x?.qty||""}`);
const planCreated=p=>Number(p?.createdAtMs||Date.parse(p?.createdAt||"")||0);
function matchRow(x,symbol,plan){
  if(String(x?.symbol||"")!==String(symbol||""))return false;
  const t=closedAt(x),created=planCreated(plan);if(created>0&&t<created-5000)return false;
  const side=String(x?.side||"");if(side&&plan?.side&&side!==String(plan.side))return false;
  const pe=Number(plan?.entry||0),re=Number(x?.avgEntryPrice||0),tick=Math.abs(Number(plan?.tickSize||plan?.filters?.tickSize||0));
  if(pe>0&&re>0&&Math.abs(re-pe)>Math.max(tick*3,pe*.0015))return false;
  return true;
}
async function history(api,days){
  const rows=[],seen=new Set();const end=now();
  for(let offset=0;offset<days;offset+=7){
    const a=Math.max(end-days*DAY,end-(offset+7)*DAY),b=end-offset*DAY;let cursor="";
    for(let p=0;p<20;p++){
      const r=await api.closedPnl(a,b,cursor),list=r?.result?.list||[];
      for(const x of list){const k=closedKey(x);if(!seen.has(k)){seen.add(k);rows.push(x);}}
      const next=String(r?.result?.nextPageCursor||"");if(!next||next===cursor)break;cursor=next;
    }
  }
  return rows.sort((a,b)=>closedAt(b)-closedAt(a));
}
function outcome(plan,rows){
  if(!rows.length)return null;
  const risk=Math.abs(Number(plan?.riskUsd||0));if(!(risk>0))return null;
  const net=rows.reduce((s,x)=>s+Number(x?.closedPnl||0),0),fees=rows.reduce((s,x)=>s+Math.abs(Number(x?.openFee||0))+Math.abs(Number(x?.closeFee||0)),0);
  const qty=rows.reduce((s,x)=>s+Math.abs(Number(x?.closedSize||x?.qty||0)),0),planned=Math.abs(Number(plan?.qty||0));if(planned>0&&qty>0&&qty<planned*.90)return null;
  let gross=0,known=false;for(const x of rows){const q=Math.abs(Number(x?.closedSize||x?.qty||0)),en=Number(x?.avgEntryPrice||plan?.entry||0),ex=Number(x?.avgExitPrice||0);if(q>0&&en>0&&ex>0){known=true;gross+=(plan?.side==="Buy"?ex-en:en-ex)*q;}}
  const latest=Math.max(...rows.map(closedAt)),created=planCreated(plan)||latest;
  return {status:net>1e-9?"WIN":net<-1e-9?"LOSS":"BREAKEVEN",authority:"BYBIT_CLOSED_PNL_RECOVERED",sourceId:rows.map(closedKey).sort().join("|").slice(0,160),pnlUsd:known?gross:net,netPnlUsd:net,rMultiple:known?gross/risk:net/risk,netR:net/risk,feesUsd:fees,holdSec:Math.max(0,Math.round((latest-created)/1000)),exitReason:"RECOVERED_CLOSED_PNL"};
}
export async function recoverBybitCanonicalLearning(env,state,{days=30}={}){
  const api=bybitV5(env),windowDays=Math.max(1,Math.min(90,Number(days)||30)),rows=await history(api,windowDays),q=Array.isArray(state?.reconcileQuarantine)?state.reconcileQuarantine:[],recovered=[],used=new Set();
  for(const item of q){
    const plan=item?.plan||item||{},symbol=String(item?.symbol||plan?.symbol||"");if(!symbol||!(Number(plan?.riskUsd)>0)||!plan?.strategy)continue;
    const matches=rows.filter(x=>!used.has(closedKey(x))&&matchRow(x,symbol,plan)),out=outcome(plan,matches);if(!out)continue;
    for(const x of matches)used.add(closedKey(x));
    const lifecycle=String(plan?.orderId||item?.orderId||`${symbol}:${planCreated(plan)||0}`),id=`BYBIT_OUTCOME:RECOVERED:${lifecycle}`;
    await recordBybitLearningEvent(env,{id,stage:"OUTCOME",mode:"LIVE",symbol,side:plan.side,strategy:plan.strategy,regime:plan.regime,betaCluster:plan.betaCluster,exitProfile:plan.exitProfile,score:plan.score,rr:plan.rr,riskUsd:plan.riskUsd,rewardUsd:plan.rewardUsd,entry:plan.entry,sl:plan.initialSl||plan.sl,tp:plan.tp,leverage:plan.leverage,ai:plan.ai,postAi:plan.postAiQuote,execution:plan.execution,outcome:out,reason:"RECOVERED_FROM_QUARANTINED_LIFECYCLE"});
    recovered.push({symbol,id,netPnlUsd:out.netPnlUsd,netR:out.netR,rows:matches.length});
  }
  const report={version:"BYBIT_LEARNING_RECOVERY_V1",at:iso(),windowDays,exchangeRows:rows.length,quarantinedLifecycles:q.length,recoveredLifecycles:recovered.length,recoveredRows:used.size,unattributedRows:Math.max(0,rows.length-used.size),recovered:recovered.slice(0,30),policy:"RECOVER_ONLY_WITH_LIFECYCLE_RISK_STRATEGY_METADATA_NO_FABRICATION"};
  await put(env,report);return report;
}
export async function getBybitLearningRecoveryState(env){try{return await env.TRADING_STATE?.get(KEY,{type:"json"})||null}catch{return null}}
