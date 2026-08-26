import {scanBybitAuto} from "./bybit-scalp-engine.js";
import {getBybitAutoV1State} from "./bybit-auto-v1.js";
import {runBybitAutoControlled} from "./bybit-auto-controller.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {buildBybitShadowChallenger} from "./bybit-evolution-engine.js";
import {probeBybitAiBridge} from "./bybit-ai-scalp-gate.js";
import {bybitCredentials,bybitExecutionMode,bybitAutoConfig} from "./bybit-auto-config.js";
import {bybitV5} from "./bybit-v5-client.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const on=v=>String(v||"").toLowerCase()==="true";
const CONTROL_KEY="bybit:auto:v1:controller";
async function kvGet(env,key,def={}){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
function authState(req,env){const want=String(env.GPT_5AI_ACTION_KEY||"");const raw=String(req.headers.get("x-action-key")||req.headers.get("authorization")||"");const got=raw.replace(/^Bearer\s+/i,"");return {ok:!!want&&got===want,actionKeyPresent:!!want,requestKeyPresent:!!got};}
function unauthorized(req,env){const a=authState(req,env);return json({ok:false,error:"unauthorized",authDiagnostics:{actionKeyPresent:a.actionKeyPresent,requestKeyPresent:a.requestKeyPresent}},401);}
async function runtimePreflight(env){
  const mode=bybitExecutionMode(env),creds=bybitCredentials(env),liveAck=on(env.BYBIT_AUTO_LIVE_ACK),scheduled=on(env.BYBIT_AUTO_ENABLED),state=await getBybitAutoV1State(env),plans=Object.values(state?.openPlans||{}),paperPlans=plans.filter(p=>String(p?.mode||"").toUpperCase()==="PAPER"),livePlans=plans.filter(p=>String(p?.mode||"").toUpperCase()==="LIVE"),runtimeRevision=String(env.RUNTIME_REVISION||"UNKNOWN");
  let account=null,positions=[],openOrdersCount=null,accountError=null;
  try{const api=bybitV5(env),[w,p,o]=await Promise.all([api.wallet(),api.positions(),api.openOrders()]),acct=w?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};account={totalEquity:Number(acct.totalEquity||coin.equity||0),walletBalance:Number(acct.totalWalletBalance||coin.walletBalance||0),availableBalance:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0)};positions=(p?.result?.list||[]).filter(x=>Number(x.size||0)>0).map(x=>({symbol:x.symbol,side:x.side,size:Number(x.size),avgPrice:Number(x.avgPrice||0),stopLoss:Number(x.stopLoss||0),takeProfit:Number(x.takeProfit||0),positionValue:Number(x.positionValue||0)}));openOrdersCount=(o?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus))).length;}catch(e){accountError=String(e?.message||e);}
  let aiBridge;try{aiBridge=await probeBybitAiBridge(env);}catch(e){aiBridge={ok:false,error:String(e?.message||e)};}
  const blockers=[];
  if(mode!=="LIVE")blockers.push("MODE_NOT_LIVE");
  if(!liveAck)blockers.push("LIVE_ACK_MISSING");
  if(!scheduled)blockers.push("SCHEDULER_DISABLED");
  if(!(creds.apiKey&&creds.apiSecret))blockers.push("BYBIT_CREDENTIALS_MISSING");
  if(!account||!(account.totalEquity>0))blockers.push("LIVE_ACCOUNT_UNAVAILABLE");
  if(!aiBridge?.ok)blockers.push("AI_BRIDGE_NOT_READY");
  if(paperPlans.length)blockers.push("PAPER_STATE_PENDING_ISOLATION");
  const tracked=new Set(livePlans.map(p=>String(p?.symbol||""))),untracked=positions.filter(p=>!tracked.has(String(p.symbol||"")));
  if(untracked.length)blockers.push("UNTRACKED_LIVE_POSITION");
  return {ok:blockers.length===0,exchange:"BYBIT",runtimeRevision,mode,execution:{liveAck,scheduled,ready:blockers.length===0},credentialSource:creds.source,account,accountError,state:{executionMode:String(state?.executionMode||"UNKNOWN"),trades:Number(state?.trades||0),realizedUsd:Number(state?.realizedUsd||0),lastTradeAt:Number(state?.lastTradeAt||0),paperPlanSymbols:paperPlans.map(p=>p.symbol),livePlanSymbols:livePlans.map(p=>p.symbol),lastModeTransition:state?.lastModeTransition||null},live:{positions,openOrdersCount,untrackedSymbols:untracked.map(x=>x.symbol)},aiBridge,blockers,checkedAt:new Date().toISOString()};
}
function qualityWaitReason(reason=""){
  const r=String(reason||"");
  if(!r||r==="UNKNOWN")return false;
  return r==="NO_SETUP"||r.startsWith("AI_")||r.includes("SCALP_GATE")||r.includes("REVALIDATION")||r.includes("SPREAD")||r.includes("CHASE")||r.includes("CORRELATION")||r.includes("SAME_DIRECTION")||r.includes("SYMBOL_ALREADY_OPEN")||r.includes("PLAN_ALREADY_TRACKED")||r.includes("STRUCTURE_")||r.includes("RR_")||r.includes("EFFECTIVE_RISK_TOO_SMALL");
}
async function entryHealth(env){
  const [preflight,ctl,state]=await Promise.all([runtimePreflight(env),kvGet(env,CONTROL_KEY,{}),getBybitAutoV1State(env)]),cfg=bybitAutoConfig(env);
  const reason=String(ctl?.lastCycleReason||"UNKNOWN"),spacingMs=Math.max(0,Number(ctl?.entrySpacingRemainingMs||0)),pauseUntil=Number(state?.pauseUntil||0),paused=pauseUntil>Date.now();
  const operationalBlockers=[...preflight.blockers];
  if(spacingMs>0)operationalBlockers.push(`ENTRY_SPACING_${Math.ceil(spacingMs/1000)}S`);
  if(paused)operationalBlockers.push("LOSS_STREAK_PAUSE");
  const hardLastReason=!qualityWaitReason(reason)&&reason!=="UNKNOWN"&&reason!=="PAPER_ORDER_ACCEPTED_AFTER_AI"&&reason!=="LIVE_ORDER_PROTECTED"&&reason!=="POSITION_CUT_BY_MANAGER"?reason:null;
  const entryReady=preflight.ok&&spacingMs===0&&!paused&&!hardLastReason;
  return {ok:true,exchange:"BYBIT",version:cfg?undefined:undefined,runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),entryReady,status:entryReady?"ENTRY_READY":qualityWaitReason(reason)&&preflight.ok&&spacingMs===0&&!paused?"WAITING_FOR_QUALITY_SETUP":"ENTRY_BLOCKED",lastCycleReason:reason,qualityWait:qualityWaitReason(reason),operationalBlockers,hardLastReason,entrySpacingRemainingMs:spacingMs,pauseUntil:paused?pauseUntil:null,limits:{scanEverySec:cfg.scanEverySec,cooldownSec:cfg.execution.cooldownSec,maxOpenPositions:cfg.maxOpenPositions,maxSameDirectionPositions:cfg.risk.maxSameDirectionPositions,maxRiskPctOfEquity:cfg.risk.maxRiskPctOfEquity,maxTotalOpenRiskPct:cfg.risk.maxTotalOpenRiskPct,maxMarginPerPositionPct:cfg.risk.maxMarginPerPositionPct,maxPortfolioMarginPct:cfg.risk.maxPortfolioMarginPct,minFreeReservePct:cfg.risk.minFreeReservePct,minRR:cfg.risk.minRR},preflight,checkedAt:new Date().toISOString()};
}
export async function handleBybitControlApi(req,env){const u=new URL(req.url);
if(u.pathname==="/bybit/auth/health"&&req.method==="GET"){const a=authState(req,env);return json({ok:true,exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),authDiagnostics:{actionKeyPresent:a.actionKeyPresent,requestKeyPresent:a.requestKeyPresent,authorized:a.ok}});}
if(u.pathname==="/bybit/entry-health"&&req.method==="GET"){try{return json(await entryHealth(env));}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_ENTRY_HEALTH_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/runtime/preflight"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await runtimePreflight(env);return json(out,out.ok?200:503);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_RUNTIME_PREFLIGHT_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/ai/health"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await probeBybitAiBridge(env);return json({exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),aiBridge:out},out.ok?200:503);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AI_HEALTH_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/scan"&&req.method==="GET"){try{return json({ok:true,exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),...(await scanBybitAuto(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_SCAN_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/state"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);return json({ok:true,exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),state:await getBybitAutoV1State(env)});}
if(u.pathname==="/bybit/learning/state"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);return json({ok:true,exchange:"BYBIT",learning:await getBybitLearningState(env)});}
if(u.pathname==="/bybit/evolution/build"&&req.method==="POST"){if(!authState(req,env).ok)return unauthorized(req,env);try{return json({exchange:"BYBIT",...(await buildBybitShadowChallenger(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_EVOLUTION_BUILD_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/run"&&req.method==="POST"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await runBybitAutoControlled(env);return json({exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),...out},out.ok===false?502:200);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AUTO_RUN_FAILED",error:String(e?.message||e)},502);}}
return null;}
