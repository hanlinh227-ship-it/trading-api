import signalHub from "./hub-v77171.js";

const VERSION="V78.027";
const SERVICE="Trading Signal-Only Runtime";

export default {
  async fetch(req,env,ctx){
    const r=await signalHub.fetch(req,env,ctx);
    if(new URL(req.url).pathname!=="/status")return r;
    let body;
    try{body=await r.clone().json();}catch{return r;}
    return new Response(JSON.stringify({...body,version:VERSION,service:SERVICE,executionAuthority:"SIGNAL_ONLY",hyroRemoved:true},null,2),{status:r.status,headers:{"content-type":"application/json; charset=utf-8"}});
  },
  async scheduled(event,env,ctx){
    return signalHub.scheduled?.(event,env,ctx);
  }
};
