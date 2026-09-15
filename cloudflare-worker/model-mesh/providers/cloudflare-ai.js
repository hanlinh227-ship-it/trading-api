export async function callCloudflareAI({accountId,apiKey,model,messages,timeoutMs=30000,fetchImpl=fetch}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const modelPath=String(model).split('/').map(encodeURIComponent).join('/');
    const response=await fetchImpl(`https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(accountId)}/ai/run/${modelPath}`,{method:'POST',headers:{'content-type':'application/json',Authorization:`Bearer ${apiKey}`},body:JSON.stringify({messages}),signal:controller.signal});
    if(!response.ok)return {ok:false,status:response.status,category:classifyProviderFailure({status:response.status}),retryAfter:response.headers.get('retry-after'),resetAt:null};
    const data=await readJsonBounded(response);
    return {ok:true,status:response.status,text:String(data?.result?.response??data?.result??'')};
  }catch(error){const code=error?.name==='AbortError'?'TIMEOUT':error?.code;return {ok:false,status:0,category:classifyProviderFailure({code})};}finally{clearTimeout(timer);}
}
import {classifyProviderFailure} from '../contracts.js';
import {readJsonBounded} from './response.js';
