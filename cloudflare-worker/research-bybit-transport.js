const BRIDGE_PUBLIC_BASE='http://127.0.0.1:8789/bybit/public';
const MAX_RESPONSE_BYTES=2_000_000;
const encoder=new TextEncoder();

const bridgeSecret=env=>String(env?.V11_AI_BRIDGE_SECRET||env?.BYBIT_VPS_BRIDGE_SECRET||'').trim();

export function createBybitBridgeFetchJson(env={}){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')throw new Error('BYBIT_VPS_BRIDGE_BINDING_MISSING');
  const secret=bridgeSecret(env);
  if(!secret)throw new Error('BYBIT_VPS_BRIDGE_SECRET_MISSING');
  return async function bybitBridgeFetchJson(url){
    const source=new URL(url);
    if(source.protocol!=='https:'||!['api.bybit.com','api.bytick.com'].includes(source.hostname)||!source.pathname.startsWith('/v5/market/')){
      throw new Error('bybit_public_transport_scope_violation');
    }
    const target=BRIDGE_PUBLIC_BASE+source.pathname+source.search;
    let response;
    try{
      response=await env.AI_BRIDGE.fetch(new Request(target,{method:'GET',headers:{accept:'application/json',authorization:'Bearer '+secret},signal:AbortSignal.timeout(12_000)}));
    }catch(error){
      throw new Error('provider_bridge_fetch_failed:'+String(error?.message||error).slice(0,120));
    }
    if(!response.ok)throw new Error(`provider_http_${response.status}`);
    const text=await response.text();
    if(encoder.encode(text).byteLength>MAX_RESPONSE_BYTES)throw new Error('provider_response_too_large');
    try{return JSON.parse(text);}catch{throw new Error('provider_invalid_json');}
  };
}
