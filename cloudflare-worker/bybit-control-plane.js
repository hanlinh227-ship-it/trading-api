import {scanBybitAuto} from "./bybit-scalp-engine.js";
import {getBybitAutoV1State} from "./bybit-auto-v1.js";
import {runBybitAutoControlled} from "./bybit-auto-controller.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {buildBybitShadowChallenger} from "./bybit-evolution-engine.js";
import {probeBybitAiBridge} from "./bybit-ai-scalp-gate.js";
import {bybitCredentials,bybitExecutionMode} from "./bybit-auto-config.js";
import {bybitV5} from "./bybit-v5-client.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const on=v=>String(v||"").toLowerCase()==="true";
function authState(req,env){const want=String(env.GPT_5AI_ACTION_KEY||"");const raw=String(req.headers.get("x-action-key")||req.headers.get("authorization")||"");const got=raw.replace(/^Bearer\s+/i,"");return {ok:!!want&&got===want,actionKeyPresent:!!want,requestKeyPresent:!!got};}
function unauthorized(req,env){const a=authState(req,env);return json({ok:false,error:"unauthorized",authDiagnostics:{actionKeyPresent:a.actionKeyPresent,requestKeyPresent:a.requestKeyPresent}},401);}
async function runtimePreflight(env){
  const mode=bybitExecutionMode(env),creds=bybitCredentials(env),liveAck=on(env.BYBIT_AUTO_LIVE_ACK),scheduled=on(env.BYBIT_AUTO_ENABLED),state=await getBybitAutoV1State(env),plans=Object.values(state?.openPlans||{}),paperPlans=plans.filter(p=>String(p?.mode||"").toUpperCase()==="PAPER"),livePlans=plans.filter(p=>String(p?.mode||"").toUpperCase()==="LIVE"),runtimeRevision=String(env.RUNTIME_REVISION||"UNKNOWN");
  let account=null,positions=[],openOrdersCount=null,accountError=null;
  try{const api=bybitV5(env),[w,p,o]=await Promise.all([api.wallet(),api.positions(),api.openOrders()]),acct=w?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};account={totalEquity:Number(acct.totalEquity||coin.equity||0),walletBalance:Number(acct.totalWalletBalance||coin.walletBalance||0),availableBalance:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0)};positions=(p?.result?.list||[]).filter(x=>Number(x.size||0)>0).map(x=>({symbol:x.symbol,side:x.side,size:Number(x.size),stopLoss:Number(x.stopLoss||0),takeProfit:Number(x.takeProfit||0)}));openOrdersCount=(o?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus))).length;}catch(e){accountError=String(e?.message||e);}
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
export async function handleBybitControlApi(req,env){const u=new URL(req.url);
if(u.pathname==="/bybit/auth/health"&&req.method==="GET"){const a=authState(req,env);return json({ok:true,exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),authDiagnostics:{actionKeyPresent:a.actionKeyPresent,requestKeyPresent:a.requestKeyPresent,authorized:a.ok}});}
if(u.pathname==="/bybit/runtime/preflight"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await runtimePreflight(env);return json(out,out.ok?200:503);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_RUNTIME_PREFLIGHT_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/ai/health"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await probeBybitAiBridge(env);return json({exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),aiBridge:out},out.ok?200:503);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AI_HEALTH_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/scan"&&req.method==="GET"){try{return json({ok:true,exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),...(await scanBybitAuto(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_SCAN_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/state"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);return json({ok:true,exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),state:await getBybitAutoV1State(env)});}
if(u.pathname==="/bybit/learning/state"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);return json({ok:true,exchange:"BYBIT",learning:await getBybitLearningState(env)});}
if(u.pathname==="/bybit/evolution/build"&&req.method==="POST"){if(!authState(req,env).ok)return unauthorized(req,env);try{return json({exchange:"BYBIT",...(await buildBybitShadowChallenger(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_EVOLUTION_BUILD_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/run"&&req.method==="POST"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await runBybitAutoControlled(env);return json({exchange:"BYBIT",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),...out},out.ok===false?502:200);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AUTO_RUN_FAILED",error:String(e?.message||e)},502);}}
return null;}
