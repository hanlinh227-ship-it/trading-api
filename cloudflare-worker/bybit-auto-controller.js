import {runBybitAutoV1,getBybitAutoV1State} from "./bybit-auto-v1.js";
import {bybitV5} from "./bybit-v5-client.js";
import {telegramApiRequest} from "./providers/telegram-client.js";
import {BYBIT_AUTO_VERSION,bybitAutoConfig} from "./bybit-auto-config.js";

const AUTO_KEY="bybit:auto:v1:state";
const CONTROL_KEY="bybit:auto:v1:controller";
const now=()=>Date.now();
const iso=()=>new Date().toISOString();
function day(){return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Bangkok",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());}
function dayStartMs(){return Date.parse(`${day()}T00:00:00+07:00`);}
async function kvGet(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function kvPut(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
function eventTime(x){return Number(x?.updatedTime||x?.createdTime||0);}
function compactPrice(v,tick=0){
  const n=Number(v);if(!Number.isFinite(n))return "—";
  const t=Math.abs(Number(tick||0));let d=8;
  if(t>0){const s=t.toFixed(12).replace(/0+$/,"");const p=s.indexOf(".");d=p<0?0:s.length-p-1;}
  else if(Math.abs(n)>=100)d=2;else if(Math.abs(n)>=1)d=4;else if(Math.abs(n)>=.01)d=5;else d=6;
  return n.toFixed(Math.min(8,d)).replace(/(\.\d*?[1-9])0+$|\.0+$/,"$1");
}
const usd=v=>`$${Math.abs(Number(v||0)).toFixed(2)}`;
const signedUsd=v=>`${Number(v||0)>=0?"+":"-"}$${Math.abs(Number(v||0)).toFixed(2)}`;

async function sendOnce(env,fingerprint,text,meta={}){
  const ctl=await kvGet(env,CONTROL_KEY,{}),seen=Array.isArray(ctl.tradeActionNotifications)?ctl.tradeActionNotifications:[];
  if(seen.some(x=>x?.fingerprint===fingerprint))return {sent:false,reason:"ALREADY_NOTIFIED",fingerprint};
  try{
    await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});
    ctl.tradeActionNotifications=[{fingerprint,at:iso(),...meta},...seen].slice(0,120);
    ctl.lastTradeActionNotifyError=null;await kvPut(env,CONTROL_KEY,ctl);return {sent:true,fingerprint};
  }catch(e){ctl.lastTradeActionNotifyError={at:iso(),fingerprint,error:String(e?.message||e),...meta};await kvPut(env,CONTROL_KEY,ctl);return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e)};}
}

async function notifyLiveEntry(env,out){
  const p=out?.plan;if(!out?.executed||out?.mode!=="LIVE"||!p?.orderId)return {sent:false,reason:"NO_NEW_LIVE_ENTRY"};
  const s=await kvGet(env,AUTO_KEY,{});
  if(String(s.lastTelegramOrderId||"")===String(p.orderId))return {sent:false,reason:"ALREADY_NOTIFIED"};
  const tick=Number(p.tickSize||p.filters?.tickSize||0),side=String(p.side||"").toLowerCase()==="buy"?"BUY":"SELL",icon=side==="BUY"?"🟢":"🔴";
  const text=[`${icon} ${p.symbol} ${side}`,`Entry ${compactPrice(p.entry,tick)}`,`SL ${compactPrice(p.sl,tick)} • -${usd(p.riskUsd)}`,`TP ${compactPrice(p.tp,tick)} • +${usd(p.rewardUsd)}`,`RR ${Number(p.rr||0).toFixed(2)} • ${Number(p.leverage||0)>0?`${Number(p.leverage)}x • `:""}AUTO LIVE`,`🛡️ SL/TP/Trailing đã bảo vệ`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n");
  try{
    await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});
    s.lastTelegramOrderId=String(p.orderId);s.lastTelegramEntryAt=iso();s.lastTelegramEntrySymbol=p.symbol;s.lastTelegramNotifyError=null;
    await kvPut(env,AUTO_KEY,s);return {sent:true,orderId:p.orderId};
  }catch(e){s.lastTelegramNotifyError={at:iso(),symbol:p.symbol,orderId:String(p.orderId),error:String(e?.message||e)};await kvPut(env,AUTO_KEY,s);return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e)};}
}

async function latestClosed(env,symbol,plan={}){
  try{const api=bybitV5(env),start=Math.max(dayStartMs(),Number(plan.createdAtMs||0)-60000),p=await api.closedPnl(start,now()),list=(p?.result?.list||[]).filter(x=>String(x.symbol||"")===String(symbol)).sort((a,b)=>eventTime(b)-eventTime(a));return list[0]||null;}catch{return null;}
}
function classifyClose(plan={},closed={}){
  const pnl=Number(closed?.closedPnl||0),exit=Number(closed?.avgExitPrice||0),entry=Number(plan.entry||0),tp=Number(plan.tp||0),sl=Number(plan.managedSl||plan.sl||0),tick=Number(plan.tickSize||plan.filters?.tickSize||0),tol=Math.max(tick*3,Math.abs(entry)*0.0008,1e-10),side=String(plan.side||"");
  if(plan.exitReason||plan.cutReason)return {kind:"SMART CUT",icon:"✂️"};
  if(exit>0&&tp>0&&Math.abs(exit-tp)<=tol)return {kind:"TP",icon:"🎯"};
  if(exit>0&&sl>0&&Math.abs(exit-sl)<=tol){if((side==="Buy"&&sl>=entry)||(side==="Sell"&&sl<=entry))return {kind:"BE / PROFIT STOP",icon:"🛡️"};return {kind:"SL",icon:"🛑"};}
  if(pnl>0)return {kind:"CLOSED PROFIT",icon:"✅"};if(pnl<0)return {kind:"CLOSED LOSS",icon:"🛑"};return {kind:"CLOSED",icon:"⚪"};
}

async function notifyLifecycleActions(env,out,prePlans={}){
  if(out?.mode!=="LIVE")return [];
  const sent=[];
  for(const x of out?.lifecycles||[]){
    const symbol=String(x?.symbol||""),plan=prePlans?.[symbol]||{};if(!symbol)continue;
    if(x.cutExecuted===true||x.verdict==="CUT"){const fp=`CUT:${symbol}:${x.orderId||x.reason||"manager"}`;sent.push(await sendOnce(env,fp,[`✂️ SMART CUT ${symbol}`,`Mark ${compactPrice(x.markPrice,plan.tickSize)} • R ${Number(x.r||0).toFixed(2)}`,`${x.reason||"MANAGER_CUT"}`,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol,action:"CUT"}));continue;}
    if(x.managed===true&&x.verdict==="TIGHTEN"){
      const phase=String(x.phase||"PROTECT"),label=phase==="BREAKEVEN"?"BE":phase==="PROFIT_LOCK"?"PROFIT LOCK":phase==="TRAIL"?"TRAILING":"SL UPDATE",icon=phase==="BREAKEVEN"?"🟰":phase==="PROFIT_LOCK"?"🔒":phase==="TRAIL"?"🧲":"🛡️",next=Number(x.nextSl||0),trail=Number(x.trailingStop||0),fp=`TIGHTEN:${symbol}:${phase}:${next}:${trail}`;
      sent.push(await sendOnce(env,fp,[`${icon} ${label} ${symbol}`,`SL ${compactPrice(x.previousSl,plan.tickSize)} → ${compactPrice(next,plan.tickSize)}`,trail>0?`Trailing ${compactPrice(trail,plan.tickSize)}`:null,`R ${Number(x.r||0).toFixed(2)} • ${BYBIT_AUTO_VERSION}`].filter(Boolean).join("\n"),{symbol,action:phase}));continue;
    }
    if(x.verdict==="CLOSED"){const c=await latestClosed(env,symbol,plan),cls=classifyClose(plan,c||{}),eid=String(c?.orderId||eventTime(c)||plan.orderId||"closed"),fp=`CLOSED:${symbol}:${eid}`;sent.push(await sendOnce(env,fp,[`${cls.icon} ${cls.kind} ${symbol}`,c?`PnL ${signedUsd(c.closedPnl)} • Exit ${compactPrice(c.avgExitPrice,plan.tickSize)}`:"Position đã đóng trên Bybit",`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{symbol,action:cls.kind}));continue;}
    if(x.verdict==="ERROR"){const fp=`ERROR:${symbol}:${x.reason}:${String(x.error||"").slice(0,80)}`;sent.push(await sendOnce(env,fp,[`⚠️ MANAGER ERROR ${symbol}`,`${x.reason||"UNKNOWN"}`,String(x.error||"").slice(0,140),`${BYBIT_AUTO_VERSION} • LIVE`].filter(Boolean).join("\n"),{symbol,action:"ERROR"}));}
  }
  return sent;
}

async function clearLegacyProfitTarget(env){const s=await kvGet(env,AUTO_KEY,{});if(s.profitTarget){s.lastRetiredProfitTarget={...s.profitTarget,retiredAt:iso(),retiredReason:"DATE_SCOPED_OVERRIDE_REMOVED_FROM_PRODUCTION"};delete s.profitTarget;await kvPut(env,AUTO_KEY,s);}}
async function isolateModeState(env,mode){
  const s=await kvGet(env,AUTO_KEY,{}),previous=String(s.executionMode||"").toUpperCase();
  if(mode==="LIVE"&&previous!=="LIVE"){
    const paperPlans=Object.fromEntries(Object.entries(s.openPlans||{}).filter(([,p])=>String(p?.mode||"").toUpperCase()==="PAPER"));
    s.openPlans=Object.fromEntries(Object.entries(s.openPlans||{}).filter(([,p])=>String(p?.mode||"").toUpperCase()==="LIVE"));
    s.lastTradeAt=0;s.lastFingerprint=null;s.trades=0;s.pauseUntil=0;s.lossStreak=0;s.executionMode="LIVE";
    s.lastModeTransition={at:iso(),from:previous||"UNKNOWN",to:"LIVE",discardedPaperPlans:Object.keys(paperPlans)};await kvPut(env,AUTO_KEY,s);
  }else if(mode==="PAPER"&&previous!=="PAPER"){s.executionMode="PAPER";s.lastModeTransition={at:iso(),from:previous||"UNKNOWN",to:"PAPER"};await kvPut(env,AUTO_KEY,s);}
  return s;
}
async function resolvePaperEquity(env){try{const api=bybitV5(env),wallet=await api.wallet(),acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};const equity=Number(acct.totalEquity||coin.equity||coin.walletBalance||0);return equity>0?equity:null;}catch{return null;}}
function scanTelemetry(scan={}){const b=scan?.best;return {scannedAt:Number(scan?.scannedAt||0)||null,universe:Number(scan?.universe?.count||0)||null,analyzed:Number(scan?.analyzed||0)||null,rawCandidates:Number(scan?.rawCandidates||0),qualified:Number(scan?.qualified||0),reason:scan?.reason||null,best:b?{symbol:b.symbol,side:b.side,score:b.score,threshold:b.adaptiveThreshold,rr:b.rr,regime:b.regime}:null,errors:Array.isArray(scan?.errors)?scan.errors.slice(0,5):[]};}

export async function recordBybitAutoSchedulerError(env,error){
  const ctl=await kvGet(env,CONTROL_KEY,{}),count=Number(ctl.consecutiveSchedulerErrors||0)+1,msg=String(error?.message||error||"UNKNOWN").slice(0,300),at=iso();
  ctl.consecutiveSchedulerErrors=count;ctl.lastSchedulerError={at,error:msg};ctl.lastCycleAt=at;ctl.lastCycleReason="SCHEDULER_EXCEPTION";ctl.lastCycleExecuted=false;
  await kvPut(env,CONTROL_KEY,ctl);
  if(count===1||count%10===0){const bucket=Math.floor(now()/3600000);await sendOnce(env,`BYBIT_SCHEDULER_ERROR:${bucket}`,[`⚠️ BYBIT AUTO SCHEDULER ERROR`,`Count ${count}`,msg,`${BYBIT_AUTO_VERSION} • LIVE`].join("\n"),{action:"SCHEDULER_ERROR"});}
  return {ok:false,reason:"SCHEDULER_EXCEPTION",error:msg,count};
}

export async function runBybitAutoControlled(env,opts={}){
  const mode=String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER",cfg=bybitAutoConfig(env),entrySpacingMs=cfg.execution.cooldownSec*1000;
  await isolateModeState(env,mode);await clearLegacyProfitTarget(env);
  const state=await getBybitAutoV1State(env),prePlans=structuredClone(state?.openPlans||{}),lastTradeAt=Number(state?.lastTradeAt||0),elapsed=now()-lastTradeAt;
  const spacingActive=lastTradeAt>0&&elapsed<entrySpacingMs,spacingReason=spacingActive?`ENTRY_SPACING_${cfg.execution.cooldownSec}S`:null;
  const entryBlockReason=spacingReason;
  const innerEnv=Object.create(env);
  let paperEquity=null;if(mode==="PAPER"){paperEquity=await resolvePaperEquity(env);if(paperEquity>0)innerEnv.BYBIT_STARTING_CAPITAL_USD=String(paperEquity);}
  const out=await runBybitAutoV1(innerEnv,{...opts,entryBlockReason});
  const telegramNotification=await notifyLiveEntry(env,out),lifecycleNotifications=await notifyLifecycleActions(env,out,prePlans),finalState=out?.state||state;
  const controller={executionMode:mode,entrySpacingSec:cfg.execution.cooldownSec,entryGateAuthority:"BYBIT_AUTO_CONFIG.execution.cooldownSec",entryBlockReason:out?.reason==="LOSS_STREAK_PAUSE"?"LOSS_STREAK_PAUSE":entryBlockReason,nextEntryAt:spacingActive?lastTradeAt+entrySpacingMs:null,entrySpacingRemainingMs:spacingActive?Math.max(0,entrySpacingMs-elapsed):0,lossStreakTrigger:3,lossPauseMinutes:30,unlimitedDailyEntries:true,managementAlwaysOn:true,allTradeActionsNotify:true,profitTarget:null,profitTargetPolicy:"NONE_CANONICAL_RISK_GATES_ONLY",pauseState:{pauseUntil:Number(finalState?.pauseUntil||0),lossStreak:Number(finalState?.lossStreak||0),lastLossPauseTriggerAt:Number(finalState?.lastLossPauseTriggerAt||0)||null},telegramNotification,lifecycleNotifications,runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN")};
  if(mode==="PAPER"){controller.equitySource=paperEquity>0?"BYBIT_LIVE_WALLET":"STATIC_FALLBACK";controller.equityUsd=paperEquity;}else{controller.equitySource="BYBIT_LIVE_WALLET";controller.equityUsd=Number(out?.equity||0)||null;}
  const oldCtl=await kvGet(env,CONTROL_KEY,{}),telemetry={...oldCtl,...controller,lastCycleAt:iso(),lastCycleReason:String(out?.reason||"UNKNOWN"),lastCycleExecuted:!!out?.executed,lastEntryBlockReason:controller.entryBlockReason||null,lastScan:scanTelemetry(out?.scan||{}),consecutiveSchedulerErrors:0,lastSchedulerError:null};
  await kvPut(env,CONTROL_KEY,telemetry);
  return {...out,controller};
}
