import signalHub from "./hub-v10.js";
import {handleUnifiedTelegram,handleControlApi} from "./binance-control-plane.js";

const VERSION="V10";
const SERVICE="Trading Unified Hub • Signal Only V10 + Separate Binance Approval";

export default {
  async fetch(req,env,ctx){
    const control=await handleControlApi(req,env);
    if(control)return control;

    const telegram=await handleUnifiedTelegram(req,env);
    if(telegram)return telegram;

    const r=await signalHub.fetch(req,env,ctx);
    if(new URL(req.url).pathname!=="/status")return r;
    let body;
    try{body=await r.clone().json();}catch{return r;}
    return new Response(JSON.stringify({
      ...body,
      version:VERSION,
      service:SERVICE,
      signalOnlySourceOfTruth:"V10",
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
  async scheduled(event,env,ctx){
    return signalHub.scheduled?.(event,env,ctx);
  }
};
