const stubFor=binding=>binding?.getByName?.('global');
export async function checkTinyFishGuard(binding,nowMs=Date.now()){
  const stub=stubFor(binding);if(!stub)return {allowed:false,state:'STORE_UNAVAILABLE'};
  try{const response=await stub.fetch('https://tinyfish-circuit/acquire',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({nowMs})});const row=await response.json();return {allowed:response.ok&&row.allowed===true,state:String(row.state||'STORE_UNAVAILABLE'),retryAfterMs:Number(row.retryAfterMs)||undefined};}catch{return {allowed:false,state:'STORE_UNAVAILABLE'};}
}
export async function recordTinyFishGuard(binding,result,nowMs=Date.now()){
  const stub=stubFor(binding);if(!stub)return {persisted:false};
  try{const response=await stub.fetch('https://tinyfish-circuit/record',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({nowMs,ok:result?.ok===true,category:String(result?.category||'')})});const row=await response.json();return {persisted:response.ok,state:row.state};}catch{return {persisted:false};}
}
