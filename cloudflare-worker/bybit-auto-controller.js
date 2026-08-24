import {runBybitAutoV1,getBybitAutoV1State} from "./bybit-auto-v1.js";
import {bybitV5} from "./bybit-v5-client.js";

const AUTO_KEY="bybit:auto:v1:state";
const CONTROL_KEY="bybit:auto:v1:controller";
const ENTRY_SPACING_MS=5*60*1000;
const LOSS_PAUSE_MS=30*60*1000;
const LOSS_STREAK_TRIGGER=3;
const now=()=>Date.now();
const iso=()=>new Date().toISOString();
function day(){return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Bangkok",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());}
function dayStartMs(){return Date.parse(`${day()}T00:00:00+07:00`);}
async function kvGet(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function kvPut(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
function eventTime(x){return Number(x?.updatedTime||x?.createdTime||0);}

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
  const state=await getBybitAutoV1State(env),lastTradeAt=Number(state?.lastTradeAt||0),elapsed=now()-lastTradeAt;
  if(lastTradeAt>0&&elapsed<ENTRY_SPACING_MS)return {ok:true,executed:false,mode:String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER",reason:"ENTRY_SPACING_5M",nextEntryAt:lastTradeAt+ENTRY_SPACING_MS,remainingMs:ENTRY_SPACING_MS-elapsed,state};

  let pause;
  try{pause=await lossPauseGate(env);}catch(e){return {ok:true,executed:false,reason:"LOSS_STREAK_CHECK_FAILED",error:String(e?.message||e),state};}
  if(!pause.ok)return {ok:true,executed:false,mode:String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER",...pause,state};

  await clearLegacyPause(env);
  const innerEnv=Object.create(env);
  innerEnv.BYBIT_MAX_LOSS_STREAK_INTERNAL="1000000000";
  innerEnv.BYBIT_LOSS_PAUSE_MINUTES_INTERNAL="30";
  innerEnv.BYBIT_ENTRY_COOLDOWN_SEC="300";

  const mode=String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"?"LIVE":"PAPER";
  let paperEquity=null;
  if(mode==="PAPER"){
    paperEquity=await resolvePaperEquity(env);
    if(paperEquity>0)innerEnv.BYBIT_STARTING_CAPITAL_USD=String(paperEquity);
  }

  const out=await runBybitAutoV1(innerEnv,opts);
  return {...out,controller:{entrySpacingSec:300,lossStreakTrigger:3,lossPauseMinutes:30,unlimitedDailyEntries:true,pauseState:pause.controller,paperEquitySource:paperEquity>0?"BYBIT_LIVE_WALLET":"STATIC_FALLBACK",paperEquityUsd:paperEquity}};
}
