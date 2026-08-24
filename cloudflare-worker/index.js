import signalHub from "./hub-v11.js";
import {
  handleUnifiedTelegram,
  handleControlApi
} from "./binance-control-plane.js";
import {
  handleMultiAiControl
} from "./multi-ai-control-plane.js";
import {
  handleChatGptMcp
} from "./chatgpt-mcp.js";
import {
  handleGpt5AiAction
} from "./gpt-5ai-action.js";
import {
  handleBinanceReadonlyHealth
} from "./binance-readonly-health.js";

const VERSION="V11";
const SERVICE="Trading Unified Hub • Signal V11 + Separate Binance Auto";

function isTelegramWebhook(req){
  try{return new URL(req.url).pathname==="/telegram/webhook"&&req.method==="POST";}catch{return false;}
}

async function telegramOwner(req){
  if(!isTelegramWebhook(req))return "NONE";
  try{
    const u=await req.clone().json();
    const cb=String(u?.callback_query?.data||"");
    return cb==="binance"||cb.startsWith("binance:")?"BINANCE":"SIGNAL_V11";
  }catch{return "SIGNAL_V11";}
}

export default {
  async fetch(req,env,ctx){
    const binanceHealth=await handleBinanceReadonlyHealth(req,env);
    if(binanceHealth)return binanceHealth;

    const mcp=await handleChatGptMcp(req,env);
    if(mcp)return mcp;

    const gpt5ai=await handleGpt5AiAction(req,env);
    if(gpt5ai)return gpt5ai;

    const multi=await handleMultiAiControl(req,env);
    if(multi)return multi;

    const control=await handleControlApi(req,env);
    if(control)return control;

    const owner=await telegramOwner(req);
    if(owner==="BINANCE"){
      const b=await handleUnifiedTelegram(req,env);
      if(b)return b;
    }

    const r=await signalHub.fetch(req,env,ctx);
    const url=new URL(req.url);
    if(owner==="SIGNAL_V11"||url.pathname!=="/status")return r;

    let body;
    try{body=await r.clone().json();}catch{return r;}

    return new Response(JSON.stringify({
      ...body,
      version:VERSION,
      service:SERVICE,
      signalOnlySourceOfTruth:"V11",
      telegramRootOwner:"SIGNAL_V11",
      binanceAutoProjectSeparate:true,
      multiAiGateway:"VPC_OIDC_CONTROL_PLANE",
      chatgptMcp:"/mcp",
      gpt5AiCouncil:"/api/5ai/council",
      binanceReadonlyHealth:"/binance/health"
    },null,2),{
      status:r.status,
      headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}
    });
  },

  async scheduled(event,env,ctx){
    return signalHub.scheduled?.(event,env,ctx);
  }
};
