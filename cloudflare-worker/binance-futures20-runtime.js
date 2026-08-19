// ============================================================================
// NON_PRODUCTION / QUARANTINED — see docs/ai-coengineer/DECISIONS.md DECISION-005
//
// This module is NOT part of current production execution authority. It is
// not imported by cloudflare-worker/index.js, hub-v77171.js, or
// engine-v77168.js and has no wired route, scheduled handler, or active
// credential binding in the production Worker entrypoint chain.
//
// Do NOT delete this file. Do NOT wire it into a production path without an
// explicit reviewed decision (V78-090) promoting it to a real
// AccountAdapter/ExecutionVenue pilot per
// docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md.
//
// Reference: docs/ai-coengineer/DECISIONS.md DECISION-005,
//            docs/ai-coengineer/V78_KV_KEY_REGISTRY.md Section 12,
//            docs/ai-coengineer/V78_EXECUTION_AUTHORITY_MAP.md Section 3.
// ============================================================================

import {binance20Config} from "./binance-futures20-config.js";
import {binanceUsdm} from "./binance-usdm-client.js";
import {scanBinance20,sizeBinance20} from "./binance-futures20-engine.js";
const KEY="v771840:binance20:state";
async function get(env){try{return await env.TRADING_STATE?.get(KEY,"json")||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
export async function runBinance20Cycle(env){const cfg=binance20Config(env),state=await get(env),now=Date.now(),day=new Date().toISOString().slice(0,10);if(state.day!==day)Object.assign(state,{day,trades:0,realizedUsd:0,lossStreak:0,pauseUntil:0});if(Number(state.realizedUsd||0)<=-cfg.risk.dailyStopUsd)return {executed:false,reason:"DAILY_STOP",state};if(Number(state.lossStreak||0)>=cfg.risk.maxLossStreak&&now<Number(state.pauseUntil||0))return {executed:false,reason:"LOSS_STREAK_PAUSE",state};if(Number(state.trades||0)>=cfg.maxTradesPerDay)return {executed:false,reason:"MAX_TRADES",state};const scan=await scanBinance20(env),s=scan.best;if(!s)return {executed:false,reason:"NO_SETUP",scan};const api=binanceUsdm(env);let equity=cfg.startingCapitalUsd,positions=[];if(cfg.execution.liveDefault){const [acct,pos]=await Promise.all([api.account(),api.positions()]);equity=Number(acct.totalWalletBalance||acct.totalMarginBalance||equity);positions=(pos||[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0);if(positions.length>=cfg.maxOpenPositions)return {executed:false,reason:"MAX_OPEN_POSITIONS",positions:positions.length,scan};}
const sizing=sizeBinance20(s,s.filters,cfg,equity);if(!sizing.ok)return {executed:false,reason:sizing.reason,sizing,scan};if(!cfg.execution.liveDefault)return {executed:false,reason:"LIVE_DISABLED",paper:true,setup:s,sizing,scan};await api.setLeverage(s.symbol,cfg.leverage).catch(()=>{});await api.setMarginType(s.symbol,cfg.execution.marginType).catch(()=>{});const side=s.side,closeSide=side==="BUY"?"SELL":"BUY",entry=await api.order({symbol:s.symbol,side,type:"MARKET",quantity:sizing.qty,newOrderRespType:"RESULT"});await api.order({symbol:s.symbol,side:closeSide,type:"STOP_MARKET",stopPrice:s.sl,closePosition:true,workingType:"MARK_PRICE"});await api.order({symbol:s.symbol,side:closeSide,type:"TAKE_PROFIT_MARKET",stopPrice:s.tp,closePosition:true,workingType:"MARK_PRICE"});state.trades=Number(state.trades||0)+1;state.lastEntryAt=now;state.lastOrder={symbol:s.symbol,side,qty:sizing.qty,entry:s.entry,sl:s.sl,tp:s.tp,orderId:entry.orderId};await put(env,state);return {executed:true,reason:"ORDER_SUBMITTED",setup:s,sizing,entry,state};}
export async function getBinance20State(env){return get(env);}
