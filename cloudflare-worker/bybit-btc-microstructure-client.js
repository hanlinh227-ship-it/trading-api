import {BYBIT_RUNTIME_CONTRACT_VERSION} from './bybit-runtime-contract.js';

function streamStub(env={}){
  const ns=env.BYBIT_MARKET_STREAM;
  if(!ns||typeof ns.idFromName!=='function'||typeof ns.get!=='function')return null;
  try{return ns.get(ns.idFromName('BTCUSDT:PUBLIC:LINEAR'));}catch{return null;}
}

export async function fetchBtcMicrostructure(env={},symbol='BTCUSDT'){
  try{
    const requested=String(symbol||'BTCUSDT').toUpperCase();
    if(requested!=='BTCUSDT'){
      if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')return null;
      const r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789/bybit/microstructure?symbol='+encodeURIComponent(requested),{method:'GET',headers:{accept:'application/json'},signal:AbortSignal.timeout(1500)}));
      if(!r.ok)return null;
      const j=await r.json().catch(()=>null);
      return j?.ok?{ok:true,data:j}:null;
    }
    const stub=streamStub(env);
    if(!stub)return null;
    const r=await stub.fetch(new Request('https://internal.bybit.stream/snapshot?symbol=BTCUSDT',{
      method:'GET',
      headers:{accept:'application/json','x-trading-runtime-contract':BYBIT_RUNTIME_CONTRACT_VERSION},
      signal:AbortSignal.timeout(1500),
    }));
    if(!r.ok)return null;
    const j=await r.json().catch(()=>null);
    const got=String(j?.data?.symbol||'').toUpperCase();
    if(got&&got!=='BTCUSDT')return null;
    return j?.ok?j:null;
  }catch{return null;}
}

export async function connectBtcMicrostructure(env={}){
  try{
    const stub=streamStub(env);if(!stub)return {ok:false,reason:'BYBIT_MARKET_STREAM_BINDING_MISSING'};
    const r=await stub.fetch(new Request('https://internal.bybit.stream/connect',{method:'POST'}));
    return await r.json().catch(()=>({ok:false,reason:'BYBIT_CLOUD_STREAM_CONNECT_INVALID_RESPONSE'}));
  }catch(error){return {ok:false,reason:'BYBIT_CLOUD_STREAM_CONNECT_FAILED',error:String(error?.message||error).slice(0,180)};}
}

export async function btcMicrostructureHealth(env={}){
  try{
    const stub=streamStub(env);if(!stub)return {ok:false,reason:'BYBIT_MARKET_STREAM_BINDING_MISSING'};
    const r=await stub.fetch(new Request('https://internal.bybit.stream/health',{method:'GET'}));
    return await r.json().catch(()=>({ok:false,reason:'BYBIT_CLOUD_STREAM_HEALTH_INVALID_RESPONSE'}));
  }catch(error){return {ok:false,reason:'BYBIT_CLOUD_STREAM_HEALTH_FAILED',error:String(error?.message||error).slice(0,180)};}
}

export const BTC_MICROSTRUCTURE_CLIENT_VERSION='BYBIT_CLOUDFLARE_WS_MICROSTRUCTURE_CLIENT_V1';
