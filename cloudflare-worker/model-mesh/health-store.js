import {PROVIDER_FAILURE_CATEGORIES,freeOnlyEligible} from './contracts.js';

export const MODEL_HEALTH_STATES=Object.freeze(['CONFIGURED','LIVE_HEALTHY','DEGRADED','COOLDOWN','QUARANTINED','NOT_ELIGIBLE']);
const PREFIX='brain:model-mesh:health:v1:';
const LIVE_TTL_MS=30*60*1000,DEGRADED_TTL_MS=5*60*1000,COOLDOWN_TTL_MS=5*60*1000,QUARANTINE_TTL_MS=6*60*60*1000;
const HEALTH_CATEGORIES=new Set([...PROVIDER_FAILURE_CATEGORIES,'FREE_ONLY_POLICY','NO_HEALTH_STORE','NO_LIVE_EVIDENCE','HEALTH_STORE_UNAVAILABLE','MODEL_FINGERPRINT_MISMATCH','SOURCE_REVISION_MISMATCH','STALE_EVIDENCE','CREDENTIAL_OR_BINDING_MISSING','SELECTION_POLICY','KV_PROPAGATION_PENDING']);

const hex=bytes=>[...new Uint8Array(bytes)].map(value=>value.toString(16).padStart(2,'0')).join('');
const iso=ms=>new Date(ms).toISOString();
export async function modelFingerprint(model){
  const identity=JSON.stringify([String(model?.provider_id||''),String(model?.model_id||''),String(model?.model_family||''),String(model?.model_variant||''),String(model?.endpoint_family||'')]);
  return hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(identity)));
}
export function healthKey(model,fingerprint){return `${PREFIX}${String(model?.provider_id||'unknown').replace(/[^a-z0-9_-]/gi,'_')}:${fingerprint}`;}

function baseState(model){return freeOnlyEligible(model)?'CONFIGURED':'NOT_ELIGIBLE';}
function safeRecord(value){
  if(!value||typeof value!=='object'||value.schemaVersion!==1||!MODEL_HEALTH_STATES.includes(value.state))return null;
  return {
    schemaVersion:1,providerId:String(value.providerId||''),modelId:String(value.modelId||''),fingerprint:String(value.fingerprint||''),sourceSha:String(value.sourceSha||''),
    state:value.state,category:value.category?(HEALTH_CATEGORIES.has(String(value.category))?String(value.category):'UNKNOWN_SANITIZED'):null,observedAt:String(value.observedAt||''),expiresAt:String(value.expiresAt||''),latencyMs:Number.isFinite(value.latencyMs)?Math.max(0,Math.round(value.latencyMs)):null,
    consecutiveFailures:Number.isInteger(value.consecutiveFailures)?Math.max(0,value.consecutiveFailures):0,cooldownUntil:value.cooldownUntil?String(value.cooldownUntil):null,
  };
}

export async function readModelHealth(kv,model,{sourceSha='',nowMs=Date.now()}={}){
  if(!freeOnlyEligible(model))return {state:'NOT_ELIGIBLE',category:'FREE_ONLY_POLICY'};
  if(!kv||typeof kv.get!=='function')return {state:'CONFIGURED',category:'NO_HEALTH_STORE'};
  const fingerprint=await modelFingerprint(model),key=healthKey(model,fingerprint);
  let parsed=null;
  try{const raw=await kv.get(key);if(raw)parsed=safeRecord(JSON.parse(raw));}catch{return {state:'DEGRADED',category:'HEALTH_STORE_UNAVAILABLE'};}
  if(!parsed)return {state:'CONFIGURED',category:'NO_LIVE_EVIDENCE',fingerprint};
  if(parsed.fingerprint!==fingerprint)return {state:'DEGRADED',category:'MODEL_FINGERPRINT_MISMATCH',fingerprint};
  if(sourceSha&&parsed.sourceSha!==sourceSha)return {...parsed,state:'DEGRADED',category:'SOURCE_REVISION_MISMATCH'};
  if(!Number.isFinite(Date.parse(parsed.expiresAt))||Date.parse(parsed.expiresAt)<=nowMs)return {...parsed,state:'DEGRADED',category:'STALE_EVIDENCE'};
  return parsed;
}

// A provider is only removed from the pool for six hours once the failure has
// proven persistent. A single transient 401/403/404 -- a provider-side blip, a
// momentary auth propagation delay -- must cost minutes, not a working day.
// 402 and a price that rose above zero are the two exceptions: both mean the
// next request would be billable, so the model leaves the pool immediately
// rather than after a second confirming failure. Everything else still gets
// the benefit of the doubt, because a transient blip must cost minutes.
export const QUARANTINE_FAILURE_THRESHOLD=Object.freeze({AUTH_FAILED:2,MODEL_NOT_FOUND:3,MODEL_GONE:3,FREE_ENTITLEMENT_INVALID:1,PRICING_CHANGED:1});

const MIN_COOLDOWN_MS=30*1000,MAX_COOLDOWN_MS=60*60*1000;

/**
 * Resolve how long a rate-limited provider must rest.
 * The provider's own Retry-After / reset header wins over our fixed default,
 * as `policy.yaml` quota.respect_provider_reset / use_runtime_headers_first
 * require: retrying sooner burns free quota, retrying later wastes capacity.
 */
export function resolveCooldownMs(probe,nowMs=Date.now()){
  const retryAfterSeconds=Number(probe?.retryAfter);
  if(Number.isFinite(retryAfterSeconds)&&retryAfterSeconds>0)return clampCooldown(retryAfterSeconds*1000);
  const retryAfterDate=probe?.retryAfter?Date.parse(String(probe.retryAfter)):NaN;
  if(Number.isFinite(retryAfterDate)&&retryAfterDate>nowMs)return clampCooldown(retryAfterDate-nowMs);
  const resetAtMs=probe?.resetAt?Date.parse(String(probe.resetAt)):NaN;
  if(Number.isFinite(resetAtMs)&&resetAtMs>nowMs)return clampCooldown(resetAtMs-nowMs);
  const resetSeconds=Number(probe?.resetAt);
  if(Number.isFinite(resetSeconds)&&resetSeconds>0&&resetSeconds<MAX_COOLDOWN_MS/1000)return clampCooldown(resetSeconds*1000);
  return COOLDOWN_TTL_MS;
}
function clampCooldown(ms){return Math.min(MAX_COOLDOWN_MS,Math.max(MIN_COOLDOWN_MS,Math.round(ms)));}

function stateForProbe(probe,previousFailures=0,nowMs=Date.now()){
  if(probe?.ok===true)return {state:'LIVE_HEALTHY',ttlMs:LIVE_TTL_MS,category:null};
  const category=PROVIDER_FAILURE_CATEGORIES.includes(String(probe?.category||''))?String(probe.category):'UNKNOWN_SANITIZED';
  const failures=Math.max(0,Number(previousFailures)||0)+1;
  const threshold=QUARANTINE_FAILURE_THRESHOLD[category];
  if(threshold!==undefined){
    // Below the threshold the provider is merely DEGRADED, so the next probe
    // can restore it within minutes instead of six hours.
    if(failures<threshold)return {state:'DEGRADED',ttlMs:DEGRADED_TTL_MS,category};
    return {state:'QUARANTINED',ttlMs:QUARANTINE_TTL_MS,category};
  }
  if(category==='RATE_LIMITED')return {state:'COOLDOWN',ttlMs:resolveCooldownMs(probe,nowMs),category};
  return {state:'DEGRADED',ttlMs:DEGRADED_TTL_MS,category};
}

export async function writeProbeHealth(kv,model,probe,{sourceSha='',nowMs=Date.now(),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms)),verifyAttempts=2}={}){
  if(!freeOnlyEligible(model))return {state:'NOT_ELIGIBLE',category:'FREE_ONLY_POLICY'};
  const fingerprint=await modelFingerprint(model);
  const previous=await readModelHealth(kv,model,{sourceSha,nowMs});
  const previousFailures=Math.max(0,Number(previous?.consecutiveFailures)||0);
  const transition=stateForProbe(probe,previousFailures,nowMs),expiresMs=nowMs+transition.ttlMs;
  const consecutiveFailures=probe?.ok===true?0:previousFailures+1;
  const record=safeRecord({schemaVersion:1,providerId:model.provider_id,modelId:model.model_id,fingerprint,sourceSha,state:transition.state,category:transition.category,observedAt:iso(nowMs),expiresAt:iso(expiresMs),latencyMs:Number(probe?.latencyMs),consecutiveFailures,cooldownUntil:transition.state==='COOLDOWN'?iso(expiresMs):null});
  if(!kv||typeof kv.put!=='function')return {...record,persisted:false};
  const key=healthKey(model,fingerprint),serialized=JSON.stringify(record);
  try{await kv.put(key,serialized,{expirationTtl:Math.max(60,Math.ceil((transition.ttlMs+60*60*1000)/1000))});}catch{return {...record,persisted:false,storeCategory:'HEALTH_STORE_UNAVAILABLE'};}
  // A resolved kv.put IS the durability guarantee. Workers KV is eventually
  // consistent and caches reads at the edge, so a read-back moments later can
  // legitimately miss a write that did land -- previously that made the deploy
  // canary (which requires evidencePersisted) fail for no real reason.
  // Read-back is kept only as an optional, non-authoritative freshness signal.
  let readBack='unverified';
  for(let attempt=0;attempt<Math.max(0,verifyAttempts);attempt+=1){
    try{if(await kv.get(key)===serialized){readBack='confirmed';break;}}catch{readBack='unavailable';break;}
    if(attempt+1<verifyAttempts)await delay(25*(attempt+1));
  }
  return {...record,persisted:true,readBack};
}

export async function recordModelExecutionHealth(kv,model,result,options={}){
  const nowMs=options.nowMs??Date.now(),sourceSha=options.sourceSha||'';
  if(result?.ok===true){const current=await readModelHealth(kv,model,{sourceSha,nowMs});return {...current,persisted:false,storeCategory:'SCHEDULED_PROBE_OWNS_SUCCESS_REFRESH'};}
  return writeProbeHealth(kv,model,result,{...options,nowMs,sourceSha});
}
