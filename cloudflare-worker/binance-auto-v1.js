import {binance20Config} from "./binance-futures20-config.js";
import {scanBinance20,sizeBinance20} from "./binance-futures20-engine.js";
import {binanceUsdm} from "./binance-usdm-client.js";

const KEY="binance:auto:v1:state";
const now=()=>Date.now();
const iso=()=>new Date().toISOString();
async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:"json"})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
function day(){return new Date().toISOString().slice(0,10);}
function envBool(v){return String(v||"").toLowerCase()==="true";}
function resetDaily(s){if(s.day===day())return s;return {...s,day:day(),trades:0,realizedUsd:0,lossStreak:0,pauseUntil:0,lastTradeAt:0};}
function hardStop(state,cfg){if(Number(state.realizedUsd||0)<=-Math.abs(cfg.risk.dailyStopUsd))return "DAILY_STOP";if(Number(state.trades||0)>=cfg.maxTradesPerDay)return "MAX_TRADES_PER_DAY";if(Number(state.pauseUntil||0)>now())return "LOSS_STREAK_PAUSE";return null;}
function executionMode(env){if(envBool(env.BINANCE_AUTO_LIVE))return "LIVE";if(envBool(env.BINANCE_AUTO_TESTNET))return "TESTNET";return "PAPER";}
function validateExecutionTarget(env,mode){const base=String(env.BINANCE_FUTURES_BASE_URL||"https://fapi.binance.com").toLowerCase(),looksTestnet=base.includes("testnet")||base.includes("demo");if(mode==="TESTNET"&&!looksTestnet)return "TESTNET_BASE_URL_REQUIRED";if(mode==="LIVE"&&looksTestnet)return "LIVE_BASE_URL_MISMATCH";if(mode==="LIVE"&&!envBool(env.BINANCE_AUTO_LIVE_ACK))return "LIVE_ACK_REQUIRED";return null;}

export async function runBinanceAutoV1(env){
  const cfg=binance20Config(env),mode=executionMode(env),targetErr=validateExecutionTarget(env,mode),state=resetDaily(await get(env)),stop=hardStop(state,cfg);
  if(targetErr)return {ok:true,executed:false,mode,reason:targetErr,state};
  if(stop){await put(env,state);return {ok:true,executed:false,mode,reason:stop,state};}

  const scan=await scanBinance20(env),setup=scan.best;
  if(!setup)return {ok:true,executed:false,mode,reason:"NO_SETUP",scan,state};
  if(Number(setup.rr||0)<cfg.risk.minRR)return {ok:true,executed:false,mode,reason:"RR_TOO_LOW",setup,state};

  const api=binanceUsdm(env);
  let equity=cfg.startingCapitalUsd,positions=[];
  if(mode!=="PAPER"){
    const [acct,pos]=await Promise.all([api.account(),api.positions()]);
    equity=Number(acct.totalWalletBalance||acct.totalMarginBalance||cfg.startingCapitalUsd);
    positions=(pos||[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0);
    if(positions.length>=cfg.maxOpenPositions)return {ok:true,executed:false,mode,reason:"MAX_OPEN_POSITIONS",positions:positions.length,state};
  }

  const sizing=sizeBinance20(setup,setup.filters,cfg,equity);
  if(!sizing.ok)return {ok:true,executed:false,mode,reason:sizing.reason,setup,sizing,state};

  const fingerprint=`${setup.symbol}:${setup.side}:${setup.strategy}:${Math.round(Number(setup.entry||0)*1e6)}`;
  if(state.lastFingerprint===fingerprint&&now()-Number(state.lastTradeAt||0)<cfg.execution.cooldownSec*1000)return {ok:true,executed:false,mode,reason:"DUPLICATE_COOLDOWN",setup,state};

  const plan={symbol:setup.symbol,side:setup.side,qty:sizing.qty,entry:setup.entry,sl:setup.sl,tp:setup.tp,rr:setup.rr,strategy:setup.strategy,score:setup.score,riskUsd:sizing.riskUsd,createdAt:iso()};
  if(mode==="PAPER"){
    state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fingerprint;state.lastPlan=plan;await put(env,state);
    return {ok:true,executed:true,paper:true,mode,reason:"PAPER_ORDER_ACCEPTED",plan,state};
  }

  await api.setLeverage(setup.symbol,cfg.leverage).catch(()=>{});
  await api.setMarginType(setup.symbol,cfg.execution.marginType).catch(()=>{});
  const closeSide=setup.side==="BUY"?"SELL":"BUY";
  const entry=await api.order({symbol:setup.symbol,side:setup.side,type:"MARKET",quantity:sizing.qty,newOrderRespType:"RESULT"});
  let protectedOk=false;
  try{
    await api.order({symbol:setup.symbol,side:closeSide,type:"STOP_MARKET",stopPrice:setup.sl,closePosition:true,workingType:"MARK_PRICE"});
    await api.order({symbol:setup.symbol,side:closeSide,type:"TAKE_PROFIT_MARKET",stopPrice:setup.tp,closePosition:true,workingType:"MARK_PRICE"});
    protectedOk=true;
  }catch(e){
    try{await api.order({symbol:setup.symbol,side:closeSide,type:"MARKET",quantity:sizing.qty,reduceOnly:true});}catch{}
    throw new Error("PROTECTION_ORDER_FAILED:"+String(e?.message||e));
  }
  if(!protectedOk)throw new Error("PROTECTION_NOT_CONFIRMED");

  state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fingerprint;state.lastPlan={...plan,orderId:entry.orderId};await put(env,state);
  return {ok:true,executed:true,mode,reason:"ORDER_SUBMITTED_AND_PROTECTED",plan:{...plan,orderId:entry.orderId},state};
}

export async function getBinanceAutoV1State(env){return get(env);}
