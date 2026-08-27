import autoHub from "./bybit-auto-hub.js";
import {handleBybitReadonlyHealth} from "./bybit-readonly-health.js";
import {handleBybitControlApi} from "./bybit-control-plane.js";
import {handleBybitAiReviewApi} from "./bybit-ai-review-api.js";
import {runBybitAutoControlled,recordBybitAutoSchedulerError} from "./bybit-auto-controller.js";
import {BYBIT_AUTO_VERSION} from "./bybit-auto-config.js";
import {BYBIT_RUNTIME_CONTRACT,BYBIT_EXECUTION_AUTHORITY,TELEGRAM_HUB_ID,BYBIT_HEALTH_ROUTE} from "./bybit-runtime-contract.js";
import {MEME_AUTO_VERSION,MEME_AUTO_MODE} from "./meme-auto-design.js";
import {runMemePaperCycle,getMemePaperState} from "./meme-paper-engine.js";
import {getMemeJupiterQuoteHealth} from "./meme-quote-health.js";
import {handleForexMt5ProtocolV1} from "./forex-mt5-protocol-v1-compat.js";
import {handleForexTelegramHub} from "./forex-telegram-hub.js";
import {FOREX_AUTO_VERSION} from "./forex-auto-config.js";

const VERSION=BYBIT_AUTO_VERSION;
const SERVICE="Unified Trading Hub";
const envBool=v=>String(v||"").toLowerCase()==="true";
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});

export default {
  async fetch(req,env,ctx){
    const bybitHealth=await handleBybitReadonlyHealth(req,env); if(bybitHealth)return bybitHealth;
    const bybitReview=await handleBybitAiReviewApi(req,env); if(bybitReview)return bybitReview;
    const bybitControl=await handleBybitControlApi(req,env); if(bybitControl)return bybitControl;
    const forex=await handleForexMt5ProtocolV1(req,env,ctx); if(forex)return forex;
    const forexTelegram=await handleForexTelegramHub(req,env,ctx); if(forexTelegram)return forexTelegram;
    const hub=await autoHub.fetch(req,env,ctx); if(hub)return hub;
    const url=new URL(req.url);
    if(url.pathname==="/runtime/contract")return json({ok:true,...BYBIT_RUNTIME_CONTRACT,runtimeRevision:String(env.RUNTIME_REVISION||"")});
    if(["/mcp","/mcp/health","/gpt-5ai/action","/internal/multi-ai/review"].includes(url.pathname))return json({ok:false,error:"RETIRED_CONFLICTING_AI_ROUTE",replacement:"/bybit/ai/latest-review",authority:"BYBIT_AUTO_CANONICAL_2AI_GATE"},410);
    if(url.pathname==="/meme-auto/paper/state")return json(await getMemePaperState(env));
    if(url.pathname==="/meme-auto/paper/run")return json(await runMemePaperCycle(env));
    if(url.pathname==="/meme-auto/quote-health")return json(await getMemeJupiterQuoteHealth(env));
    if(url.pathname==="/status")return json({
      ok:true,version:VERSION,service:SERVICE,hub:BYBIT_EXECUTION_AUTHORITY,runtimeContract:BYBIT_RUNTIME_CONTRACT,
      telegramHub:TELEGRAM_HUB_ID,telegramBranches:["BYBIT","FOREX","MEME"],signalV11Enabled:false,signalSchedulerEnabled:false,
      bybit:{version:BYBIT_AUTO_VERSION,autoEnabled:envBool(env.BYBIT_AUTO_ENABLED),live:envBool(env.BYBIT_AUTO_LIVE),demo:envBool(env.BYBIT_AUTO_DEMO),environment:envBool(env.BYBIT_AUTO_DEMO)?"DEMO":(envBool(env.BYBIT_AUTO_LIVE)?"LIVE":"PAPER"),executionAuthority:true,readonlyHealth:BYBIT_HEALTH_ROUTE,runtimeContract:"/runtime/contract",twoAiAuthority:"BYBIT_AUTO_CANONICAL_2AI_GATE",latestAiReview:"/bybit/ai/latest-review"},
      forex:{version:FOREX_AUTO_VERSION,mode:envBool(env.FOREX_AUTO_LIVE)?"LIVE":"PAPER",mt5VpsWine11:true,autonomous2Ai:["chatgpt","claude"],telegramCanonicalDashboard:true,ruleBasedSignalAuthority:false,health:"/forex/health",liveEnabled:envBool(env.FOREX_AUTO_LIVE)},
      meme:{version:MEME_AUTO_VERSION,mode:MEME_AUTO_MODE,paperEnabled:true,executionEnabled:false,walletConnected:false,signingEnabled:false,paperState:"/meme-auto/paper/state",paperRun:"/meme-auto/paper/run",quoteHealth:"/meme-auto/quote-health"},telegramWebhook:"/telegram/webhook"
    });
    if(url.pathname.startsWith("/v11/"))return json({ok:false,error:"SIGNAL_V11_DISABLED",replacement:"BYBIT_AUTO_TRADE_HUB",runtimeContract:"/runtime/contract"},410);
    return json({ok:false,error:"AUTO_HUB_ENDPOINT_NOT_FOUND",runtimeContract:"/runtime/contract"},404);
  },
  async scheduled(event,env,ctx){
    if(envBool(env.BYBIT_AUTO_ENABLED))ctx.waitUntil(Promise.resolve(runBybitAutoControlled(env)).catch(e=>recordBybitAutoSchedulerError(env,e).catch(()=>null)));
    ctx.waitUntil(Promise.resolve(runMemePaperCycle(env)).catch(()=>null));
  }
};
