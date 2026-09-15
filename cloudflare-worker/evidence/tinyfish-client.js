import {classifyProviderFailure} from '../model-mesh/contracts.js';
import {readJsonBounded} from '../model-mesh/providers/response.js';

const SEARCH_URL='https://api.search.tinyfish.ai',FETCH_URL='https://api.fetch.tinyfish.ai';
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function safeUrl(value){
  try{const url=new URL(value);const host=url.hostname.toLowerCase();if(url.protocol!=='https:'||host==='localhost'||host.endsWith('.local')||/^(?:127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.)/.test(host))return null;return url.toString();}catch{return null;}
}
function sanitizeEvidence(data){
  const source=Array.isArray(data?.results)?data.results:Array.isArray(data)?data:[];
  return source.slice(0,10).map(item=>({title:String(item?.title||'').slice(0,300),url:safeUrl(item?.url)||null,snippet:String(item?.snippet??item?.content??item?.text??'').slice(0,4000),error:item?.error?String(item.error).slice(0,120):undefined}));
}
export async function callTinyFish({operation,query='',urls=[],apiKey,timeoutMs=15000,maxRetries=1,fetchImpl=fetch,delay=wait}={}){
  if(!apiKey)return {ok:false,status:0,category:'AUTH_FAILED',attempts:0,evidence:[]};
  const op=String(operation||'search').toLowerCase();if(!['search','fetch'].includes(op))return {ok:false,status:400,category:'REQUEST_INVALID',attempts:0,evidence:[]};
  const validUrls=op==='fetch'?(Array.isArray(urls)?urls:[]).map(safeUrl).filter(Boolean).slice(0,10):[];
  if(op==='fetch'&&(!validUrls.length||validUrls.length!==(Array.isArray(urls)?urls.length:0)))return {ok:false,status:400,category:'REQUEST_INVALID',attempts:0,evidence:[]};
  if(op==='search'&&(!String(query).trim()||String(query).length>500))return {ok:false,status:400,category:'REQUEST_INVALID',attempts:0,evidence:[]};
  for(let attempt=0;attempt<=Math.max(0,Math.min(2,maxRetries));attempt+=1){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);
    try{
      const url=op==='search'?`${SEARCH_URL}?query=${encodeURIComponent(String(query).trim())}`:FETCH_URL;
      const init={method:op==='search'?'GET':'POST',headers:{'X-API-Key':apiKey,'accept':'application/json'},signal:controller.signal};
      if(op==='fetch'){init.headers['content-type']='application/json';init.body=JSON.stringify({urls:validUrls});}
      const response=await fetchImpl(url,init);
      if(response.ok){const data=await readJsonBounded(response,262144);return {ok:true,status:response.status,category:null,attempts:attempt+1,evidence:sanitizeEvidence(data)};}
      const category=classifyProviderFailure({status:response.status});
      if(attempt<maxRetries&&(category==='RATE_LIMITED'||category==='PROVIDER_5XX')){await delay(Math.min(250*(attempt+1),500));continue;}
      return {ok:false,status:response.status,category,attempts:attempt+1,evidence:[]};
    }catch(error){const category=classifyProviderFailure({code:error?.name==='AbortError'?'TIMEOUT':error?.code});if(attempt<maxRetries&&category!=='PARSE_FAILED'){await delay(Math.min(250*(attempt+1),500));continue;}return {ok:false,status:0,category,attempts:attempt+1,evidence:[]};}
    finally{clearTimeout(timer);}
  }
  return {ok:false,status:0,category:'UNKNOWN_SANITIZED',attempts:0,evidence:[]};
}
