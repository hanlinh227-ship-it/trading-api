import {personalGoldConfig} from "./personal-gold-config.js";

const now=()=>Date.now();
async function req(env,path,{method="GET",body=null}={}){
  const base=String(env.PERSONAL_GOLD_EXECUTOR_URL||"").replace(/\/+$/,""),token=String(env.PERSONAL_GOLD_EXECUTOR_TOKEN||"");
  if(!base)return {ok:false,reason:"EXECUTOR_URL_MISSING"};
  const headers={"content-type":"application/json"};if(token)headers.authorization=`Bearer ${token}`;
  const c=new AbortController(),id=setTimeout(()=>c.abort(),4500),t0=now();
  try{const r=await fetch(base+path,{method,headers,body:body?JSON.stringify(body):undefined,signal:c.signal});const j=await r.json().catch(()=>null);return {ok:r.ok,status:r.status,latencyMs:now()-t0,data:j,reason:r.ok?null:(j?.error||j?.reason||`HTTP_${r.status}`)};}catch(e){return {ok:false,reason:String(e?.name==="AbortError"?"EXECUTOR_TIMEOUT":e?.message||e),latencyMs:now()-t0};}finally{clearTimeout(id);}
}
export async function getPersonalGoldAccount(env){return req(env,"/status");}
export async function getPersonalGoldPositions(env){return req(env,"/positions");}
export async function executePersonalGold(env,setup,riskUsd){const cfg=personalGoldConfig(env);if(!cfg.execution.defaultLive)return {ok:false,reason:"LIVE_EXECUTION_DISABLED",paper:true};if(!(Number(riskUsd)>0))return {ok:false,reason:"RISK_USD_INVALID"};const payload={symbol:cfg.brokerSymbol,side:setup.side,entry:Number(setup.entry),sl:Number(setup.sl),tp:Number(setup.tp),riskUsd:Number(riskUsd),maxSlippageUsd:cfg.execution.maxSlippageUsd,setupId:setup.setupId,strategy:setup.strategy,comment:`PGOLD ${setup.strategy}`};return req(env,"/order",{method:"POST",body:payload});}
export async function closePersonalGoldPosition(env,positionId,reason="RISK_MANAGER"){return req(env,"/close",{method:"POST",body:{positionId,reason}});}
