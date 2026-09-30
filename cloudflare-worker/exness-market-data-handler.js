import {authState} from './worker-auth.js';
import {jsonResponse} from './exness-market-data.js';

const readOnlyEnabled=env=>String(env.EXNESS_ENABLED||'').toLowerCase()==='true'&&String(env.EXNESS_MODE||'').toUpperCase()==='SHADOW'&&String(env.EXNESS_LIVE_ENABLED||'').toLowerCase()!=='true'&&String(env.EXNESS_LIVE_ACK||'').toLowerCase()!=='true';

export async function handleExnessMarketData(request,env={},opts={}){
  const url=new URL(request.url),path=url.pathname;
  if(!['/exness/instruments','/exness/quote'].includes(path))return null;
  if(request.method!=='GET')return jsonResponse({ok:false,error:'METHOD_NOT_ALLOWED',readOnly:true},405);
  if(!authState(request,env).ok)return jsonResponse({ok:false,error:'UNAUTHORIZED'},401);
  if(!readOnlyEnabled(env))return jsonResponse({ok:false,error:'EXNESS_READ_ONLY_DISABLED',readOnly:true},503);
  if(!(env.EXNESS_READONLY_API_KEY||env.EXNESS_API_KEY)||!(env.EXNESS_READONLY_PRIVATE_KEY||env.EXNESS_PRIVATE_KEY)||!(env.EXNESS_READONLY_ACCOUNT_ID||env.EXNESS_ACCOUNT_ID)||!(env.EXNESS_READONLY_API_BASE_URL||env.EXNESS_API_BASE_URL))return jsonResponse({ok:false,error:'EXNESS_RUNTIME_CONFIGURATION_MISSING',readOnly:true},503);
  const instrument=String(url.searchParams.get('instrument')||'').trim();
  if(path==='/exness/quote'&&!/^[A-Za-z0-9._-]{1,11}$/.test(instrument))return jsonResponse({ok:false,error:'INSTRUMENT_REQUIRED',readOnly:true},400);
  try{
    if(opts.clientFactory){
      const client=opts.clientFactory(env);
      const result=path==='/exness/instruments'?await client.instruments():await client.quote(instrument);
      return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,...result});
    }
    const binding=env.EXNESS_MARKET_DATA_STATE;
    if(!binding)throw Object.assign(new Error('EXNESS_RUNTIME_BINDING_MISSING'),{code:'EXNESS_RUNTIME_BINDING_MISSING',status:503});
    const accountId=env.EXNESS_READONLY_ACCOUNT_ID||env.EXNESS_ACCOUNT_ID;
    const id=binding.idFromName(String(accountId)),stub=binding.get(id);
    const target=path==='/exness/instruments'?'/instruments':`/quote?instrument=${encodeURIComponent(instrument)}`;
    const response=await stub.fetch(new Request(`https://exness-market-data.internal${target}`,{method:'GET'}));
    return new Response(await response.text(),{status:response.status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
  }catch(error){
    const code=String(error?.code||error?.message||'EXNESS_MARKET_DATA_UNAVAILABLE');
    return jsonResponse({ok:false,exchange:'EXNESS',readOnly:true,error:code},Number(error?.status)||503);
  }
}
