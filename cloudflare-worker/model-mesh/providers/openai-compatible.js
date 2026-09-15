export async function callOpenAICompatible({baseUrl,apiKey,model,messages,timeoutMs=30000,fetchImpl=fetch}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const response=await fetchImpl(`${String(baseUrl).replace(/\/$/,'')}/chat/completions`,{method:'POST',headers:{'content-type':'application/json',Authorization:`Bearer ${apiKey}`},body:JSON.stringify({model,messages,temperature:0.2}),signal:controller.signal});
    const retryAfter=response.headers.get('retry-after');
    if(response.status===429)return {ok:false,status:429,error:'rate_limited',retryAfter,resetAt:response.headers.get('x-ratelimit-reset-requests')||response.headers.get('x-ratelimit-reset-tokens')||null};
    if(!response.ok)return {ok:false,status:response.status,error:'provider_error'};
    const data=await response.json();
    return {ok:true,status:response.status,text:String(data?.choices?.[0]?.message?.content??'')};
  }catch(error){return {ok:false,status:0,error:error?.name==='AbortError'?'timeout':'network_error'};}finally{clearTimeout(timer);}
}
