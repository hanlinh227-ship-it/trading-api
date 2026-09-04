import {BYBIT_RUNTIME_CONTRACT_VERSION} from './bybit-runtime-contract.js';

const BRIDGE_URL='http://127.0.0.1:8789/bybit/microstructure';
export async function fetchBtcMicrostructure(env={},symbol='BTCUSDT'){
  try{
    if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')return null;
    const secret=String(env.V11_AI_BRIDGE_SECRET||env.BYBIT_VPS_BRIDGE_SECRET||'');if(!secret)return null;
    const url=`${BRIDGE_URL}?symbol=${encodeURIComponent(symbol)}`;
    const r=await env.AI_BRIDGE.fetch(new Request(url,{method:'GET',headers:{accept:'application/json',authorization:`Bearer ${secret}`,'x-trading-runtime-contract':BYBIT_RUNTIME_CONTRACT_VERSION},signal:AbortSignal.timeout(2500)}));
    if(!r.ok)return null;const j=await r.json().catch(()=>null),got=String(j?.data?.symbol||j?.result?.symbol||'').toUpperCase();if(got&&got!==String(symbol).toUpperCase())return null;return j?.ok?j:null;
  }catch{return null;}
}
export const BTC_MICROSTRUCTURE_CLIENT_VERSION='BYBIT_MULTI_SYMBOL_VPS_MICROSTRUCTURE_CLIENT_V2';
