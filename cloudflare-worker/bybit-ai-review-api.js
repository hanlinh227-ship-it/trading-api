const AUTO_KEY="bybit:auto:v1:state";
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
async function state(env){try{return await env.TRADING_STATE?.get(AUTO_KEY,{type:"json"})||{};}catch{return {};}}
function compactProvider(x={}){return {status:String(x.status||"UNAVAILABLE").toUpperCase(),latencySeconds:Number.isFinite(Number(x.latencySeconds))?Number(x.latencySeconds):null,error:x.error?String(x.error).slice(0,180):null,review:x.review&&typeof x.review==="object"?x.review:null};}
export async function handleBybitAiReviewApi(req,env){
  const u=new URL(req.url);if(u.pathname!=="/bybit/ai/latest-review")return null;
  if(req.method!=="GET")return json({ok:false,error:"METHOD_NOT_ALLOWED"},405);
  const s=await state(env),a=s.lastAiReview||null,p=s.lastPreAiPreparation||null,q=s.lastPostAiQuote||null;
  if(!a)return json({ok:true,exchange:"BYBIT",available:false,reason:"NO_AI_REVIEW_RECORDED",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),executionAllowed:false});
  const raw=a.providers||{},providers={claude:compactProvider(raw.claude),codex:compactProvider(raw.codex),deepseek:compactProvider(raw.deepseek)};
  return json({ok:true,exchange:"BYBIT",available:true,source:"BYBIT_AUTO_CANONICAL_3AI_GATE",runtimeRevision:String(env.RUNTIME_REVISION||"UNKNOWN"),executionAllowed:false,review:{symbol:a.symbol,side:a.side,at:a.at,mode:a.mode||null,reason:a.reason||null,allow:!!a.allow,pass:Number(a.pass||0),reject:Number(a.reject||0),blocked:Number(a.blocked||0),unavailable:Number(a.unavailable||0),verdicts:a.verdicts||null,providers,entryState:a.entryState||null,reanchorCount:Number(a.reanchorCount||0)},preAiPreparation:p,postAiQuote:q,readOnly:true});
}
