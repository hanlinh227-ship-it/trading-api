export async function callOpenAICompatible({baseUrl,apiKey,model,messages,timeoutMs=30000,fetchImpl=fetch}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const response=await fetchImpl(`${String(baseUrl).replace(/\/$/,'')}/chat/completions`,{method:'POST',headers:{'content-type':'application/json',Authorization:`Bearer ${apiKey}`},body:JSON.stringify({model,messages,temperature:0.2}),signal:controller.signal});
    const retryAfter=response.headers.get('retry-after');
    if(!response.ok)return {ok:false,status:response.status,category:classifyProviderFailure({status:response.status}),retryAfter,resetAt:response.headers.get('x-ratelimit-reset-requests')||response.headers.get('x-ratelimit-reset-tokens')||null};
    const data=await readJsonBounded(response);
    return {ok:true,status:response.status,text:String(data?.choices?.[0]?.message?.content??'')};
  }catch(error){const code=error?.name==='AbortError'?'TIMEOUT':error?.code;return {ok:false,status:0,category:classifyProviderFailure({code})};}finally{clearTimeout(timer);}
}
import {classifyProviderFailure} from '../contracts.js';
import {readJsonBounded} from './response.js';
