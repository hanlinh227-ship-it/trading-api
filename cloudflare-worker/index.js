import signalHub from "./hub-v77171.js";
import {handleUnifiedTelegram,handleControlApi} from "./binance-control-plane.js";

const VERSION="V78.029";
const SERVICE="Trading Unified Hub • Signal + Binance Approval";

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
      executionAuthority:"APPROVAL_CONTROL_ONLY",
      binanceApprovalHub:true,
      binanceExecutionLocation:"VPS",
      hyroRemoved:true
    },null,2),{status:r.status,headers:{"content-type":"application/json; charset=utf-8"}});
  },
  async scheduled(event,env,ctx){
    return signalHub.scheduled?.(event,env,ctx);
  }
};
