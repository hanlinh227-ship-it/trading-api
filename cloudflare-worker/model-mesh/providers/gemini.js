export async function callGemini({baseUrl='https://generativelanguage.googleapis.com/v1beta',apiKey,model,messages,timeoutMs=30000,fetchImpl=fetch}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const contents=messages.map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:String(m.content??'')}]}));
    const response=await fetchImpl(`${String(baseUrl).replace(/\/$/,'')}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({contents}),signal:controller.signal});
    if(response.status===429)return {ok:false,status:429,error:'rate_limited',retryAfter:response.headers.get('retry-after'),resetAt:null};
    if(!response.ok)return {ok:false,status:response.status,error:'provider_error'};
    const data=await response.json();
    const text=(data?.candidates?.[0]?.content?.parts||[]).map(x=>x?.text||'').join('');
    return {ok:true,status:response.status,text:String(text)};
  }catch(error){return {ok:false,status:0,error:error?.name==='AbortError'?'timeout':'network_error'};}finally{clearTimeout(timer);}
}
