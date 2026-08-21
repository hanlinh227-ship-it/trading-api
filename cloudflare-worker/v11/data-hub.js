import {V11_CONFIG} from './config.js';
const mem=new Map();
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const now=()=>Date.now();
function cacheKey(provider,symbol,tf){return `v11:data:${provider}:${symbol}:${tf}`;}
export function candleTtlMs(tf){return ({'1min':60000,'5min':300000,'15min':900000,'1h':3600000,'4h':14400000,'1day':86400000}[tf]||60000);}
export function verifiedQuote(q,market){const p=n(q?.price),ts=n(q?.timestamp??q?.ts),age=ts?Math.max(0,(Date.now()/1000-ts)):Infinity;return !!p&&q?.fresh===true&&age<=V11_CONFIG.quoteTtlSec[market];}
export class TdBudget{constructor(){this.minute=-1;this.used=0;}reset(){const m=Math.floor(Date.now()/60000);if(m!==this.minute){this.minute=m;this.used=0;}}available(){this.reset();return Math.max(0,V11_CONFIG.td.creditsPerMinute-this.used);}admit(cost,kind='discovery'){this.reset();const reserve=kind==='lifecycle'?0:kind==='verification'?V11_CONFIG.td.reserveLifecycle:V11_CONFIG.td.reserveLifecycle+V11_CONFIG.td.reserveVerification;if(this.used+cost>V11_CONFIG.td.creditsPerMinute-reserve)return false;this.used+=cost;return true;}}
export const tdBudget=new TdBudget();
async function kvGet(env,key){try{return env.V11_CACHE?.get(key,'json')||null}catch{return null}}
async function kvPut(env,key,val,ttl){try{await env.V11_CACHE?.put(key,JSON.stringify(val),{expirationTtl:Math.max(60,Math.ceil(ttl/1000))})}catch{}}
export async function cached(env,{provider,symbol,timeframe,loader,ttlMs=candleTtlMs(timeframe),force=false}){const key=cacheKey(provider,symbol,timeframe),m=mem.get(key);if(!force&&m&&now()-m.at<ttlMs)return {...m.value,cache:'memory'};if(!force){const k=await kvGet(env,key);if(k&&now()-Number(k.cachedAt||0)<ttlMs){mem.set(key,{at:Number(k.cachedAt),value:k});return {...k,cache:'kv'};}}const value=await loader();const wrapped={...value,cachedAt:now(),provider,symbol,timeframe};mem.set(key,{at:now(),value:wrapped});await kvPut(env,key,wrapped,ttlMs);return {...wrapped,cache:'miss'};}
export function evidenceEnvelope({market,symbol,quote,candles={},context={},source=[]}){if(!verifiedQuote(quote,market))throw new Error('V11_QUOTE_NOT_VERIFIED_FRESH');return {version:'V11',market,symbol,quote,candles,context,source,createdAt:Date.now()};}
