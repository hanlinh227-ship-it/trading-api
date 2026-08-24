import {scanBybitAuto} from "./bybit-scalp-engine.js";
import {getBybitAutoV1State} from "./bybit-auto-v1.js";
import {runBybitAutoControlled} from "./bybit-auto-controller.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {buildBybitShadowChallenger} from "./bybit-evolution-engine.js";
import {probeBybitAiBridge} from "./bybit-ai-scalp-gate.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
function authState(req,env){const want=String(env.GPT_5AI_ACTION_KEY||"");const raw=String(req.headers.get("x-action-key")||req.headers.get("authorization")||"");const got=raw.replace(/^Bearer\s+/i,"");return {ok:!!want&&got===want,actionKeyPresent:!!want,requestKeyPresent:!!got};}
function unauthorized(req,env){const a=authState(req,env);return json({ok:false,error:"unauthorized",authDiagnostics:{actionKeyPresent:a.actionKeyPresent,requestKeyPresent:a.requestKeyPresent}},401);}
export async function handleBybitControlApi(req,env){const u=new URL(req.url);
if(u.pathname==="/bybit/auth/health"&&req.method==="GET"){const a=authState(req,env);return json({ok:true,exchange:"BYBIT",authDiagnostics:{actionKeyPresent:a.actionKeyPresent,requestKeyPresent:a.requestKeyPresent,authorized:a.ok}});}
if(u.pathname==="/bybit/ai/health"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await probeBybitAiBridge(env);return json({exchange:"BYBIT",aiBridge:out},out.ok?200:503);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AI_HEALTH_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/scan"&&req.method==="GET"){try{return json({ok:true,exchange:"BYBIT",...(await scanBybitAuto(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_SCAN_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/state"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);return json({ok:true,exchange:"BYBIT",state:await getBybitAutoV1State(env)});}
if(u.pathname==="/bybit/learning/state"&&req.method==="GET"){if(!authState(req,env).ok)return unauthorized(req,env);return json({ok:true,exchange:"BYBIT",learning:await getBybitLearningState(env)});}
if(u.pathname==="/bybit/evolution/build"&&req.method==="POST"){if(!authState(req,env).ok)return unauthorized(req,env);try{return json({exchange:"BYBIT",...(await buildBybitShadowChallenger(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_EVOLUTION_BUILD_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/run"&&req.method==="POST"){if(!authState(req,env).ok)return unauthorized(req,env);try{const out=await runBybitAutoControlled(env);return json({exchange:"BYBIT",...out},out.ok===false?502:200);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AUTO_RUN_FAILED",error:String(e?.message||e)},502);}}
return null;}
