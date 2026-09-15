export async function callCloudflareAI({accountId,apiKey,model,messages,timeoutMs=30000,fetchImpl=fetch}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const response=await fetchImpl(`https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(accountId)}/ai/run/${encodeURIComponent(model)}`,{method:'POST',headers:{'content-type':'application/json',Authorization:`Bearer ${apiKey}`},body:JSON.stringify({messages}),signal:controller.signal});
    if(response.status===429)return {ok:false,status:429,error:'rate_limited',retryAfter:response.headers.get('retry-after'),resetAt:null};
    if(!response.ok)return {ok:false,status:response.status,error:'provider_error'};
    const data=await response.json();
    return {ok:true,status:response.status,text:String(data?.result?.response??data?.result??'')};
  }catch(error){return {ok:false,status:0,error:error?.name==='AbortError'?'timeout':'network_error'};}finally{clearTimeout(timer);}
}
