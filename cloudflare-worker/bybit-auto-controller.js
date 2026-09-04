import {runBtcHyperscale,getBtcHyperscaleState} from "./bybit-btc-engine.js";
import {reconcileBtcAccountBalance} from "./bybit-btc-balance-reconciler.js";
import {telegramApiRequest} from "./providers/telegram-client.js";
import {bybitV5} from "./bybit-v5-client.js";
import {BYBIT_AUTO_VERSION} from "./bybit-auto-config.js";

const AUTO_KEY="bybit:btc:hyperscale:v2:state";
const CONTROL_KEY="bybit:auto:v1:controller";
const iso=()=>new Date().toISOString();
const envBool=v=>String(v||"").toLowerCase()==="true";
async function kvGet(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function kvPut(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
function compactPrice(v,tick=0){const n=Number(v);if(!Number.isFinite(n)||n<=0)return "—";const t=Math.abs(Number(tick||0));let d=t>0?Math.max(0,String(t).split(".")[1]?.length||0):2;return n.toFixed(Math.min(8,d)).replace(/(\.\d*?[1-9])0+$|\.0+$/,"$1");}
const usd=v=>`$${Math.abs(Number(v||0)).toFixed(2)}`;
const signedUsd=v=>`${Number(v||0)>=0?"+":"-"}$${Math.abs(Number(v||0)).toFixed(2)}`;
const h=v=>String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const openTranches=s=>(Array.isArray(s?.tranches)?s.tranches:[]).filter(x=>String(x.status||"OPEN")==="OPEN");
function grossReward(side,entry,tp,qty){const e=Number(entry||0),t=Number(tp||0),q=Math.abs(Number(qty||0));if(!(e>0&&t>0&&q>0))return 0;return Math.max(0,String(side)==="Sell"?e-t:t-e)*q;}

async function sendOnce(env,fingerprint,text,meta={}){
  const ctl=await kvGet(env,CONTROL_KEY,{}),seen=Array.isArray(ctl.tradeActionNotifications)?ctl.tradeActionNotifications:[];
  if(seen.some(x=>x?.fingerprint===fingerprint))return {sent:false,reason:"ALREADY_NOTIFIED",fingerprint};
  try{await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,parse_mode:"HTML",disable_web_page_preview:true});ctl.tradeActionNotifications=[{fingerprint,at:iso(),...meta},...seen].slice(0,240);ctl.lastTradeActionNotifyError=null;await kvPut(env,CONTROL_KEY,ctl);return {sent:true,fingerprint};}
  catch(e){ctl.lastTradeActionNotifyError={at:iso(),fingerprint,error:String(e?.message||e),...meta};await kvPut(env,CONTROL_KEY,ctl);return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e),fingerprint};}
}

function entryCandidateFromTranche(t={},state={}){const qty=Number(t.qty||0),entry=Number(t.entry||0),tp=Number(t.tp||state.virtualTarget||0),costReserveUsd=Number(t.costReserveUsd||0),gross=Number(t.plannedGrossProfitUsd||grossReward(t.side,entry,tp,qty)),net=Number.isFinite(Number(t.plannedNetProfitUsd))?Number(t.plannedNetProfitUsd):Math.max(0,gross-costReserveUsd);return {orderId:String(t.orderId||t.id||""),side:t.side,qty,entry,sl:Number(t.managedSl||t.sl||0),tp,riskUsd:Number(t.riskUsd||t.initialRiskUsd||0),rewardUsd:gross,plannedNetProfitUsd:net,minPlannedNetProfitUsd:Number(t.minPlannedNetProfitUsd||0),costReserveUsd,rr:Number(t.rr||0),leverage:Number(t.leverage||0),setup:t.setup||"BTC_STRUCTURE_FLOW",regime:t.regime||state.lastRegime||"REGIME",executionIntent:t.executionIntent||"",orderType:t.orderType||"",tickSize:Number(t.tickSize||0),capitalBaseUsd:Number(t.capitalBaseUsd||state.lastCapitalBaseUsd||0),scaleRiskMult:Number(t.scaleRiskMult||0),reconciledExternalPosition:!!t.reconciledExternalPosition,createdAtMs:Number(t.createdAt||0)};}
function entryCandidates(out={},state={}){
  const rows=[];if(out?.executed&&out?.mode==="LIVE"&&out?.plan?.orderId)rows.push({...out.plan,reconciledExternalPosition:false});
  for(const t of openTranches(state)){const p=entryCandidateFromTranche(t,state);if(p.orderId)rows.push(p);}
  const seen=new Set();return rows.filter(x=>{const id=String(x.orderId||"");if(!id||seen.has(id))return false;seen.add(id);return true;}).sort((a,b)=>Number(a.createdAtMs||0)-Number(b.createdAtMs||0));
}
async function notifyPendingLiveEntries(env,out,state={}){
  const mode=String(out?.mode||state.executionMode||"");if(mode!=="LIVE")return {sent:false,reason:"NOT_LIVE"};
  const s=await kvGet(env,AUTO_KEY,state||{}),notified=new Set((Array.isArray(s.telegramNotifiedOrderIds)?s.telegramNotifiedOrderIds:[]).map(String)),pending=entryCandidates(out,state).filter(p=>!notified.has(String(p.orderId))).slice(-4);
  if(!pending.length)return {sent:false,reason:"NO_PENDING_LIVE_ENTRY_ALERT"};
  const results=[];
  for(const p of pending){
    const orderId=String(p.orderId),side=String(p.side||"").toUpperCase()==="BUY"?"BUY":"SELL",icon=side==="BUY"?"🟢":"🔴",tick=Number(p.tickSize||0),reconciled=!!p.reconciledExternalPosition,gross=Number(p.rewardUsd||grossReward(p.side,p.entry,p.tp,p.qty)),cost=Math.max(0,Number(p.costReserveUsd||0)),net=Number.isFinite(Number(p.plannedNetProfitUsd))?Number(p.plannedNetProfitUsd):Math.max(0,gross-cost),route=String(p.executionIntent||p.orderType||"");
    const text=[reconciled?`🔄 <b>BTC ${h(side)} · RECONCILED</b>`:`${icon} <b>BTC ${h(side)} · LIVE</b>`,`<code>ENTRY  ${compactPrice(p.entry,tick)}</code>`,`<code>TP     ${compactPrice(p.tp,tick)}  +$${Math.max(0,net).toFixed(2)} net</code>`,`<code>SL     ${compactPrice(p.sl,tick)}  -$${Math.abs(Number(p.riskUsd||0)).toFixed(2)}</code>`,`<code>${Number(p.qty||0).toFixed(6)} BTC · ${Number(p.leverage||0)}x · RR ${Number(p.rr||0).toFixed(2)}</code>`,`<i>${h(p.setup||"BTC_STRUCTURE_FLOW")} · ${h(p.regime||"REGIME")}</i>`,route?`↳ Route ${h(route)}${cost>0?` · Cost reserve ${usd(cost)}`:""}`:cost>0?`↳ Cost reserve ${usd(cost)}`:null].filter(Boolean).join("\n");
    try{await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,parse_mode:"HTML",disable_web_page_preview:true});notified.add(orderId);results.push({sent:true,orderId,reconciled});}
    catch(e){results.push({sent:false,orderId,reconciled,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e)});break;}
  }
  s.telegramNotifiedOrderIds=[...notified].slice(-200);const lastOk=[...results].reverse().find(x=>x.sent);if(lastOk){s.lastTelegramOrderId=lastOk.orderId;s.lastTelegramEntryAt=iso();}const failed=results.find(x=>!x.sent);s.lastTelegramEntryError=failed?{at:iso(),orderId:failed.orderId,error:failed.error}:null;await kvPut(env,AUTO_KEY,s);
  return {sent:results.some(x=>x.sent),sentCount:results.filter(x=>x.sent).length,pendingCount:pending.length,results,reason:failed?"PARTIAL_OR_FAILED":"ENTRY_ALERTS_CONFIRMED"};
}

async function notifyLifecycleActions(env,out){
  if(out?.mode!=="LIVE")return [];
  const sent=[];
  for(const x of out?.lifecycles||[]){const symbol=String(x.symbol||"BTCUSDT");if(x.cutExecuted||x.verdict==="CUT"){sent.push(await sendOnce(env,`BTC:CUT:${x.orderId||x.reason||Date.now()}`,[`✂️ <b>BTC SMART CUT</b>`,`<code>MARK ${compactPrice(x.markPrice)} · R ${Number(x.r||0).toFixed(2)}</code>`,`<i>${h(x.reason||"STRUCTURE_FLOW_INVALIDATION")}</i>`].join("\n"),{symbol,action:"CUT"}));continue;}if(x.verdict==="TIGHTEN"){const phase=String(x.phase||"PROTECT"),title=phase.includes("TRAIL")?"📐 BTC SCALP TRAIL":phase.includes("PROFIT_LOCK")||phase.includes("DECELERATION")?"🔒 BTC PROFIT LOCK":"🛡️ BTC PROTECTION";sent.push(await sendOnce(env,`BTC:STOP:${phase}:${x.nextSl}`,[`<b>${h(title)}</b>`,`<code>SL ${compactPrice(x.previousSl)} → ${compactPrice(x.nextSl)} · R ${Number(x.r||0).toFixed(2)}</code>`].join("\n"),{symbol,action:phase}));}}
  return sent;
}

function classifyClose(row,previous={}){const exit=Number(row.avgExitPrice||0),sl=Number(previous.lastKnownStopUsd||0),tp=Number(previous.lastKnownTargetUsd||0),tol=Math.max(5,exit*.00015);if(exit>0&&sl>0&&Math.abs(exit-sl)<=tol)return "SL / PROTECTION";if(exit>0&&tp>0&&Math.abs(exit-tp)<=tol)return "TP / TARGET";if(String(previous.lastCycleReason||"")==="SMART_CUT")return "SMART CUT";return "OTHER / EXCHANGE CLOSE";}
async function notifyClosedPnl(env,mode,previous={},walletAfter=0){
  const now=Date.now(),last=Number(previous.closedPnlLastCheckMs||0);if(mode!=="LIVE")return {checkedAtMs:now,baseline:false,notifications:[],reason:"NOT_LIVE"};if(!(last>0))return {checkedAtMs:now,baseline:true,notifications:[],reason:"BASELINE_ESTABLISHED"};
  try{const api=bybitV5(env),start=Math.max(now-6*3600000,last-120000),r=await api.closedPnl(start,now),rows=(r?.result?.list||[]).filter(x=>String(x.symbol)==="BTCUSDT"&&Number(x.updatedTime||x.createdTime||0)>last-1000),sent=[];for(const x of rows){const id=String(x.orderId||x.execId||`${x.updatedTime}:${x.avgExitPrice}:${x.closedPnl}`),pnl=Number(x.closedPnl||0),cause=classifyClose(x,previous),side=String(x.side||""),entry=Number(x.avgEntryPrice||0),exit=Number(x.avgExitPrice||0),qty=Number(x.qty||x.closedSize||0);sent.push(await sendOnce(env,`BTC:CLOSED:${id}`,[pnl>=0?`✅ <b>BTC CLOSED ${h(signedUsd(pnl))}</b>`:`❌ <b>BTC CLOSED ${h(signedUsd(pnl))}</b>`,`<code>${h(side.toUpperCase())} ${qty?qty.toFixed(6):"—"} BTC · ${compactPrice(entry)} → ${compactPrice(exit)}</code>`,`${h(cause)} · BAL <b>$${Number(walletAfter||0).toFixed(2)}</b>`].join("\n"),{symbol:"BTCUSDT",action:"CLOSED",cause,pnlUsd:pnl}));}return {checkedAtMs:now,baseline:false,notifications:sent,rows:rows.length};}
  catch(e){return {checkedAtMs:now,baseline:false,notifications:[],reason:"CLOSED_PNL_READ_FAILED",error:String(e?.message||e)};}
}

function scanTelemetry(scan={}){const b=scan?.best;return {scannedAt:Number(scan?.scannedAt||0)||null,universe:1,analyzed:Number(scan?.analyzed||1),rawCandidates:Number(scan?.rawCandidates||0),qualified:Number(scan?.qualified||0),reason:scan?.reason||null,best:b?{symbol:b.symbol,side:b.side,setup:b.setup,strength:b.strength,rr:b.rr,regime:b.regime,executionIntent:b.executionIntent||null}:null};}
function benignSchedulerError(error){const s=String(error?.bybit?.retMsg||error?.message||error||"").toLowerCase();return s.includes("not modified")||s.includes("not modify")||s.includes("already set")||s.includes("same as current")||s.includes("trading_stop_unchanged")||s.includes("leverage_unchanged");}
export async function recordBybitAutoSchedulerError(env,error){
  const ctl=await kvGet(env,CONTROL_KEY,{}),msg=String(error?.message||error||"UNKNOWN").slice(0,300);
  if(benignSchedulerError(error)){ctl.consecutiveSchedulerErrors=0;ctl.lastBenignSchedulerEvent={at:iso(),message:msg};ctl.lastCycleAt=iso();ctl.lastCycleReason="IDEMPOTENT_WRITE_NO_CHANGE";ctl.lastCycleExecuted=false;await kvPut(env,CONTROL_KEY,ctl);return {ok:true,reason:"IDEMPOTENT_WRITE_NO_CHANGE",message:msg};}
  const count=Number(ctl.consecutiveSchedulerErrors||0)+1;ctl.consecutiveSchedulerErrors=count;ctl.lastSchedulerError={at:iso(),error:msg};ctl.lastCycleAt=iso();ctl.lastCycleReason="BTC_EVENT_CYCLE_EXCEPTION";ctl.lastCycleExecuted=false;await kvPut(env,CONTROL_KEY,ctl);if(count===1||count%10===0)await sendOnce(env,`BTC:EVENT_ERROR:${Math.floor(Date.now()/3600000)}`,[`⚠️ <b>BTC EVENT ERROR · ${count}</b>`,`<code>${h(msg)}</code>`].join("\n"),{action:"EVENT_CYCLE_ERROR"});return {ok:false,reason:"BTC_EVENT_CYCLE_EXCEPTION",error:msg,count};
}

export async function runBybitAutoControlled(env,opts={}){
  const balanceReconcile=await reconcileBtcAccountBalance(env),previousBefore=await kvGet(env,CONTROL_KEY,{});
  const requestedLive=envBool(env.BYBIT_AUTO_LIVE),btcAck=envBool(env.BYBIT_BTC_LIVE_ACK),mode=requestedLive&&btcAck?"LIVE":"PAPER",state=await getBtcHyperscaleState(env);
  const out=await runBtcHyperscale(env,{...opts,entryBlockReason:null}),finalState=out?.state||state,telegramNotification=await notifyPendingLiveEntries(env,out,finalState),lifecycleNotifications=await notifyLifecycleActions(env,out),walletAfter=Number(balanceReconcile?.snapshot?.walletBalanceUsd||finalState?.lastWalletBalanceUsd||0),closedPnlTelemetry=await notifyClosedPnl(env,out?.mode||mode,previousBefore,walletAfter);
  const previous=await kvGet(env,CONTROL_KEY,{}),plan=out?.plan||null,activeCount=openTranches(finalState).length,controller={...previous,executionMode:out?.mode||mode,requestedLive,btcLiveAck:btcAck,liveAuthority:requestedLive&&btcAck?"BTC_ONLY":"PAPER_SAFE_MIGRATION",entrySpacingSec:0,entryBlockReason:null,timeGate:false,eventDriven:true,decisionAuthority:"VPS_WS_MARKET_STATE_CHANGE",unlimitedDailyEntries:true,frequencyAuthority:"ACTIVE_RISK_MARGIN_DRAWDOWN_NOT_TRADE_COUNT",managementAlwaysOn:true,legacyMultiCoinDisabled:true,symbol:"BTCUSDT",strategyAuthority:"MARKET_STRUCTURE_ORDERFLOW_DERIVATIVES_MICROSTRUCTURE",balanceAuthority:"BYBIT_WALLET_PLUS_TRANSACTION_LOG",depositWithdrawalAware:true,continuousScale:true,balanceReconcile:{ok:!!balanceReconcile?.ok,reason:balanceReconcile?.reason||null,netExternalCashFlowUsd:Number(balanceReconcile?.netExternalCashFlowUsd||0),walletBalanceUsd:walletAfter||null,equityUsd:Number(balanceReconcile?.snapshot?.equityUsd||out?.equity||finalState?.lastEquityUsd||0)||null,availableUsd:Number(balanceReconcile?.snapshot?.availableUsd||finalState?.lastAvailableUsd||0)||null},telegramNotification,lifecycleNotifications,closedPnlTelemetry,equityUsd:Number(out?.equity||finalState?.lastEquityUsd||0)||null,walletBalanceUsd:walletAfter||null,availableUsd:Number(finalState?.lastAvailableUsd||balanceReconcile?.snapshot?.availableUsd||0)||null,highWaterUsd:Number(finalState?.highWaterUsd||0)||null,activeTranches:activeCount,lastKnownStopUsd:activeCount?Number(plan?.managedSl||plan?.sl||finalState?.aggregateStop||previous.lastKnownStopUsd||0):Number(previous.lastKnownStopUsd||0),lastKnownTargetUsd:activeCount?Number(plan?.tp||finalState?.virtualTarget||previous.lastKnownTargetUsd||0):Number(previous.lastKnownTargetUsd||0),closedPnlLastCheckMs:closedPnlTelemetry.checkedAtMs,lastCycleAt:iso(),lastCycleReason:String(out?.reason||"UNKNOWN"),lastCycleExecuted:!!out?.executed,lastScan:scanTelemetry(out?.scan||{}),consecutiveSchedulerErrors:0,lastSchedulerError:null,runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN")};await kvPut(env,CONTROL_KEY,controller);return {...out,balanceReconcile,controller};
}