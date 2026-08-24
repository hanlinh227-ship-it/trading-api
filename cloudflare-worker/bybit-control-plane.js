import {scanBybitAuto} from "./bybit-scalp-engine.js";
import {runBybitAutoV1,getBybitAutoV1State} from "./bybit-auto-v1.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {buildBybitShadowChallenger} from "./bybit-evolution-engine.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
function authorized(req,env){const want=String(env.GPT_5AI_ACTION_KEY||"");if(!want)return false;const got=String(req.headers.get("x-action-key")||req.headers.get("authorization")||"").replace(/^Bearer\s+/i,"");return got===want;}
export async function handleBybitControlApi(req,env){const u=new URL(req.url);
if(u.pathname==="/bybit/scan"&&req.method==="GET"){try{return json({ok:true,exchange:"BYBIT",...(await scanBybitAuto(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_SCAN_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/state"&&req.method==="GET"){if(!authorized(req,env))return json({ok:false,error:"unauthorized"},401);return json({ok:true,exchange:"BYBIT",state:await getBybitAutoV1State(env)});}
if(u.pathname==="/bybit/learning/state"&&req.method==="GET"){if(!authorized(req,env))return json({ok:false,error:"unauthorized"},401);return json({ok:true,exchange:"BYBIT",learning:await getBybitLearningState(env)});}
if(u.pathname==="/bybit/evolution/build"&&req.method==="POST"){if(!authorized(req,env))return json({ok:false,error:"unauthorized"},401);try{return json({exchange:"BYBIT",...(await buildBybitShadowChallenger(env))});}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_EVOLUTION_BUILD_FAILED",error:String(e?.message||e)},502);}}
if(u.pathname==="/bybit/auto/run"&&req.method==="POST"){if(!authorized(req,env))return json({ok:false,error:"unauthorized"},401);try{const out=await runBybitAutoV1(env);return json({exchange:"BYBIT",...out},out.ok===false?502:200);}catch(e){return json({ok:false,exchange:"BYBIT",reason:"BYBIT_AUTO_RUN_FAILED",error:String(e?.message||e)},502);}}
return null;}
