import autoHub from "./bybit-auto-hub.js";
import {handleMultiAiControl} from "./multi-ai-control-plane.js";
import {handleChatGptMcp} from "./chatgpt-mcp.js";
import {handleGpt5AiAction} from "./gpt-5ai-action.js";
import {handleBybitReadonlyHealth} from "./bybit-readonly-health.js";
import {handleBybitControlApi} from "./bybit-control-plane.js";
import {runBybitAutoControlled} from "./bybit-auto-controller.js";
import {BYBIT_AUTO_VERSION} from "./bybit-auto-config.js";
import {MEME_AUTO_VERSION,MEME_AUTO_MODE} from "./meme-auto-design.js";

const VERSION=BYBIT_AUTO_VERSION;
const SERVICE="Unified Trading Hub";
const envBool=v=>String(v||"").toLowerCase()==="true";
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});

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

    const hub=await autoHub.fetch(req,env,ctx);
    if(hub)return hub;

    const url=new URL(req.url);
    if(url.pathname==="/status")return json({
      ok:true,
      version:VERSION,
      service:SERVICE,
      hub:"BYBIT_AUTO_TRADE_ONLY",
      telegramHub:"UNIFIED_BYBIT_MEME",
      telegramBranches:["BYBIT","MEME"],
      readOnlyHub:true,
      signalV11Enabled:false,
      signalSchedulerEnabled:false,
      bybit:{
        version:BYBIT_AUTO_VERSION,
        autoEnabled:envBool(env.BYBIT_AUTO_ENABLED),
        live:envBool(env.BYBIT_AUTO_LIVE),
        executionAuthority:true,
        readonlyHealth:"/bybit/health",
        preflight:"/bybit/runtime/preflight",
        autoState:"/bybit/auto/state",
        learningState:"/bybit/learning/state"
      },
      meme:{
        version:MEME_AUTO_VERSION,
        mode:MEME_AUTO_MODE,
        executionEnabled:false,
        walletConnected:false,
        signingEnabled:false,
        design:"/meme-auto/design"
      },
      telegramWebhook:"/telegram/webhook",
      management:"HOLD_BREAKEVEN_PROFIT_LOCK_TRAIL_TP_STOP",
      discretionaryCutEnabled:envBool(env.BYBIT_DISCRETIONARY_CUT_ENABLED),
      aiCore:["claude","codex","deepseek"]
    });

    if(url.pathname.startsWith("/v11/"))return json({ok:false,error:"SIGNAL_V11_DISABLED",replacement:"BYBIT_AUTO_TRADE_HUB"},410);
    return json({ok:false,error:"AUTO_HUB_ENDPOINT_NOT_FOUND"},404);
  },

  async scheduled(event,env,ctx){
    // Signal V11 scheduler is intentionally disabled. The only scheduled trading workload
    // on this Worker remains the Bybit Auto controller. MEME is design-only and has no scheduler.
    if(envBool(env.BYBIT_AUTO_ENABLED))ctx.waitUntil(Promise.resolve(runBybitAutoControlled(env)).catch(()=>null));
  }
};