export async function callGemini({baseUrl='https://generativelanguage.googleapis.com/v1beta',apiKey,model,messages,timeoutMs=30000,fetchImpl=fetch}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const contents=messages.map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:String(m.content??'')}]}));
    const response=await fetchImpl(`${String(baseUrl).replace(/\/$/,'')}/models/${encodeURIComponent(model)}:generateContent`,{method:'POST',headers:{'content-type':'application/json','x-goog-api-key':apiKey},body:JSON.stringify({contents}),signal:controller.signal});
    if(!response.ok)return {ok:false,status:response.status,category:classifyProviderFailure({status:response.status}),retryAfter:response.headers.get('retry-after'),resetAt:null};
    const data=await readJsonBounded(response);
    const text=(data?.candidates?.[0]?.content?.parts||[]).map(x=>x?.text||'').join('');
    return {ok:true,status:response.status,text:String(text)};
  }catch(error){const code=error?.name==='AbortError'?'TIMEOUT':error?.code;return {ok:false,status:0,category:classifyProviderFailure({code})};}finally{clearTimeout(timer);}
}
import {classifyProviderFailure} from '../contracts.js';
import {readJsonBounded} from './response.js';
