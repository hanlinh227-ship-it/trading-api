const KEY='brain:evidence:tinyfish:guard:v1';
const safe=raw=>{try{const x=JSON.parse(raw);return x?.schemaVersion===1?x:null;}catch{return null;}};
export async function checkTinyFishGuard(kv,nowMs=Date.now()){
  if(!kv?.get)return {allowed:true,state:'UNPERSISTED'};
  try{const row=safe(await kv.get(KEY));if(!row)return {allowed:true,state:'CLOSED'};if(Number(row.openUntil)>nowMs)return {allowed:false,state:'OPEN',retryAfterMs:Number(row.openUntil)-nowMs};if(Number(row.nextAllowedAt)>nowMs)return {allowed:false,state:'RATE_LIMITED',retryAfterMs:Number(row.nextAllowedAt)-nowMs};return {allowed:true,state:'CLOSED',failures:Number(row.failures)||0};}catch{return {allowed:true,state:'STORE_UNAVAILABLE'};}
}
export async function recordTinyFishGuard(kv,result,nowMs=Date.now()){
  if(!kv?.put)return {persisted:false};
  let previous={failures:0};try{previous=safe(await kv.get(KEY))||previous;}catch{}
  const failures=result?.ok?0:Math.min(10,(Number(previous.failures)||0)+1),openUntil=failures>=3?nowMs+5*60*1000:0;
  const row={schemaVersion:1,failures,openUntil,nextAllowedAt:nowMs+2000,updatedAt:new Date(nowMs).toISOString(),lastCategory:result?.ok?null:String(result?.category||'UNKNOWN_SANITIZED')};
  try{await kv.put(KEY,JSON.stringify(row),{expirationTtl:600});return {persisted:true,state:openUntil?'OPEN':'CLOSED'};}catch{return {persisted:false};}
}
