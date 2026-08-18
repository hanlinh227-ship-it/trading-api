import {getHyroProfile,getHyroTelemetry,getHyroControl,setHyroPaused,hyroDynamicRiskView,cancelHyroPending} from "./hyro-execution.js";
import {runHyroAutoCycle,getHyroRuntime} from "./hyro-runtime.js";

const GLOBAL_MIRROR_KEY="v771815:hyro:anti_mirror";
const B_PREFIX="v771815:hyro:B:";
const PROFILE_KEY="v7717:hyro:profile";
const ACCOUNT_IDS=["A","B"];
const now=()=>Date.now();
const kvJson=async(kv,key,fallback=null)=>{try{return await kv?.get(key,"json")??fallback;}catch{return fallback;}};
const putJson=async(kv,key,v)=>{if(kv)await kv.put(key,JSON.stringify(v));};

function scopedKv(base,prefix){
  return {
    get:(key,...args)=>base?.get(prefix+key,...args),
    put:(key,value,...args)=>base?.put(prefix+key,value,...args),
    delete:(key)=>base?.delete(prefix+key),
    list:async(opts={})=>{const o={...opts,prefix:prefix+String(opts.prefix||"")},r=await base?.list(o);if(!r)return r;return {...r,keys:(r.keys||[]).map(k=>({...k,name:String(k.name||"").slice(prefix.length)}))};}
  };
}

export function hyroAccountEnv(env,id="A"){
  const account=String(id||"A").toUpperCase()==="B"?"B":"A";
  if(account==="A")return new Proxy(env,{get(t,k){if(k==="HYRO_ACCOUNT_ID")return "A";if(k==="HYRO_ACCOUNT_LABEL")return "TK1";return t[k];}});
  const kv=scopedKv(env.TRADING_STATE,B_PREFIX);
  return new Proxy(env,{get(t,k){
    if(k==="TRADING_STATE")return kv;
    if(k==="HYRO_ACCOUNT_ID")return "B";
    if(k==="HYRO_ACCOUNT_LABEL")return "TK2";
    if(k==="HYRO_BYBIT_API_KEY")return t.HYRO_B_BYBIT_API_KEY;
    if(k==="HYRO_BYBIT_API_SECRET")return t.HYRO_B_BYBIT_API_SECRET;
    if(k==="HYRO_BYBIT_LIVE_API_KEY")return t.HYRO_B_BYBIT_LIVE_API_KEY;
    if(k==="HYRO_BYBIT_LIVE_API_SECRET")return t.HYRO_B_BYBIT_LIVE_API_SECRET;
    if(k==="HYRO_BYBIT_MODE")return t.HYRO_B_BYBIT_MODE||"DEMO";
    if(k==="HYRO_AUTO_EXECUTION")return t.HYRO_B_AUTO_EXECUTION||"false";
    return t[k];
  }});
}

export async function ensureHyroBProfile(env){
  const b=hyroAccountEnv(env,"B"),existing=await getHyroProfile(b);if(existing)return existing;
  const a=await getHyroProfile(hyroAccountEnv(env,"A"));if(!a)return null;
  const cloned={...a,provider:"HYROTRADER",accountAlias:"B",connected:false,autoTrade:false,configuredAt:now(),clonedRulesFrom:"A"};
  await b.TRADING_STATE?.put(PROFILE_KEY,JSON.stringify(cloned));
  return cloned;
}

async function antiMirrorState(env){const x=await kvJson(env.TRADING_STATE,GLOBAL_MIRROR_KEY,{events:[]});const cutoff=now()-6*60*60*1000;return {events:(x?.events||[]).filter(e=>Number(e.at)>=cutoff).slice(-30)};}
async function recordExecution(env,id,cycle){if(!cycle?.executed||!cycle?.execution)return;const s=await antiMirrorState(env),o=cycle.execution;s.events.push({account:id,symbol:String(o.symbol||"").toUpperCase(),side:String(o.side||"").toUpperCase(),at:now()});await putJson(env.TRADING_STATE,GLOBAL_MIRROR_KEY,{events:s.events.slice(-30),updatedAt:now()});}
export async function antiMirrorBlocked(env,id){const s=await antiMirrorState(env);return s.events.filter(e=>e.account!==id).map(e=>`${e.symbol}:${e.side}`);}

export async function runHyroAccountCycle(env,id,opts={}){
  const account=id==="B"?"B":"A";if(account==="B")await ensureHyroBProfile(env);
  const scoped=hyroAccountEnv(env,account),blocked=await antiMirrorBlocked(env,account),cycle=await runHyroAutoCycle(scoped,{...opts,accountId:account,excludedSignatures:blocked});
  await recordExecution(env,account,cycle);return cycle;
}

export async function hyroAccountSnapshot(env,id){
  const account=id==="B"?"B":"A";if(account==="B")await ensureHyroBProfile(env);const e=hyroAccountEnv(env,account),p=await getHyroProfile(e),c=await getHyroControl(e),t=await getHyroTelemetry(e),rt=await getHyroRuntime(e),r=p&&t?.connected?hyroDynamicRiskView(p,t):null;
  return {id:account,label:account==="A"?"TK1":"TK2",configured:!!p,profile:p,control:c,telemetry:t,runtime:rt,dynamicRisk:r,autoRequested:String(e.HYRO_AUTO_EXECUTION||"false").toLowerCase()==="true"};
}
export async function pauseHyroAccount(env,id,paused){const e=hyroAccountEnv(env,id);const c=await setHyroPaused(e,paused);if(paused)await cancelHyroPending(e).catch(()=>{});return c;}
export async function hyroHubSnapshot(env){const rows=[];for(const id of ACCOUNT_IDS)rows.push(await hyroAccountSnapshot(env,id));return rows;}
