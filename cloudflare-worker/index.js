import signalHub from "./hub-v10-unified-v2.js";
import {handleUnifiedTelegram,handleControlApi} from "./binance-control-plane.js";

const VERSION="V10";
const SERVICE="Trading Unified Hub • Signal Only V10 + Separate Binance Approval";

function isTelegramWebhook(req){
  try{return new URL(req.url).pathname==="/telegram/webhook"&&req.method==="POST";}catch{return false;}
}

async function telegramOwner(req){
  if(!isTelegramWebhook(req))return "NONE";
  try{
    const u=await req.clone().json();
    const cb=String(u?.callback_query?.data||"");
    return cb==="binance"||cb.startsWith("binance:")?"BINANCE":"SIGNAL_V10";
  }catch{return "SIGNAL_V10";}
}

export default {
  async fetch(req,env,ctx){
    const control=await handleControlApi(req,env);
    if(control)return control;

    const owner=await telegramOwner(req);
    if(owner==="BINANCE"){
      const b=await handleUnifiedTelegram(req,env);
      if(b)return b;
    }

    const r=await signalHub.fetch(req,env,ctx);
    if(owner==="SIGNAL_V10")return r;

    if(new URL(req.url).pathname!=="/status")return r;
    let body;
    try{body=await r.clone().json();}catch{return r;}
    return new Response(JSON.stringify({
      ...body,
      version:VERSION,
      service:SERVICE,
      signalOnlySourceOfTruth:"V10",
      telegramRootOwner:"SIGNAL_V10",
      telegramUx:"V10_UNIFIED_LIVE_HISTORY_V2",
      legacyLiveOrdersVisible:true,
      candidateQuoteRefresh:true,
      rejectedCandidatesHiddenFromTradeList:true,
      binanceCallbackNamespace:"binance:*",
      signalThreeAiCouncil:true,
      signalLifecycleLearning:true,
      signalObservedWinRate:true,
      legacySignalVersions:"COMPATIBILITY_SCANNER_ONLY",
      executionAuthority:"APPROVAL_CONTROL_ONLY",
      binanceApprovalHub:true,
      binanceAutoProjectSeparate:true,
      binanceExecutionLocation:"VPS"
    },null,2),{status:r.status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
  },
  async scheduled(event,env,ctx){return signalHub.scheduled?.(event,env,ctx);}
};