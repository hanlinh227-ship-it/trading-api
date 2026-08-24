import {bybitAutoConfig,bybitExecutionMode} from "./bybit-auto-config.js";
import {bybitV5,roundTick} from "./bybit-v5-client.js";
import {scanBybitAuto,sizeBybitAuto} from "./bybit-scalp-engine.js";
import {reviewBybitScalp,revalidateBybitScalpAfterAi} from "./bybit-ai-scalp-gate.js";
import {recordBybitLearningEvent} from "./bybit-learning-engine.js";
import {reconcileBybitPaperPlans} from "./bybit-shadow-lifecycle.js";

const KEY="bybit:auto:v1:state";
const now=()=>Date.now(),iso=()=>new Date().toISOString(),envBool=v=>String(v||"").toLowerCase()==="true";
async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:"json"})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
function day(){return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Bangkok",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());}
function reset(s){return s.day===day()?s:{...s,day:day(),trades:0,realizedUsd:0,lossStreak:0,pauseUntil:0,lastTradeAt:0,lastFingerprint:null,openPlans:{}};}
function liveGuard(env,mode){if(mode!=="LIVE")return null;if(!envBool(env.BYBIT_AUTO_LIVE_ACK))return "LIVE_ACK_REQUIRED";return null;}
function tpForReward(side,entry,qty,rewardUsd){const q=Math.abs(Number(qty||0));if(!(q>0))return null;const d=Number(rewardUsd||0)/q;return side==="Buy"?entry+d:entry-d;}
async function fill(api,symbol,orderId){for(let i=0;i<8;i++){const p=await api.orderStatus(symbol,orderId),x=p?.result?.list?.[0],qty=Number(x?.cumExecQty||0),avg=Number(x?.avgPrice||0);if(qty>0&&avg>0)return {ok:true,orderId,executedQty:qty,avgPrice:avg,status:x.orderStatus};await new Promise(r=>setTimeout(r,250));}return {ok:false,reason:"MARKET_FILL_TIMEOUT",orderId};}
async function emergencyFlat(api,setup,qty){try{return await api.order({symbol:setup.symbol,side:setup.side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(qty),reduceOnly:true,positionIdx:0});}catch{return null;}}
async function learn(env,event){try{await recordBybitLearningEvent(env,event);}catch{}}

export async function runBybitAutoV1(env,{forceScan=false}={}){
  const cfg=bybitAutoConfig(env),mode=bybitExecutionMode(env),guard=liveGuard(env,mode),api=bybitV5(env);let state=reset(await get(env));
  if(mode==="PAPER"){
    try{const rec=await reconcileBybitPaperPlans(env,state);state.openPlans=rec.plans;state.lastShadowReconcile={at:iso(),closed:rec.closed};if(rec.closed.length)await put(env,state);}catch(e){state.lastShadowReconcile={at:iso(),error:String(e?.message||e)};}
  }
  if(guard)return {ok:true,executed:false,mode,reason:guard,state};
  if(Number(state.trades||0)>=cfg.maxTradesPerDay)return {ok:true,executed:false,mode,reason:"MAX_TRADES_PER_DAY",state};
  if(Number(state.pauseUntil||0)>now())return {ok:true,executed:false,mode,reason:"LOSS_STREAK_PAUSE",state};
  let equity=cfg.startingCapitalUsd,positions=[];
  if(mode==="LIVE"){
    const [wallet,pos]=await Promise.all([api.wallet(),api.positions()]),acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};
    equity=Number(acct.totalEquity||coin.equity||coin.walletBalance||cfg.startingCapitalUsd);
    positions=(pos?.result?.list||[]).filter(x=>Number(x.size||0)>0);
    if(positions.length>=cfg.maxOpenPositions)return {ok:true,executed:false,mode,reason:"MAX_OPEN_POSITIONS",positions:positions.length,equity,state};
  }

  const scan=await scanBybitAuto(env),setup=scan.best;
  if(!setup)return {ok:true,executed:false,mode,reason:scan.reason||"NO_SETUP",scan,state};
  const sameDir=positions.filter(p=>String(p.side)===setup.side).length;
  if(sameDir>=cfg.risk.maxSameDirectionPositions)return {ok:true,executed:false,mode,reason:"SAME_DIRECTION_CAP",setup,scan,state};
  const sizing=sizeBybitAuto(setup,cfg,equity);
  if(!sizing.ok)return {ok:true,executed:false,mode,reason:sizing.reason,setup,sizing,scan,state};
  const fp=`${setup.symbol}:${setup.side}:${setup.strategy}:${Math.round(setup.entry*1e6)}`;
  if(!forceScan&&state.lastFingerprint===fp&&now()-Number(state.lastTradeAt||0)<cfg.execution.cooldownSec*1000)return {ok:true,executed:false,mode,reason:"DUPLICATE_COOLDOWN",setup,scan,state};

  const ai=await reviewBybitScalp(env,setup);
  state.lastAiReview={symbol:setup.symbol,side:setup.side,at:iso(),...ai};
  if(!ai.allow){await learn(env,{stage:"AI_REJECT",mode,symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:setup.score,rr:setup.rr,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,entry:setup.entry,sl:setup.sl,tp:setup.tp,ai,reason:ai.reason});await put(env,state);return {ok:true,executed:false,mode,reason:ai.reason||"AI_SCALP_GATE",ai,setup,sizing,scan,state};}

  const postAi=await revalidateBybitScalpAfterAi(env,api,setup);
  state.lastPostAiQuote={symbol:setup.symbol,side:setup.side,at:iso(),...postAi};
  if(!postAi.ok){await learn(env,{stage:"POST_AI_REJECT",mode,symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:setup.score,rr:setup.rr,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,entry:setup.entry,sl:setup.sl,tp:setup.tp,ai,postAi,reason:postAi.reason});await put(env,state);return {ok:true,executed:false,mode,reason:postAi.reason||"POST_AI_REVALIDATION_FAILED",ai,postAi,setup,sizing,scan,state};}

  const rewardTp=tpForReward(setup.side,setup.entry,sizing.qty,sizing.rewardUsd),plan={
    mode,symbol:setup.symbol,side:setup.side,qty:sizing.qty,entry:setup.entry,sl:setup.sl,tp:rewardTp||setup.tp,structureTp:setup.tp,
    rr:sizing.targetRR,strategy:setup.strategy,score:setup.score,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,
    ai:{mode:ai.mode,reason:ai.reason,pass:ai.pass,reject:ai.reject,blocked:ai.blocked,unavailable:ai.unavailable,verdicts:ai.verdicts},
    postAiQuote:{px:postAi.px,spreadBps:postAi.spreadBps,driftBps:postAi.driftBps,checkedAt:postAi.checkedAt},
    createdAt:iso(),createdAtMs:now()
  };

  if(mode==="PAPER"){
    state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fp;state.openPlans={...(state.openPlans||{}),[setup.symbol]:plan};
    await learn(env,{stage:"PAPER_ACCEPT",mode,symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:setup.score,rr:plan.rr,riskUsd:plan.riskUsd,rewardUsd:plan.rewardUsd,entry:plan.entry,sl:plan.sl,tp:plan.tp,ai,postAi,reason:"PAPER_ORDER_ACCEPTED_AFTER_AI"});
    await put(env,state);
    return {ok:true,executed:true,paper:true,mode,reason:"PAPER_ORDER_ACCEPTED_AFTER_AI",plan,ai,postAi,scan,state};
  }

  try{await api.setLeverage(setup.symbol,cfg.leverage);}catch{}
  const order=await api.order({symbol:setup.symbol,side:setup.side,orderType:"Market",qty:String(sizing.qty),positionIdx:cfg.execution.positionIdx,timeInForce:"IOC"}),orderId=order?.result?.orderId;
  if(!orderId)return {ok:false,executed:false,mode,reason:"BYBIT_ORDER_ID_MISSING",order,ai,postAi,setup,scan,state};
  const f=await fill(api,setup.symbol,orderId);
  if(!f.ok){await emergencyFlat(api,setup,sizing.qty);return {ok:false,executed:false,mode,reason:f.reason,fill:f,ai,postAi,setup,scan,state};}
  const tick=Number(setup.filters?.tickSize||0),sl=roundTick(setup.sl,tick),tp=roundTick(tpForReward(setup.side,f.avgPrice,f.executedQty,sizing.rewardUsd),tick),actualRisk=Math.abs(f.avgPrice-sl)*f.executedQty,actualReward=Math.abs(tp-f.avgPrice)*f.executedQty,actualRR=actualRisk>0?actualReward/actualRisk:null;
  if(!(tp>0&&sl>0&&actualRR>=cfg.risk.minRR)){await emergencyFlat(api,setup,f.executedQty);return {ok:true,executed:false,mode,reason:"ACTUAL_RR_INVALID",actualRR,fill:f,ai,postAi,setup,scan,state};}
  try{await api.tradingStop({symbol:setup.symbol,tpslMode:"Full",positionIdx:cfg.execution.positionIdx,takeProfit:String(tp),stopLoss:String(sl),tpTriggerBy:"MarkPrice",slTriggerBy:"MarkPrice"});}
  catch(e){await emergencyFlat(api,setup,f.executedQty);return {ok:false,executed:false,mode,reason:"PROTECTION_SET_FAILED",error:String(e?.message||e),fill:f,ai,postAi,setup,scan,state};}

  const actual={...plan,entry:f.avgPrice,qty:f.executedQty,sl,tp,rr:actualRR,orderId:f.orderId,riskUsd:actualRisk,rewardUsd:actualReward,execution:{status:f.status}};
  state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fp;state.openPlans={...(state.openPlans||{}),[setup.symbol]:actual};
  await learn(env,{stage:"LIVE_ACCEPT",mode,symbol:actual.symbol,side:actual.side,strategy:actual.strategy,score:actual.score,rr:actual.rr,riskUsd:actual.riskUsd,rewardUsd:actual.rewardUsd,entry:actual.entry,sl:actual.sl,tp:actual.tp,ai,postAi,reason:"ORDER_SUBMITTED_AND_PROTECTED_AFTER_AI"});
  await put(env,state);
  return {ok:true,executed:true,mode,reason:"ORDER_SUBMITTED_AND_PROTECTED_AFTER_AI",plan:actual,ai,postAi,scan,state};
}

export async function getBybitAutoV1State(env){return get(env);}
