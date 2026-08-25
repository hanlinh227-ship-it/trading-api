import {runBybitAutoV1,getBybitAutoV1State} from "./bybit-auto-v1.js";
import {bybitV5} from "./bybit-v5-client.js";
import {telegramApiRequest} from "./providers/telegram-client.js";

const AUTO_KEY="bybit:auto:v1:state";
const CONTROL_KEY="bybit:auto:v1:controller";
const ENTRY_SPACING_MS=3*60*1000;
const LOSS_PAUSE_MS=30*60*1000;
const LOSS_STREAK_TRIGGER=3;
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

const LIVE_TARGET_SPEC={
  id:"2026-08-25T06:01+07:+100USD",
  day:"2026-08-25",
  targetUsd:100,
  baselineRealizedUsd:0.9529275799999999,
  startAt:"2026-08-25T06:01:00+07:00",
  endAt:"2026-08-25T23:59:59.999+07:00",
  policy:"STOP_NEW_ENTRIES_ONLY_KEEP_MANAGING_OPEN_POSITIONS"
};

async function notifyLiveEntry(env,out){
  const p=out?.plan;if(!out?.executed||out?.mode!=="LIVE"||!p?.orderId)return {sent:false,reason:"NO_NEW_LIVE_ENTRY"};
  const s=await kvGet(env,AUTO_KEY,{});
  if(String(s.lastTelegramOrderId||"")===String(p.orderId))return {sent:false,reason:"ALREADY_NOTIFIED"};
  const tick=Number(p.tickSize||p.filters?.tickSize||0),side=String(p.side||"").toLowerCase()==="buy"?"BUY":"SELL",icon=side==="BUY"?"🟢":"🔴";
  const text=[
    `${icon} ${p.symbol} ${side}`,
    `Entry ${compactPrice(p.entry,tick)}`,
    `SL ${compactPrice(p.sl,tick)} • -${usd(p.riskUsd)}`,
    `TP ${compactPrice(p.tp,tick)} • +${usd(p.rewardUsd)}`,
    `RR ${Number(p.rr||0).toFixed(2)} • ${Number(p.leverage||0)>0?`${Number(p.leverage)}x • `:""}AUTO LIVE`
  ].join("\n");
  try{
    await telegramApiRequest(env,"sendMessage",{chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true});
    s.lastTelegramOrderId=String(p.orderId);s.lastTelegramEntryAt=iso();s.lastTelegramEntrySymbol=p.symbol;s.lastTelegramNotifyError=null;
    await kvPut(env,AUTO_KEY,s);return {sent:true,orderId:p.orderId};
  }catch(e){
    s.lastTelegramNotifyError={at:iso(),symbol:p.symbol,orderId:String(p.orderId),error:String(e?.message||e)};
    await kvPut(env,AUTO_KEY,s);return {sent:false,reason:"TELEGRAM_SEND_FAILED",error:String(e?.message||e)};
  }
}

async function ensureLiveProfitTarget(env,mode){
  if(mode!=="LIVE")return null;
  const s=await kvGet(env,AUTO_KEY,{}),spec=LIVE_TARGET_SPEC;
  if(day()!==spec.day)return s.profitTarget||null;
  const existing=s.profitTarget;
  if(existing?.id!==spec.id){
    s.profitTarget={...spec,status:"ACTIVE",targetPnlUsd:Number(s.realizedUsd||0)-spec.baselineRealizedUsd,createdAt:iso(),updatedAt:iso(),baselineSource:"LIVE_RUNTIME_SNAPSHOT"};
    await kvPut(env,AUTO_KEY,s);
    return s.profitTarget;
  }
  return existing;
}

async function syncLiveProfitTarget(env){
  const s=await kvGet(env,AUTO_KEY,{}),t=s.profitTarget;
  if(!t||t.id!==LIVE_TARGET_SPEC.id)return t||null;
  const current=Number(s.realizedUsd||0)-Number(t.baselineRealizedUsd||0),endMs=Date.parse(t.endAt),startMs=Date.parse(t.startAt);
  t.targetPnlUsd=current;
  t.remainingUsd=Math.max(0,Number(t.targetUsd||0)-current);
  t.updatedAt=iso();
  if(current>=Number(t.targetUsd||0)){if(t.status!=="REACHED")t.reachedAt=iso();t.status="REACHED";}
  else if(now()>endMs){t.status="EXPIRED";}
  else if(now()>=startMs){t.status="ACTIVE";}
  s.profitTarget=t;
  await kvPut(env,AUTO_KEY,s);
  return t;
}

async function isolateModeState(env,mode){
  const s=await kvGet(env,AUTO_KEY,{}),previous=String(s.executionMode||"").toUpperCase();
  if(mode==="LIVE"&&previous!=="LIVE"){
    const paperPlans=Object.fromEntries(Object.entries(s.openPlans||{}).filter(([,p])=>String(p?.mode||"").toUpperCase()==="PAPER"));
    s.openPlans=Object.fromEntries(Object.entries(s.openPlans||{}).filter(([,p])=>String(p?.mode||"").toUpperCase()==="LIVE"));
    s.lastTradeAt=0;
    s.lastFingerprint=null;
    s.trades=0;
    s.pauseUntil=0;
    s.lossStreak=0;
    s.executionMode="LIVE";
    s.lastModeTransition={at:iso(),from:previous||"UNKNOWN",to:"LIVE",discardedPaperPlans:Object.keys(paperPlans)};
    await kvPut(env,AUTO_KEY,s);
  }else if(mode==="PAPER"&&previous!=="PAPER"){
    s.executionMode="PAPER";
    s.lastModeTransition={at:iso(),from:previous||"UNKNOWN",to:"PAPER"};
    await kvPut(env,AUTO_KEY,s);
  }
  return s;
}

async function lossPauseGate(env){
  const ctl=await kvGet(env,CONTROL_KEY,{day:day(),pauseUntil:0,lastPauseTriggerAt:0});
  if(ctl.day!==day()){ctl.day=day();ctl.pauseUntil=0;ctl.lastPauseTriggerAt=0;}
  if(Number(ctl.pauseUntil||0)>now())return {ok:false,reason:"LOSS_STREAK_PAUSE",pauseUntil:ctl.pauseUntil,remainingMs:ctl.pauseUntil-now(),controller:ctl};

  const mode=String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER";
  if(mode!=="LIVE"){ctl.pauseUntil=0;await kvPut(env,CONTROL_KEY,ctl);return {ok:true,controller:ctl};}

  const api=bybitV5(env),p=await api.closedPnl(dayStartMs(),now()),list=[...(p?.result?.list||[])].sort((a,b)=>eventTime(b)-eventTime(a));
  let streak=0,newestLossAt=0;
  for(const x of list){
    const t=eventTime(x);
    if(!(t>Number(ctl.lastPauseTriggerAt||0)))continue;
    const pnl=Number(x.closedPnl||0);
    if(pnl<0){streak++;if(!newestLossAt)newestLossAt=t;}
    else break;
  }
  ctl.currentLossStreak=streak;
  ctl.checkedAt=iso();
  if(streak>=LOSS_STREAK_TRIGGER&&newestLossAt>Number(ctl.lastPauseTriggerAt||0)){
    ctl.pauseUntil=now()+LOSS_PAUSE_MS;
    ctl.lastPauseTriggerAt=newestLossAt;
    ctl.lastPauseReason="THREE_CONSECUTIVE_LOSSES";
    await kvPut(env,CONTROL_KEY,ctl);
    return {ok:false,reason:"LOSS_STREAK_PAUSE",pauseUntil:ctl.pauseUntil,remainingMs:LOSS_PAUSE_MS,lossStreak:streak,controller:ctl};
  }
  ctl.pauseUntil=0;await kvPut(env,CONTROL_KEY,ctl);return {ok:true,lossStreak:streak,controller:ctl};
}

async function clearLegacyPause(env){
  const s=await kvGet(env,AUTO_KEY,{});
  if(Number(s.pauseUntil||0)>0||Number(s.lossStreak||0)>0){s.pauseUntil=0;s.lossStreak=0;await kvPut(env,AUTO_KEY,s);}
}

async function resolvePaperEquity(env){
  try{
    const api=bybitV5(env),wallet=await api.wallet(),acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};
    const equity=Number(acct.totalEquity||coin.equity||coin.walletBalance||0);
    return equity>0?equity:null;
  }catch{return null;}
}

export async function runBybitAutoControlled(env,opts={}){
  const mode=String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER";
  await isolateModeState(env,mode);
  await ensureLiveProfitTarget(env,mode);
  const state=await getBybitAutoV1State(env),lastTradeAt=Number(state?.lastTradeAt||0),elapsed=now()-lastTradeAt;
  const spacingActive=lastTradeAt>0&&elapsed<ENTRY_SPACING_MS,spacingReason=spacingActive?"ENTRY_SPACING_3M":null;

  let pause;
  try{pause=await lossPauseGate(env);}catch(e){pause={ok:false,reason:"LOSS_STREAK_CHECK_FAILED",error:String(e?.message||e),controller:null};}
  if(pause.ok)await clearLegacyPause(env);
  const entryBlockReason=!pause.ok?pause.reason:spacingReason;

  const innerEnv=Object.create(env);
  innerEnv.BYBIT_MAX_LOSS_STREAK_INTERNAL="1000000000";
  innerEnv.BYBIT_LOSS_PAUSE_MINUTES_INTERNAL="30";
  innerEnv.BYBIT_ENTRY_COOLDOWN_SEC="180";

  let paperEquity=null;
  if(mode==="PAPER"){
    paperEquity=await resolvePaperEquity(env);
    if(paperEquity>0)innerEnv.BYBIT_STARTING_CAPITAL_USD=String(paperEquity);
  }

  const out=await runBybitAutoV1(innerEnv,{...opts,entryBlockReason});
  const telegramNotification=await notifyLiveEntry(env,out);
  const profitTarget=mode==="LIVE"?await syncLiveProfitTarget(env):null;
  const controller={
    executionMode:mode,
    entrySpacingSec:180,
    entryBlockReason,
    nextEntryAt:spacingActive?lastTradeAt+ENTRY_SPACING_MS:null,
    entrySpacingRemainingMs:spacingActive?ENTRY_SPACING_MS-elapsed:0,
    lossStreakTrigger:3,
    lossPauseMinutes:30,
    unlimitedDailyEntries:true,
    managementAlwaysOn:true,
    pauseState:pause.controller,
    pauseError:pause.error||null,
    profitTarget,
    telegramNotification,
    runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN")
  };
  if(mode==="PAPER"){
    controller.equitySource=paperEquity>0?"BYBIT_LIVE_WALLET":"STATIC_FALLBACK";
    controller.equityUsd=paperEquity;
  }else{
    controller.equitySource="BYBIT_LIVE_WALLET";
    controller.equityUsd=Number(out?.equity||0)||null;
  }
  return {...out,controller};
}
