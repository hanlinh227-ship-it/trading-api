// Compatibility surface retained only so existing scheduler/controller routes and KV keys do not break.
// There is no legacy multi-coin strategy behind this file: all authority is BTC-only.
import {runBtcHyperscale,getBtcHyperscaleState} from './bybit-btc-engine.js';
import {BYBIT_AUTO_VERSION} from './bybit-auto-config.js';
const KEY='bybit:btc:hyperscale:v2:state';
async function normalizePersistedVersion(env,state){const s={...(state||{}),version:BYBIT_AUTO_VERSION};try{if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(s));}catch{}return s;}
export async function runBybitAutoV1(env,opts={}){const out=await runBtcHyperscale(env,opts),state=await normalizePersistedVersion(env,out?.state);return {...out,version:BYBIT_AUTO_VERSION,state};}
export async function getBybitAutoV1State(env){return normalizePersistedVersion(env,await getBtcHyperscaleState(env));}
export const BYBIT_AUTO_V1_COMPAT_VERSION=BYBIT_AUTO_VERSION;
