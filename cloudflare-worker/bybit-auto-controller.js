import {runBtcHyperscale,getBtcHyperscaleState} from "./bybit-btc-engine.js";
import {telegramApiRequest} from "./providers/telegram-client.js";
import {BYBIT_AUTO_VERSION,bybitAutoConfig} from "./bybit-auto-config.js";

const AUTO_KEY="bybit:btc:hyperscale:v2:state";
// Keep the historical controller key so the existing health/dashboard surface keeps working during migration.
const CONTROL_KEY="bybit:auto:v1:controller";
const iso=()=>new Date().toISOString();
const envBool=v=>String(v||"").toLowerCase()==="true";
async function kvGet(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function kvPut(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
function compactPrice(v,tick=0){const n=Number(v);if(!Number.isFinite(n))return "—";const t=Math.abs(Number(tick||0));let d=t>0?Math.max(0,String(t).split(".")[1]?.length||0):2;return n.toFixed(Math.min(8,d)).replace(/(\.\d*?[1-9])0+$|\.0+$/,"$1");}
const usd=v=>`$${Math.abs(Number(v||0)).toFixed(2)}`;

async function sendOnce(env,fingerprint,text,meta={}){
  const ctl=await kvGet(env,CONTROL_KEY,{}),seen=Array.isArray(ctl.tradeActionNotifications)?ctl.tradeActionNotifications:[];
  if(seen.some(x=>x?.fingerprint===fingerprint))return {sent:false,reason:"ALREADY_NOTIFIED",fingerprint};
  try{await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});ctl.tradeActionNotifications=[{fingerprint,at:iso(),...meta},...seen].slice(0,160);ctl.lastTradeActionNotifyError=null;await kvPut(env,CONTROL_KEY,ctl);return {sent:true,fingerprint};}
  catch(e){ctl.lastTradeActionNotifyError={at:iso(),fingerprint,error:String(e?.message||e),...meta};await kvPut(env,CONTROL_KEY,ctl);return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e)};}
}

async function notifyLiveEntry(env,out){
  if(!(out?.executed&&out?.mode==="LIVE"&&out?.plan?.orderId))return {sent:false,reason:"NO_NEW_LIVE_BTC_ENTRY"};
  const p=out.plan,orderId=String(p.orderId),s=await kvGet(env,AUTO_KEY,{}),notified=Array.isArray(s.telegramNotifiedOrderIds)?s.telegramNotifiedOrderIds.map(String):[];
  if(notified.includes(orderId))return {sent:false,reason:"ALREADY_NOTIFIED",orderId};
  const side=String(p.side||"").toUpperCase()==="BUY"?"BUY":"SELL",icon=side==="BUY"?"🟢":"🔴",tick=Number(p.tickSize||0),tranches=Number(p.trancheCount||s?.tranches?.filter?.(x=>String(x.status||"OPEN")==="OPEN")?.length||1);
  const text=[`${icon} BTCUSDT ${side} • tranche ${tranches}`,`Entry ${compactPrice(p.entry,tick)}`,`SL ${compactPrice(p.sl,tick)} • risk ${usd(p.riskUsd)}`,`Virtual target ${compactPrice(p.tp,tick)} • RR ${Number(p.rr||0).toFixed(2)}`,`${Number(p.leverage||0)}x • ${p.setup||"BTC_STRUCTURE_FLOW"}`,`${p.regime||"REGIME"} • winner-pyramid / risk-recycle`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n");
  try{await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});s.telegramNotifiedOrderIds=[orderId,...notified.filter(x=>x!==orderId)].slice(0,120);s.lastTelegramOrderId=orderId;s.lastTelegramEntryAt=iso();await kvPut(env,AUTO_KEY,s);return {sent:true,orderId};}
  catch(e){return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e),orderId};}
}

async function notifyLifecycleActions(env,out){
  if(out?.mode!=="LIVE")return [];
  const sent=[];
  for(const x of out?.lifecycles||[]){const symbol=String(x.symbol||"BTCUSDT");if(x.cutExecuted||x.verdict==="CUT"){sent.push(await sendOnce(env,`BTC:CUT:${x.orderId||x.reason||Date.now()}`,[`✂️ BTC SMART CUT`,`${x.reason||"STRUCTURE_FLOW_INVALIDATION"}`,`Mark ${compactPrice(x.markPrice)} • R ${Number(x.r||0).toFixed(2)}`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol,action:"CUT"}));continue;}if(x.verdict==="TIGHTEN"){sent.push(await sendOnce(env,`BTC:STOP:${x.phase}:${x.nextSl}`,[`🛡️ BTC ${x.phase||"PROTECT"}`,`SL ${compactPrice(x.previousSl)} → ${compactPrice(x.nextSl)}`,`Latest tranche R ${Number(x.r||0).toFixed(2)}`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol,action:x.phase||"TIGHTEN"}));}}
  return sent;
}

function scanTelemetry(scan={}){const b=scan?.best;return {scannedAt:Number(scan?.scannedAt||0)||null,universe:1,analyzed:Number(scan?.analyzed||1),rawCandidates:Number(scan?.rawCandidates||0),qualified:Number(scan?.qualified||0),reason:scan?.reason||null,best:b?{symbol:b.symbol,side:b.side,setup:b.setup,strength:b.strength,rr:b.rr,regime:b.regime}:null};}

export async function recordBybitAutoSchedulerError(env,error){const ctl=await kvGet(env,CONTROL_KEY,{}),count=Number(ctl.consecutiveSchedulerErrors||0)+1,msg=String(error?.message||error||"UNKNOWN").slice(0,300);ctl.consecutiveSchedulerErrors=count;ctl.lastSchedulerError={at:iso(),error:msg};ctl.lastCycleAt=iso();ctl.lastCycleReason="BTC_SCHEDULER_EXCEPTION";ctl.lastCycleExecuted=false;await kvPut(env,CONTROL_KEY,ctl);if(count===1||count%10===0)await sendOnce(env,`BTC:SCHEDULER:${Math.floor(Date.now()/3600000)}`,[`⚠️ BTC BOT SCHEDULER ERROR`,`Count ${count}`,msg,`${BYBIT_AUTO_VERSION}`].join("\n"),{action:"SCHEDULER_ERROR"});return {ok:false,reason:"BTC_SCHEDULER_EXCEPTION",error:msg,count};}

export async function runBybitAutoControlled(env,opts={}){
  const cfg=bybitAutoConfig(env),requestedLive=envBool(env.BYBIT_AUTO_LIVE),btcAck=envBool(env.BYBIT_BTC_LIVE_ACK),mode=requestedLive&&btcAck?"LIVE":"PAPER",state=await getBtcHyperscaleState(env),lastTradeAt=Number(state?.lastTradeAt||0),spacingMs=Math.max(0,Number(cfg.execution?.cooldownSec||0))*1000,elapsed=Date.now()-lastTradeAt,spacingActive=spacingMs>0&&lastTradeAt>0&&elapsed<spacingMs,entryBlockReason=spacingActive?`BTC_ENTRY_SPACING_${Math.round(spacingMs/1000)}S`:null;
  const out=await runBtcHyperscale(env,{...opts,entryBlockReason}),telegramNotification=await notifyLiveEntry(env,out),lifecycleNotifications=await notifyLifecycleActions(env,out),finalState=out?.state||state;
  const previous=await kvGet(env,CONTROL_KEY,{}),controller={...previous,executionMode:out?.mode||mode,requestedLive,btcLiveAck:btcAck,liveAuthority:requestedLive&&btcAck?"BTC_ONLY":"PAPER_SAFE_MIGRATION",entrySpacingSec:spacingMs/1000,entryBlockReason,unlimitedDailyEntries:true,frequencyAuthority:"ACTIVE_RISK_MARGIN_DRAWDOWN_NOT_TRADE_COUNT",managementAlwaysOn:true,legacyMultiCoinDisabled:true,symbol:"BTCUSDT",strategyAuthority:"MARKET_STRUCTURE_ORDERFLOW_DERIVATIVES_MICROSTRUCTURE",telegramNotification,lifecycleNotifications,equityUsd:Number(out?.equity||finalState?.lastEquityUsd||0)||null,highWaterUsd:Number(finalState?.highWaterUsd||0)||null,activeTranches:Array.isArray(finalState?.tranches)?finalState.tranches.filter(x=>String(x.status||"OPEN")==="OPEN").length:0,lastCycleAt:iso(),lastCycleReason:String(out?.reason||"UNKNOWN"),lastCycleExecuted:!!out?.executed,lastScan:scanTelemetry(out?.scan||{}),consecutiveSchedulerErrors:0,lastSchedulerError:null,runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN")};await kvPut(env,CONTROL_KEY,controller);return {...out,controller};
}
