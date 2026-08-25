import autoHub from "./bybit-auto-hub.js";
import {handleMultiAiControl} from "./multi-ai-control-plane.js";
import {handleChatGptMcp} from "./chatgpt-mcp.js";
import {handleGpt5AiAction} from "./gpt-5ai-action.js";
import {handleBybitReadonlyHealth} from "./bybit-readonly-health.js";
import {handleBybitControlApi} from "./bybit-control-plane.js";
import {runBybitAutoControlled} from "./bybit-auto-controller.js";
import {BYBIT_AUTO_VERSION} from "./bybit-auto-config.js";
import {MEME_AUTO_VERSION,MEME_AUTO_MODE} from "./meme-auto-design.js";
import {runMemePaperCycle,getMemePaperState} from "./meme-paper-engine.js";

const VERSION=BYBIT_AUTO_VERSION;
const SERVICE="Unified Trading Hub";
const EXECUTION_AUTHORITY="BYBIT_AUTO_TRADE_ONLY";
const envBool=v=>String(v||"").toLowerCase()==="true";
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});

export default {
  async fetch(req,env,ctx){
    const bybitHealth=await handleBybitReadonlyHealth(req,env); if(bybitHealth)return bybitHealth;
    const bybitControl=await handleBybitControlApi(req,env); if(bybitControl)return bybitControl;
    const mcp=await handleChatGptMcp(req,env); if(mcp)return mcp;
    const gpt5ai=await handleGpt5AiAction(req,env); if(gpt5ai)return gpt5ai;
    const multi=await handleMultiAiControl(req,env); if(multi)return multi;
    const hub=await autoHub.fetch(req,env,ctx); if(hub)return hub;
    const url=new URL(req.url);
    if(url.pathname==="/meme-auto/paper/state")return json(await getMemePaperState(env));
    if(url.pathname==="/meme-auto/paper/run")return json(await runMemePaperCycle(env));
    if(url.pathname==="/status")return json({
      ok:true,version:VERSION,service:SERVICE,hub:EXECUTION_AUTHORITY,
      telegramHub:"UNIFIED_BYBIT_MEME",telegramBranches:["BYBIT","MEME"],
      signalV11Enabled:false,signalSchedulerEnabled:false,
      bybit:{version:BYBIT_AUTO_VERSION,autoEnabled:envBool(env.BYBIT_AUTO_ENABLED),live:envBool(env.BYBIT_AUTO_LIVE),executionAuthority:true,readonlyHealth:"/bybit/health"},
      meme:{version:MEME_AUTO_VERSION,mode:MEME_AUTO_MODE,paperEnabled:true,executionEnabled:false,walletConnected:false,signingEnabled:false,paperState:"/meme-auto/paper/state",paperRun:"/meme-auto/paper/run"},
      telegramWebhook:"/telegram/webhook"
    });
    if(url.pathname.startsWith("/v11/"))return json({ok:false,error:"SIGNAL_V11_DISABLED",replacement:"BYBIT_AUTO_TRADE_HUB"},410);
    return json({ok:false,error:"AUTO_HUB_ENDPOINT_NOT_FOUND"},404);
  },
  async scheduled(event,env,ctx){
    // BYBIT remains the only real-money execution authority. MEME cycle is PAPER-ONLY:
    // it reads free public market/on-chain data and updates simulated KV state only.
    if(envBool(env.BYBIT_AUTO_ENABLED))ctx.waitUntil(Promise.resolve(runBybitAutoControlled(env)).catch(()=>null));
    ctx.waitUntil(Promise.resolve(runMemePaperCycle(env)).catch(()=>null));
  }
};
