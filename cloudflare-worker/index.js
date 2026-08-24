import signalHub from "./hub-v11.js";
import {handleMultiAiControl} from "./multi-ai-control-plane.js";
import {handleChatGptMcp} from "./chatgpt-mcp.js";
import {handleGpt5AiAction} from "./gpt-5ai-action.js";
import {handleBybitReadonlyHealth} from "./bybit-readonly-health.js";
import {handleBybitControlApi} from "./bybit-control-plane.js";
import {runBybitAutoV1} from "./bybit-auto-v1.js";

const VERSION="V11";
const SERVICE="Trading Unified Hub • Signal V11 + Separate Bybit Auto";
const envBool=v=>String(v||"").toLowerCase()==="true";

export default {
  async fetch(req,env,ctx){
    const bybitHealth=await handleBybitReadonlyHealth(req,env);
    if(bybitHealth)return bybitHealth;

    const bybitControl=await handleBybitControlApi(req,env);
    if(bybitControl)return bybitControl;

    const mcp=await handleChatGptMcp(req,env);
    if(mcp)return mcp;

    const gpt5ai=await handleGpt5AiAction(req,env);
    if(gpt5ai)return gpt5ai;

    const multi=await handleMultiAiControl(req,env);
    if(multi)return multi;

    const r=await signalHub.fetch(req,env,ctx);
    const url=new URL(req.url);
    if(url.pathname!=="/status")return r;

    let body;
    try{body=await r.clone().json();}catch{return r;}

    return new Response(JSON.stringify({
      ...body,
      version:VERSION,
      service:SERVICE,
      signalOnlySourceOfTruth:"V11",
      bybitAutoProjectSeparate:true,
      bybitPrimaryExecution:true,
      bybitReadonlyHealth:"/bybit/health",
      bybitScan:"/bybit/scan",
      bybitAutoState:"/bybit/auto/state",
      bybitAutoRun:"/bybit/auto/run",
      bybitScheduledEnabled:envBool(env.BYBIT_AUTO_ENABLED),
      binanceAutoProductionRoute:false,
      multiAiGateway:"VPC_OIDC_CONTROL_PLANE",
      chatgptMcp:"/mcp",
      gpt5AiCouncil:"/api/5ai/council"
    },null,2),{
      status:r.status,
      headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}
    });
  },

  async scheduled(event,env,ctx){
    const signalPromise=Promise.resolve(signalHub.scheduled?.(event,env,ctx)).catch(()=>null);
    if(envBool(env.BYBIT_AUTO_ENABLED))ctx.waitUntil(Promise.resolve(runBybitAutoV1(env)).catch(()=>null));
    return signalPromise;
  }
};
