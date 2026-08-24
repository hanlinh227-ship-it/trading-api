import {binance20Config} from "./binance-futures20-config.js";
import {scanBinance20,sizeBinance20} from "./binance-futures20-engine.js";
import {binanceUsdm,symbolFilters,roundTick} from "./binance-usdm-client.js";
import {getDailySession,dailySessionPolicy} from "./binance-daily-session.js";
import {reconcileDailyPnl} from "./binance-pnl-reconciliation.js";
import {manageScalpPosition} from "./binance-dynamic-stop-manager.js";
import {preflightExecution,resolveMarketFill,validateFillAgainstPlan} from "./binance-execution-guard.js";
import {chooseCandidateForSlots} from "./binance-position-cap.js";

const KEY="binance:auto:v1:state";
const now=()=>Date.now();
const iso=()=>new Date().toISOString();
async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:"json"})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
function day(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function envBool(v){return String(v||"").toLowerCase()==="true";}
function resetDaily(s){if(s.day===day())return s;return {...s,day:day(),trades:0,realizedUsd:0,lossStreak:0,pauseUntil:0,lastTradeAt:0,openPlans:{}};}
function hardStop(state,cfg){if(Number(state.realizedUsd||0)<=-Math.abs(cfg.risk.dailyStopUsd))return "DAILY_STOP";if(Number(state.trades||0)>=cfg.maxTradesPerDay)return "MAX_TRADES_PER_DAY";if(Number(state.pauseUntil||0)>now())return "LOSS_STREAK_PAUSE";return null;}
function executionMode(env){if(envBool(env.BINANCE_AUTO_LIVE))return "LIVE";if(envBool(env.BINANCE_AUTO_TESTNET))return "TESTNET";return "PAPER";}
function validateExecutionTarget(env,mode){const base=String(env.BINANCE_FUTURES_BASE_URL||"https://fapi.binance.com").toLowerCase(),looksTestnet=base.includes("testnet")||base.includes("demo");if(mode==="TESTNET"&&!looksTestnet)return "TESTNET_BASE_URL_REQUIRED";if(mode==="LIVE"&&looksTestnet)return "LIVE_BASE_URL_MISMATCH";if(mode==="LIVE"&&!envBool(env.BINANCE_AUTO_LIVE_ACK))return "LIVE_ACK_REQUIRED";return null;}
async function emergencyFlat(api,setup,qty){const closeSide=setup.side==="BUY"?"SELL":"BUY";try{return await api.order({symbol:setup.symbol,side:closeSide,type:"MARKET",quantity:qty,reduceOnly:true,newOrderRespType:"RESULT"});}catch{return null;}}

async function manageOpenPlans(env,state,positions){
  const plans={...(state.openPlans||{})},liveSymbols=new Set((positions||[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0).map(x=>String(x.symbol||"").toUpperCase())),results=[];
  for(const symbol of Object.keys(plans)){
    if(!liveSymbols.has(symbol)){delete plans[symbol];results.push({symbol,managed:false,reason:"POSITION_CLOSED"});continue;}
    try{const r=await manageScalpPosition(env,plans[symbol]);results.push({symbol,...r});}
    catch(e){results.push({symbol,managed:false,reason:"POSITION_MANAGEMENT_FAILED",error:String(e?.message||e)});}
  }
  state.openPlans=plans;state.lastLifecycles=results;return results;
}

export async function runBinanceAutoV1(env){
  const cfg=binance20Config(env),mode=executionMode(env),targetErr=validateExecutionTarget(env,mode);
  let state=resetDaily(await get(env)),pnl=null;
  if(mode!=="PAPER"){
    try{pnl=await reconcileDailyPnl(env,state);state=pnl.state;await put(env,state);}catch(e){return {ok:true,executed:false,mode,reason:"PNL_RECONCILIATION_FAILED",error:String(e?.message||e),state};}
  }
  const session=await getDailySession(env),target=dailySessionPolicy(session,state),stop=hardStop(state,cfg);
  if(targetErr)return {ok:true,executed:false,mode,reason:targetErr,session,target,pnl,state};
  if(!target.active){await put(env,state);return {ok:true,executed:false,mode,reason:"WAITING_FOR_DAILY_TARGET",session,target,pnl,state};}
  if(target.reached){await put(env,state);return {ok:true,executed:false,mode,reason:"DAILY_TARGET_REACHED",session,target,pnl,state};}
  if(stop){await put(env,state);return {ok:true,executed:false,mode,reason:stop,session,target,pnl,state};}

  const api=binanceUsdm(env);let equity=cfg.startingCapitalUsd,positions=[],lifecycles=[];
  if(mode!=="PAPER"){
    const [acct,pos]=await Promise.all([api.account(),api.positions()]);
    equity=Number(acct.totalWalletBalance||acct.totalMarginBalance||cfg.startingCapitalUsd);
    positions=(pos||[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0);
    lifecycles=await manageOpenPlans(env,state,positions);await put(env,state);
    if(positions.length>=cfg.maxOpenPositions)return {ok:true,executed:false,mode,reason:"MAX_OPEN_POSITIONS",positions:positions.length,lifecycles,session,target,pnl,state};
  }

  const scan=await scanBinance20(env),slot=chooseCandidateForSlots(scan.candidates||[],positions,cfg),setup=slot.candidate;
  if(!setup)return {ok:true,executed:false,mode,reason:slot.reason||scan.reason||"NO_SETUP",slot,scan,lifecycles,session,target,pnl,state};
  if(Number(setup.rr||0)<cfg.risk.minRR)return {ok:true,executed:false,mode,reason:"RR_TOO_LOW",setup,slot,scan,lifecycles,session,target,pnl,state};
  const sizing=sizeBinance20(setup,setup.filters,cfg,equity);
  if(!sizing.ok)return {ok:true,executed:false,mode,reason:sizing.reason,setup,sizing,slot,scan,lifecycles,session,target,pnl,state};
  const fingerprint=`${setup.symbol}:${setup.side}:${setup.strategy}:${Math.round(Number(setup.entry||0)*1e6)}`;
  if(state.lastFingerprint===fingerprint&&now()-Number(state.lastTradeAt||0)<cfg.execution.cooldownSec*1000)return {ok:true,executed:false,mode,reason:"DUPLICATE_COOLDOWN",setup,slot,scan,lifecycles,session,target,pnl,state};

  const plan={symbol:setup.symbol,side:setup.side,qty:sizing.qty,entry:setup.entry,sl:setup.sl,tp:setup.tp,rr:setup.rr,strategy:setup.strategy,score:setup.score,riskUsd:sizing.riskUsd,exitPlan:setup.exitPlan,context:setup.context,targetMode:target.mode,targetRemainingUsd:target.remainingUsd,universeCount:Number(scan?.universe?.count||0),createdAt:iso()};
  if(mode==="PAPER"){
    state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fingerprint;state.openPlans={...(state.openPlans||{}),[setup.symbol]:plan};await put(env,state);
    return {ok:true,executed:true,paper:true,mode,reason:"PAPER_ORDER_ACCEPTED",plan,slot,scan,session,target,pnl,state};
  }

  const preflight=await preflightExecution(api,setup,env);
  if(!preflight.ok)return {ok:true,executed:false,mode,reason:preflight.reason,preflight,setup,slot,scan,lifecycles,session,target,pnl,state};
  const info=await api.exchangeInfo(),filters=symbolFilters(info,setup.symbol),sl=roundTick(setup.sl,filters?.tickSize||0),tp=roundTick(setup.tp,filters?.tickSize||0);
  setup.sl=sl;setup.tp=tp;
  await api.setLeverage(setup.symbol,cfg.leverage).catch(()=>{});await api.setMarginType(setup.symbol,cfg.execution.marginType).catch(()=>{});
  const closeSide=setup.side==="BUY"?"SELL":"BUY",orderResult=await api.order({symbol:setup.symbol,side:setup.side,type:"MARKET",quantity:sizing.qty,newOrderRespType:"RESULT"}),fill=await resolveMarketFill(api,setup.symbol,orderResult);
  if(!fill.ok){await emergencyFlat(api,setup,sizing.qty);return {ok:false,executed:false,mode,reason:fill.reason,preflight,fill,setup,slot,scan,session,target,pnl,state};}
  const fillCheck=validateFillAgainstPlan({setup,preflight,fill,env});
  if(!fillCheck.ok){const emergency=await emergencyFlat(api,setup,fill.executedQty||sizing.qty);state.lastExecutionGuard={preflight,fill,fillCheck,emergencyFlat:!!emergency,at:iso()};await put(env,state);return {ok:true,executed:false,mode,reason:fillCheck.reason,emergencyFlat:!!emergency,preflight,fill,fillCheck,setup,slot,scan,session,target,pnl,state};}
  try{await api.order({symbol:setup.symbol,side:closeSide,type:"STOP_MARKET",stopPrice:sl,closePosition:true,workingType:"MARK_PRICE"});await api.order({symbol:setup.symbol,side:closeSide,type:"TAKE_PROFIT_MARKET",stopPrice:tp,closePosition:true,workingType:"MARK_PRICE"});}
  catch(e){await emergencyFlat(api,setup,fill.executedQty||sizing.qty);throw new Error("PROTECTION_ORDER_FAILED:"+String(e?.message||e));}

  const actualPlan={...plan,entry:fill.avgPrice,sl,tp,rr:fillCheck.actualRR,qty:fill.executedQty,orderId:fill.orderId,execution:{preflight,fill:{avgPrice:fill.avgPrice,executedQty:fill.executedQty,orderId:fill.orderId},slippageBps:fillCheck.slippageBps,actualRR:fillCheck.actualRR}};
  state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fingerprint;state.openPlans={...(state.openPlans||{}),[setup.symbol]:actualPlan};state.lastExecutionGuard=actualPlan.execution;await put(env,state);
  return {ok:true,executed:true,mode,reason:"ORDER_SUBMITTED_AND_PROTECTED",plan:actualPlan,slot,scan,lifecycles,session,target,pnl,state};
}

export async function getBinanceAutoV1State(env){return get(env);}
