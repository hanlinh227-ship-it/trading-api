import {BYBIT_RUNTIME_CONTRACT_VERSION} from './bybit-runtime-contract.js';
import {normalizeBybitSymbol} from './bybit-coin-profiles.js';

const DEFAULT_SYMBOL='BTCUSDT';
const SNAPSHOT_COLD_START_TIMEOUT_MS=3000;
const CONNECT_COLD_START_TIMEOUT_MS=6000;
const HEALTH_PROPAGATION_TIMEOUT_MS=1500;
function validSymbol(v=''){
  const s=normalizeBybitSymbol(v||DEFAULT_SYMBOL);
  return /^[A-Z0-9]{2,28}USDT$/.test(s)?s:DEFAULT_SYMBOL;
}
function streamStub(env={},symbol=DEFAULT_SYMBOL){
  const ns=env.BYBIT_MARKET_STREAM,s=validSymbol(symbol);
  if(!ns||typeof ns.idFromName!=='function'||typeof ns.get!=='function')return null;
  try{return ns.get(ns.idFromName(s+':PUBLIC:LINEAR'));}catch{return null;}
}
async function streamFetch(env,symbol,path,{method='GET',timeoutMs=700}={}){
  const s=validSymbol(symbol),stub=streamStub(env,s);if(!stub)return null;
  const sep=path.includes('?')?'&':'?',url='https://internal.bybit.stream'+path+sep+'symbol='+encodeURIComponent(s);
  const r=await stub.fetch(new Request(url,{method,headers:{accept:'application/json','x-trading-runtime-contract':BYBIT_RUNTIME_CONTRACT_VERSION},signal:AbortSignal.timeout(timeoutMs)}));
  if(!r.ok)return null;
  return await r.json().catch(()=>null);
}

export async function fetchBtcMicrostructure(env={},symbol=DEFAULT_SYMBOL){
  try{
    const requested=validSymbol(symbol),j=await streamFetch(env,requested,'/snapshot',{timeoutMs:SNAPSHOT_COLD_START_TIMEOUT_MS}),got=normalizeBybitSymbol(j?.data?.symbol||'');
    if(!j?.ok||!got||got!==requested)return null;
    return j;
  }catch{return null;}
}

export async function fetchBybitUniverseTickers(env={}){
  try{
    const j=await streamFetch(env,DEFAULT_SYMBOL,'/universe-tickers',{timeoutMs:800});
    return j?.ok&&Array.isArray(j?.data?.rows)?j.data:null;
  }catch{return null;}
}

export async function connectBtcMicrostructure(env={},symbol=DEFAULT_SYMBOL){
  try{
    const s=validSymbol(symbol),j=await streamFetch(env,s,'/connect',{method:'POST',timeoutMs:CONNECT_COLD_START_TIMEOUT_MS});
    return j||{ok:false,reason:'BYBIT_CLOUD_STREAM_CONNECT_INVALID_RESPONSE',symbol:s};
  }catch(error){return {ok:false,reason:'BYBIT_CLOUD_STREAM_CONNECT_FAILED',error:String(error?.message||error).slice(0,180),symbol:validSymbol(symbol)};}
}

export async function btcMicrostructureHealth(env={},symbol=DEFAULT_SYMBOL){
  try{
    const s=validSymbol(symbol),j=await streamFetch(env,s,'/health',{timeoutMs:HEALTH_PROPAGATION_TIMEOUT_MS});
    return j||{ok:false,reason:'BYBIT_CLOUD_STREAM_HEALTH_INVALID_RESPONSE',symbol:s};
  }catch(error){return {ok:false,reason:'BYBIT_CLOUD_STREAM_HEALTH_FAILED',error:String(error?.message||error).slice(0,180),symbol:validSymbol(symbol)};}
}

export const BTC_MICROSTRUCTURE_CLIENT_VERSION='BYBIT_CLOUDFLARE_WS_MICROSTRUCTURE_CLIENT_V4_COLD_START_TOLERANT';
