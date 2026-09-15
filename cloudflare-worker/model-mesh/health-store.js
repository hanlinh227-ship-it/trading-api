import {PROVIDER_FAILURE_CATEGORIES,freeOnlyEligible} from './contracts.js';

export const MODEL_HEALTH_STATES=Object.freeze(['CONFIGURED','LIVE_HEALTHY','DEGRADED','COOLDOWN','QUARANTINED','NOT_ELIGIBLE']);
const PREFIX='brain:model-mesh:health:v1:';
const LIVE_TTL_MS=30*60*1000,DEGRADED_TTL_MS=5*60*1000,COOLDOWN_TTL_MS=5*60*1000,QUARANTINE_TTL_MS=6*60*60*1000;
const HEALTH_CATEGORIES=new Set([...PROVIDER_FAILURE_CATEGORIES,'FREE_ONLY_POLICY','NO_HEALTH_STORE','NO_LIVE_EVIDENCE','HEALTH_STORE_UNAVAILABLE','MODEL_FINGERPRINT_MISMATCH','SOURCE_REVISION_MISMATCH','STALE_EVIDENCE','CREDENTIAL_OR_BINDING_MISSING']);

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

function stateForProbe(probe){
  if(probe?.ok===true)return {state:'LIVE_HEALTHY',ttlMs:LIVE_TTL_MS,category:null};
  const category=PROVIDER_FAILURE_CATEGORIES.includes(String(probe?.category||''))?String(probe.category):'UNKNOWN_SANITIZED';
  if(['AUTH_FAILED','MODEL_NOT_FOUND','FREE_ENTITLEMENT_INVALID'].includes(category))return {state:'QUARANTINED',ttlMs:QUARANTINE_TTL_MS,category};
  if(category==='RATE_LIMITED')return {state:'COOLDOWN',ttlMs:COOLDOWN_TTL_MS,category};
  return {state:'DEGRADED',ttlMs:DEGRADED_TTL_MS,category};
}

export async function writeProbeHealth(kv,model,probe,{sourceSha='',nowMs=Date.now(),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms)),verifyAttempts=2}={}){
  if(!freeOnlyEligible(model))return {state:'NOT_ELIGIBLE',category:'FREE_ONLY_POLICY'};
  const fingerprint=await modelFingerprint(model),transition=stateForProbe(probe),expiresMs=nowMs+transition.ttlMs;
  const previous=await readModelHealth(kv,model,{sourceSha,nowMs});
  const consecutiveFailures=probe?.ok===true?0:Math.max(0,Number(previous?.consecutiveFailures)||0)+1;
  const record=safeRecord({schemaVersion:1,providerId:model.provider_id,modelId:model.model_id,fingerprint,sourceSha,state:transition.state,category:transition.category,observedAt:iso(nowMs),expiresAt:iso(expiresMs),latencyMs:Number(probe?.latencyMs),consecutiveFailures,cooldownUntil:transition.state==='COOLDOWN'?iso(expiresMs):null});
  if(!kv||typeof kv.put!=='function')return {...record,persisted:false};
  const key=healthKey(model,fingerprint),serialized=JSON.stringify(record);
  try{await kv.put(key,serialized,{expirationTtl:Math.max(60,Math.ceil((transition.ttlMs+60*60*1000)/1000))});}catch{return {...record,persisted:false,storeCategory:'HEALTH_STORE_UNAVAILABLE'};}
  for(let attempt=0;attempt<Math.max(1,verifyAttempts);attempt+=1){
    try{if(await kv.get(key)===serialized)return {...record,persisted:true};}catch{}
    if(attempt+1<verifyAttempts)await delay(25*(attempt+1));
  }
  return {...record,persisted:false,storeCategory:'KV_PROPAGATION_PENDING'};
}

export async function recordModelExecutionHealth(kv,model,result,options={}){
  const nowMs=options.nowMs??Date.now(),sourceSha=options.sourceSha||'';
  if(result?.ok===true){const current=await readModelHealth(kv,model,{sourceSha,nowMs});return {...current,persisted:false,storeCategory:'SCHEDULED_PROBE_OWNS_SUCCESS_REFRESH'};}
  return writeProbeHealth(kv,model,result,{...options,nowMs,sourceSha});
}
