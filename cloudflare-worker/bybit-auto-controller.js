import {runBtcHyperscale,getBtcHyperscaleState} from "./bybit-btc-engine.js";
import {reconcileBtcAccountBalance} from "./bybit-btc-balance-reconciler.js";
import {telegramApiRequest} from "./providers/telegram-client.js";
import {bybitV5} from "./bybit-v5-client.js";
import {BYBIT_AUTO_VERSION,bybitAutoConfig} from "./bybit-auto-config.js";

const AUTO_KEY="bybit:btc:hyperscale:v2:state";
const CONTROL_KEY="bybit:auto:v1:controller";
const iso=()=>new Date().toISOString();
const envBool=v=>String(v||"").toLowerCase()==="true";
async function kvGet(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function kvPut(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
function compactPrice(v,tick=0){const n=Number(v);if(!Number.isFinite(n))return "—";const t=Math.abs(Number(tick||0));let d=t>0?Math.max(0,String(t).split(".")[1]?.length||0):2;return n.toFixed(Math.min(8,d)).replace(/(\.\d*?[1-9])0+$|\.0+$/,"$1");}
const usd=v=>`$${Math.abs(Number(v||0)).toFixed(2)}`;
const signedUsd=v=>`${Number(v||0)>=0?"+":"-"}$${Math.abs(Number(v||0)).toFixed(2)}`;

async function sendOnce(env,fingerprint,text,meta={}){
  const ctl=await kvGet(env,CONTROL_KEY,{}),seen=Array.isArray(ctl.tradeActionNotifications)?ctl.tradeActionNotifications:[];
  if(seen.some(x=>x?.fingerprint===fingerprint))return {sent:false,reason:"ALREADY_NOTIFIED",fingerprint};
  try{await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});ctl.tradeActionNotifications=[{fingerprint,at:iso(),...meta},...seen].slice(0,240);ctl.lastTradeActionNotifyError=null;await kvPut(env,CONTROL_KEY,ctl);return {sent:true,fingerprint};}
  catch(e){ctl.lastTradeActionNotifyError={at:iso(),fingerprint,error:String(e?.message||e),...meta};await kvPut(env,CONTROL_KEY,ctl);return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e)};}
}

async function notifyLiveEntry(env,out){
  if(!(out?.executed&&out?.mode==="LIVE"&&out?.plan?.orderId))return {sent:false,reason:"NO_NEW_LIVE_BTC_ENTRY"};
  const p=out.plan,orderId=String(p.orderId),s=await kvGet(env,AUTO_KEY,{}),notified=Array.isArray(s.telegramNotifiedOrderIds)?s.telegramNotifiedOrderIds.map(String):[];
  if(notified.includes(orderId))return {sent:false,reason:"ALREADY_NOTIFIED",orderId};
  const side=String(p.side||"").toUpperCase()==="BUY"?"BUY":"SELL",icon=side==="BUY"?"🟢":"🔴",tick=Number(p.tickSize||0),tranches=Number(p.trancheCount||s?.tranches?.filter?.(x=>String(x.status||"OPEN")==="OPEN")?.length||1),capital=Number(p.capitalBaseUsd||s.lastCapitalBaseUsd||0),scale=Number(p.scaleRiskMult||p.riskMult||0);
  const text=[`${icon} BTCUSDT ${side} • tranche ${tranches}`,`Entry ${compactPrice(p.entry,tick)} • qty ${Number(p.qty||0).toFixed(6)} BTC`,`SL ${compactPrice(p.sl,tick)} • risk ${usd(p.riskUsd)}`,`Virtual target ${compactPrice(p.tp,tick)} • RR ${Number(p.rr||0).toFixed(2)}`,`${Number(p.leverage||0)}x • ${p.setup||"BTC_STRUCTURE_FLOW"}`,`${p.regime||"REGIME"} • winner-pyramid / risk-recycle`,capital>0?`Capital base $${capital.toFixed(2)}${scale>0?` • scale ×${scale.toFixed(3)}`:""}`:null,`${BYBIT_AUTO_VERSION} • LIVE`].filter(Boolean).join("\n");
  try{await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});s.telegramNotifiedOrderIds=[orderId,...notified.filter(x=>x!==orderId)].slice(0,160);s.lastTelegramOrderId=orderId;s.lastTelegramEntryAt=iso();await kvPut(env,AUTO_KEY,s);return {sent:true,orderId};}
  catch(e){return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e),orderId};}
}

async function notifyLifecycleActions(env,out){
  if(out?.mode!=="LIVE")return [];
  const sent=[];
  for(const x of out?.lifecycles||[]){const symbol=String(x.symbol||"BTCUSDT");if(x.cutExecuted||x.verdict==="CUT"){sent.push(await sendOnce(env,`BTC:CUT:${x.orderId||x.reason||Date.now()}`,[`✂️ BTC SMART CUT`,`${x.reason||"STRUCTURE_FLOW_INVALIDATION"}`,`Mark ${compactPrice(x.markPrice)} • R ${Number(x.r||0).toFixed(2)}`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol,action:"CUT"}));continue;}if(x.verdict==="TIGHTEN"){const phase=String(x.phase||"PROTECT"),title=phase==="TRAIL"?"📐 BTC TRAILING":phase==="PROFIT_LOCK"?"🔒 BTC BE / PROFIT LOCK":"🛡️ BTC PROTECTION";sent.push(await sendOnce(env,`BTC:STOP:${phase}:${x.nextSl}`,[title,`SL ${compactPrice(x.previousSl)} → ${compactPrice(x.nextSl)}`,`Latest tranche R ${Number(x.r||0).toFixed(2)}`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol,action:phase}));}}
  return sent;
}

function classifyClose(row,previous={}){const exit=Number(row.avgExitPrice||0),sl=Number(previous.lastKnownStopUsd||0),tp=Number(previous.lastKnownTargetUsd||0),tol=Math.max(5,exit*.00015);if(exit>0&&sl>0&&Math.abs(exit-sl)<=tol)return "SL / PROTECTION";if(exit>0&&tp>0&&Math.abs(exit-tp)<=tol)return "TP / TARGET";if(String(previous.lastCycleReason||"")==="SMART_CUT")return "SMART CUT";return "OTHER / EXCHANGE CLOSE";}
async function notifyClosedPnl(env,mode,previous={},walletAfter=0){
  const now=Date.now(),last=Number(previous.closedPnlLastCheckMs||0);if(mode!=="LIVE")return {checkedAtMs:now,baseline:false,notifications:[],reason:"NOT_LIVE"};if(!(last>0))return {checkedAtMs:now,baseline:true,notifications:[],reason:"BASELINE_ESTABLISHED"};
  try{const api=bybitV5(env),start=Math.max(now-6*3600000,last-120000),r=await api.closedPnl(start,now),rows=(r?.result?.list||[]).filter(x=>String(x.symbol)==="BTCUSDT"&&Number(x.updatedTime||x.createdTime||0)>last-1000),sent=[];for(const x of rows){const id=String(x.orderId||x.execId||`${x.updatedTime}:${x.avgExitPrice}:${x.closedPnl}`),pnl=Number(x.closedPnl||0),cause=classifyClose(x,previous),side=String(x.side||""),entry=Number(x.avgEntryPrice||0),exit=Number(x.avgExitPrice||0),qty=Number(x.qty||x.closedSize||0);sent.push(await sendOnce(env,`BTC:CLOSED:${id}`,[pnl>=0?`✅ BTC POSITION CLOSED ${signedUsd(pnl)}`:`❌ BTC POSITION CLOSED ${signedUsd(pnl)}`,`Cause ${cause}`,`${side.toUpperCase()} ${qty?qty.toFixed(6):"—"} BTC`,`Entry ${compactPrice(entry)} → Exit ${compactPrice(exit)}`,`Balance after ≈ $${Number(walletAfter||0).toFixed(2)}`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol:"BTCUSDT",action:"CLOSED",cause,pnlUsd:pnl}));}return {checkedAtMs:now,baseline:false,notifications:sent,rows:rows.length};}
  catch(e){return {checkedAtMs:now,baseline:false,notifications:[],reason:"CLOSED_PNL_READ_FAILED",error:String(e?.message||e)};}
}

function scanTelemetry(scan={}){const b=scan?.best;return {scannedAt:Number(scan?.scannedAt||0)||null,universe:1,analyzed:Number(scan?.analyzed||1),rawCandidates:Number(scan?.rawCandidates||0),qualified:Number(scan?.qualified||0),reason:scan?.reason||null,best:b?{symbol:b.symbol,side:b.side,setup:b.setup,strength:b.strength,rr:b.rr,regime:b.regime}:null};}

export async function recordBybitAutoSchedulerError(env,error){const ctl=await kvGet(env,CONTROL_KEY,{}),count=Number(ctl.consecutiveSchedulerErrors||0)+1,msg=String(error?.message||error||"UNKNOWN").slice(0,300);ctl.consecutiveSchedulerErrors=count;ctl.lastSchedulerError={at:iso(),error:msg};ctl.lastCycleAt=iso();ctl.lastCycleReason="BTC_SCHEDULER_EXCEPTION";ctl.lastCycleExecuted=false;await kvPut(env,CONTROL_KEY,ctl);if(count===1||count%10===0)await sendOnce(env,`BTC:SCHEDULER:${Math.floor(Date.now()/3600000)}`,[`⚠️ BTC BOT SCHEDULER ERROR`,`Count ${count}`,msg,`${BYBIT_AUTO_VERSION}`].join("\n"),{action:"SCHEDULER_ERROR"});return {ok:false,reason:"BTC_SCHEDULER_EXCEPTION",error:msg,count};}

export async function runBybitAutoControlled(env,opts={}){
  const balanceReconcile=await reconcileBtcAccountBalance(env),previousBefore=await kvGet(env,CONTROL_KEY,{});
  const cfg=bybitAutoConfig(env),requestedLive=envBool(env.BYBIT_AUTO_LIVE),btcAck=envBool(env.BYBIT_BTC_LIVE_ACK),mode=requestedLive&&btcAck?"LIVE":"PAPER",state=await getBtcHyperscaleState(env),lastTradeAt=Number(state?.lastTradeAt||0),spacingMs=Math.max(0,Number(cfg.execution?.cooldownSec||0))*1000,elapsed=Date.now()-lastTradeAt,spacingActive=spacingMs>0&&lastTradeAt>0&&elapsed<spacingMs,entryBlockReason=spacingActive?`BTC_ENTRY_SPACING_${Math.round(spacingMs/1000)}S`:null;
  const out=await runBtcHyperscale(env,{...opts,entryBlockReason}),telegramNotification=await notifyLiveEntry(env,out),lifecycleNotifications=await notifyLifecycleActions(env,out),finalState=out?.state||state,walletAfter=Number(balanceReconcile?.snapshot?.walletBalanceUsd||finalState?.lastWalletBalanceUsd||0),closedPnlTelemetry=await notifyClosedPnl(env,out?.mode||mode,previousBefore,walletAfter);
  const previous=await kvGet(env,CONTROL_KEY,{}),plan=out?.plan||null,activeCount=Array.isArray(finalState?.tranches)?finalState.tranches.filter(x=>String(x.status||"OPEN")==="OPEN").length:0,controller={...previous,executionMode:out?.mode||mode,requestedLive,btcLiveAck:btcAck,liveAuthority:requestedLive&&btcAck?"BTC_ONLY":"PAPER_SAFE_MIGRATION",entrySpacingSec:spacingMs/1000,entryBlockReason,unlimitedDailyEntries:true,frequencyAuthority:"ACTIVE_RISK_MARGIN_DRAWDOWN_NOT_TRADE_COUNT",managementAlwaysOn:true,legacyMultiCoinDisabled:true,symbol:"BTCUSDT",strategyAuthority:"MARKET_STRUCTURE_ORDERFLOW_DERIVATIVES_MICROSTRUCTURE",balanceAuthority:"BYBIT_WALLET_PLUS_TRANSACTION_LOG",depositWithdrawalAware:true,continuousScale:true,balanceReconcile:{ok:!!balanceReconcile?.ok,reason:balanceReconcile?.reason||null,netExternalCashFlowUsd:Number(balanceReconcile?.netExternalCashFlowUsd||0),walletBalanceUsd:walletAfter||null,equityUsd:Number(balanceReconcile?.snapshot?.equityUsd||out?.equity||finalState?.lastEquityUsd||0)||null,availableUsd:Number(balanceReconcile?.snapshot?.availableUsd||finalState?.lastAvailableUsd||0)||null},telegramNotification,lifecycleNotifications,closedPnlTelemetry,equityUsd:Number(out?.equity||finalState?.lastEquityUsd||0)||null,walletBalanceUsd:walletAfter||null,availableUsd:Number(finalState?.lastAvailableUsd||balanceReconcile?.snapshot?.availableUsd||0)||null,highWaterUsd:Number(finalState?.highWaterUsd||0)||null,activeTranches:activeCount,lastKnownStopUsd:activeCount?Number(plan?.managedSl||plan?.sl||finalState?.aggregateStop||previous.lastKnownStopUsd||0):Number(previous.lastKnownStopUsd||0),lastKnownTargetUsd:activeCount?Number(plan?.tp||finalState?.virtualTarget||previous.lastKnownTargetUsd||0):Number(previous.lastKnownTargetUsd||0),closedPnlLastCheckMs:closedPnlTelemetry.checkedAtMs,lastCycleAt:iso(),lastCycleReason:String(out?.reason||"UNKNOWN"),lastCycleExecuted:!!out?.executed,lastScan:scanTelemetry(out?.scan||{}),consecutiveSchedulerErrors:0,lastSchedulerError:null,runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN")};await kvPut(env,CONTROL_KEY,controller);return {...out,balanceReconcile,controller};
}
