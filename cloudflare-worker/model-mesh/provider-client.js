import {callOpenAICompatible} from './providers/openai-compatible.js';
import {callGemini} from './providers/gemini.js';
import {callCloudflareAI} from './providers/cloudflare-ai.js';
import {selectModelWorkers} from './selector.js';
import {classifyProviderFailure,sanitizeDataClass,selectionCandidate} from './contracts.js';
import {applyCapabilityEvidence,enabledHardCapabilities} from './capability-evidence.js';
import {MODEL_MESH_BINDINGS} from '../generated/model-mesh-bindings.js';
import {readModelHealth,recordModelExecutionHealth,writeProbeHealth} from './health-store.js';
import {providerRuntimeStatus,resolveLiveModels} from './runtime-health.js';
import {timingSafeToken} from './auth.js';
import {scheduleSelfHeal} from './self-heal.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const nowIso=()=>new Date().toISOString();
const redact=value=>String(value??'').replace(/sk-[A-Za-z0-9_-]+/g,'[REDACTED]').replace(/Bearer\s+\S+/gi,'Bearer [REDACTED]');

export function resolveRuntimeWorker(worker){
  const binding=MODEL_MESH_BINDINGS?.[worker?.provider_id];
  if(!binding||binding.enabled!==true)return null;
  return {...worker,endpoint_family:binding.endpoint_family,endpoint_url:binding.endpoint_url,secret_name:binding.secret_name,account_id_env:binding.account_id_env||null};
}

async function callProvider(worker,env,messages,fetchImpl){
  const secretName=String(worker.secret_name||'');const apiKey=secretName?env?.[secretName]:undefined;
  if(!apiKey)return {ok:false,status:0,category:'UNKNOWN_SANITIZED'};
  if(worker.endpoint_family==='gemini')return callGemini({baseUrl:worker.endpoint_url,apiKey,model:worker.model_id,messages,fetchImpl});
  if(worker.endpoint_family==='cloudflare_ai'){
    const accountId=env?.[worker.account_id_env||'CLOUDFLARE_ACCOUNT_ID'];
    if(!accountId)return {ok:false,status:0,category:'UNKNOWN_SANITIZED'};
    return callCloudflareAI({accountId,apiKey,model:worker.model_id,messages,fetchImpl});
  }
  return callOpenAICompatible({baseUrl:worker.endpoint_url,apiKey,model:worker.model_id,messages,fetchImpl});
}

function normalizedResult(worker,route,startedAt,completedAt,result){
  const started=Date.parse(startedAt),completed=Date.parse(completedAt);
  return {task_id:`mesh-${route.primarySkill}`,subtask_id:`${worker.provider_id}:${worker.model_id}`,input_hash:null,authority_revision:route.sourceSha||null,primary_skill_id:route.primarySkill,capsule_hash:route.capsuleHash||null,domain_label:route.domain||'core',worker_role:worker.worker_role||'maker',provider_id:worker.provider_id,model_id:worker.model_id,model_family:worker.model_family,started_at:startedAt,completed_at:completedAt,latency_ms:Number.isFinite(completed-started)?Math.max(0,completed-started):0,quota_state:result.status===429?'COOLDOWN_QUOTA':'AVAILABLE',source_refs:[],verification_status:result.ok?'unverified_model_output':'provider_error',text:result.ok?redact(result.text):undefined,error_category:result.ok?undefined:(result.category||classifyProviderFailure({status:result.status})),retry_after:result.status===429?result.retryAfter||null:undefined,reset_at:result.status===429?result.resetAt||null:undefined};
}

export async function providerConfigurationStatus(modelSnapshot,env={}){return providerRuntimeStatus(modelSnapshot,env);}

// How many models of one provider a single probe round may try before the
// provider is reported unavailable. A mixed catalog holds paid and free models
// at once and a listing is not liveness, so one 402 or one retired id must cost
// the model, never the provider -- the bound is what keeps that from becoming
// an unbounded sweep.
const DEFAULT_MAX_CANDIDATES_PER_PROVIDER=3;
// Failures that say "this model is wrong", not "this provider is unusable".
// Trying the provider's next candidate is the whole point of admitting several.
const MODEL_SCOPED_FAILURES=new Set(['MODEL_NOT_FOUND','MODEL_GONE','FREE_ENTITLEMENT_INVALID','REQUEST_INVALID']);

export function createProviderProbe({fetchImpl=fetch,maxParallel=4,maxCandidatesPerProvider=DEFAULT_MAX_CANDIDATES_PER_PROVIDER}={}){
  return async function probeProviders(env,{modelSnapshot}={}){
    // Group by provider so each provider gets a bounded candidate list rather
    // than a single guessed model id.
    const byProvider=new Map();
    for(const model of modelSnapshot?.models||[]){
      if(!selectionCandidate(model))continue;
      if(!byProvider.has(model.provider_id))byProvider.set(model.provider_id,[]);
      const bucket=byProvider.get(model.provider_id);
      if(bucket.length<Math.max(1,Number(maxCandidatesPerProvider)||DEFAULT_MAX_CANDIDATES_PER_PROVIDER))bucket.push(model);
    }
    const providerCandidates=[...byProvider.values()];
    const probeModel=async model=>{
      const started=Date.now();const worker=resolveRuntimeWorker(model);
      if(!worker)return {providerId:model.provider_id,modelId:model.model_id,configured:false,ok:false,status:0,latencyMs:Date.now()-started,category:'UNKNOWN_SANITIZED',state:'CONFIGURED'};
      const configured=Boolean(worker.secret_name&&env?.[worker.secret_name])&&Boolean(!worker.account_id_env||env?.[worker.account_id_env]);
      if(!configured)return {providerId:model.provider_id,modelId:model.model_id,configured:false,ok:false,status:0,latencyMs:Date.now()-started,category:'UNKNOWN_SANITIZED',state:'CONFIGURED'};

      const existing=await readModelHealth(env?.TRADING_STATE,model,{sourceSha:modelSnapshot?.source_sha||'',nowMs:started});
      const cooldownUntilMs=existing?.cooldownUntil?Date.parse(String(existing.cooldownUntil)):NaN;
      if(existing?.state==='COOLDOWN'&&Number.isFinite(cooldownUntilMs)&&cooldownUntilMs>started){
        return {providerId:model.provider_id,modelId:model.model_id,configured:true,ok:false,status:0,latencyMs:0,
          category:existing.category||'RATE_LIMITED',state:'COOLDOWN',evidencePersisted:true,skipped:'quota_cooldown_active',
          resetAt:existing.cooldownUntil};
      }

      const result=await callProvider(worker,env,[{role:'user',content:'Reply with OK only.'}],fetchImpl);
      const latencyMs=Math.max(0,Date.now()-started),category=result.ok?null:(result.category||classifyProviderFailure({status:result.status}));
      const health=await writeProbeHealth(env?.TRADING_STATE,model,{ok:Boolean(result.ok),category,latencyMs,retryAfter:result.retryAfter,resetAt:result.resetAt},{sourceSha:modelSnapshot?.source_sha||''});
      const row={providerId:model.provider_id,modelId:model.model_id,configured:true,ok:Boolean(result.ok),status:Number(result.status||0),latencyMs,category,state:health.state,evidencePersisted:Boolean(health.persisted)};
      if(result.status===429){row.retryAfter=result.retryAfter||null;row.resetAt=result.resetAt||null;}
      return row;
    };
    // Probe a provider's candidates in order and stop at the first one that
    // completes. Every attempt is still recorded, so a 402 on one model is
    // evidence about that model and never about the provider as a whole.
    const probeProvider=async candidates=>{
      const attempts=[];
      for(const model of candidates){
        const row=await probeModel(model);
        attempts.push(row);
        if(row.ok===true)break;
        if(row.skipped)break;
        if(!row.configured)break;
        if(!MODEL_SCOPED_FAILURES.has(String(row.category||'')))break;
      }
      const chosen=attempts.find(row=>row.ok===true)||attempts[attempts.length-1];
      return {
        ...chosen,
        candidatesProbed:attempts.length,
        candidatesAvailable:candidates.length,
        attemptedModelIds:attempts.map(row=>row.modelId),
        // Recorded so an operator can tell "no free model left here" from
        // "we never looked past the first id".
        providerExhausted:attempts.length>0&&!attempts.some(row=>row.ok===true)&&attempts.length===candidates.length,
      };
    };
    const results=[];const width=Math.max(1,Math.min(4,Number(maxParallel)||4));
    for(let index=0;index<providerCandidates.length;index+=width){
      const batch=providerCandidates.slice(index,index+width);
      const settled=await Promise.allSettled(batch.map(probeProvider));
      settled.forEach((item,offset)=>results.push(item.status==='fulfilled'?item.value:{providerId:batch[offset][0].provider_id,modelId:batch[offset][0].model_id,configured:false,ok:false,status:0,latencyMs:0,category:'UNKNOWN_SANITIZED',state:'DEGRADED',evidencePersisted:false,candidatesProbed:0,candidatesAvailable:batch[offset].length,attemptedModelIds:[],providerExhausted:false}));
    }
    return {ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,probedProviderCount:results.length,successfulProviderCount:results.filter(row=>row.ok).length,results};
  };
}

export function createMeshExecutor({fetchImpl=fetch,selfHealProbe=null}={}){
  return async function executeWorkers(request,env,{skillSnapshot,modelSnapshot,activeIndex,routeSkill,ctx}){
    if(String(env?.MODEL_MESH_EXECUTION_ENABLED||'0')!=='1')return json({ok:false,error:'mesh_execution_disabled'},503);
    const expected=String(env?.MODEL_MESH_EXECUTION_TOKEN||'');const supplied=String(request.headers.get('x-model-mesh-token')||'');
    if(!await timingSafeToken(expected,supplied))return json({ok:false,error:'unauthorized'},401);
    let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
    if(typeof body?.text!=='string'||!body.text.trim())return json({ok:false,error:'invalid_text'},400);
    const dataClass=sanitizeDataClass(body.dataClass);if(dataClass==='SECRET')return json({ok:false,error:'secret_external_mesh_forbidden'},403);
    const route=routeSkill({text:body.text});if(route.profile==='FAST')return json({ok:false,error:'fast_profile_external_execution_forbidden'},409);
    if(!activeIndex||activeIndex.source_sha!==modelSnapshot?.source_sha)return json({ok:false,error:'model_mesh_source_sha_mismatch'},503);
    const capsule=skillSnapshot?.capsules?.[route.primarySkill]||{};
    const domain=route.domain||capsule.domain||'core';
    const evidenceSnapshot={...modelSnapshot,models:applyCapabilityEvidence(modelSnapshot?.models,activeIndex)};
    const liveModels=await resolveLiveModels(evidenceSnapshot,env);
    const hardCapabilities=enabledHardCapabilities(activeIndex,domain);
    const selected=selectModelWorkers({profile:route.profile,domain,dataClass,models:liveModels,hardCapabilities});
    if(!selected.length){
      scheduleSelfHeal({env,ctx,probeProviders:selfHealProbe,modelSnapshot});
      return json({ok:false,error:'no_eligible_free_worker'},503);
    }
    const messages=[{role:'user',content:body.text}];
    const run=async selectedWorker=>{
      const startedAt=nowIso();const worker=resolveRuntimeWorker(selectedWorker);
      const result=worker?await callProvider(worker,env,messages,fetchImpl):{ok:false,status:0,category:'UNKNOWN_SANITIZED'};
      const completedAt=nowIso(),normalized=normalizedResult(worker||selectedWorker,route,startedAt,completedAt,result);
      const persist=recordModelExecutionHealth(env?.TRADING_STATE,selectedWorker,{ok:Boolean(result.ok),category:result.category,latencyMs:normalized.latency_ms,retryAfter:result.retryAfter,resetAt:result.resetAt},{sourceSha:modelSnapshot?.source_sha||''});
      await persist;
      return normalized;
    };
    const settled=await Promise.allSettled(selected.map(run));
    const results=settled.map((item,index)=>item.status==='fulfilled'?item.value:normalizedResult(selected[index],route,nowIso(),nowIso(),{ok:false,status:0,error:'worker_failure'}));
    return json({ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,workerCount:results.length,results});
  };
}
