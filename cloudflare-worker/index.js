import autoHub from "./bybit-auto-hub.js";
import {handleBybitReadonlyHealth} from "./bybit-readonly-health.js";
import {handleBybitControlApi} from "./bybit-control-plane.js";
import {runBybitAutoControlled,recordBybitAutoSchedulerError} from "./bybit-auto-controller.js";
import {BYBIT_AUTO_VERSION,bybitExecutionMode} from "./bybit-auto-config.js";
import {BYBIT_RUNTIME_CONTRACT,BYBIT_EXECUTION_AUTHORITY,TELEGRAM_HUB_ID,BYBIT_HEALTH_ROUTE} from "./bybit-runtime-contract.js";

const VERSION=BYBIT_AUTO_VERSION;
const SERVICE="BTCUSDT Bybit Hyperscale";
const envBool=v=>String(v||"").toLowerCase()==="true";
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const RETIRED_PREFIXES=["/v11/","/forex/","/meme-auto/","/binance/","/hyro/"];

export default {
  async fetch(req,env,ctx){
    const bybitHealth=await handleBybitReadonlyHealth(req,env);if(bybitHealth)return bybitHealth;
    const bybitControl=await handleBybitControlApi(req,env);if(bybitControl)return bybitControl;
    const hub=await autoHub.fetch(req,env,ctx);if(hub)return hub;
    const url=new URL(req.url);
    if(url.pathname==="/runtime/contract")return json({ok:true,...BYBIT_RUNTIME_CONTRACT,runtimeRevision:String(env.RUNTIME_REVISION||"")});
    if(url.pathname==="/status")return json({ok:true,version:VERSION,service:SERVICE,executionAuthority:BYBIT_EXECUTION_AUTHORITY,runtimeContract:BYBIT_RUNTIME_CONTRACT,telegramHub:TELEGRAM_HUB_ID,legacyBotsDisabled:true,bybit:{symbol:"BTCUSDT",market:"LINEAR_PERPETUAL",mode:bybitExecutionMode(env),enabled:envBool(env.BYBIT_AUTO_ENABLED),requestedLive:envBool(env.BYBIT_AUTO_LIVE),btcLiveAck:envBool(env.BYBIT_BTC_LIVE_ACK),readonlyHealth:BYBIT_HEALTH_ROUTE,strategyAuthority:"MARKET_STRUCTURE_ORDERFLOW_DERIVATIVES_MICROSTRUCTURE",hardDailyTradeQuota:false,martingale:false,addToLoser:false,winnerPyramiding:true}});
    if(RETIRED_PREFIXES.some(p=>url.pathname.startsWith(p))||["/mcp","/mcp/health","/gpt-5ai/action","/internal/multi-ai/review","/bybit/ai/latest-review"].includes(url.pathname))return json({ok:false,error:"RETIRED_OLD_BOT_ROUTE",replacement:"BTCUSDT_BYBIT_HYPERSCALE",authority:BYBIT_EXECUTION_AUTHORITY},410);
    return json({ok:false,error:"BTC_HUB_ENDPOINT_NOT_FOUND",runtimeContract:"/runtime/contract"},404);
  },
  async scheduled(event,env,ctx){if(envBool(env.BYBIT_AUTO_ENABLED))ctx.waitUntil(Promise.resolve(runBybitAutoControlled(env)).catch(e=>recordBybitAutoSchedulerError(env,e).catch(()=>null)));}
};
