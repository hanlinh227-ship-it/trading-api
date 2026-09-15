import {callOpenAICompatible} from './providers/openai-compatible.js';
import {callGemini} from './providers/gemini.js';
import {callCloudflareAI} from './providers/cloudflare-ai.js';
import {selectModelWorkers} from './selector.js';
import {sanitizeDataClass} from './contracts.js';
import {MODEL_MESH_BINDINGS} from '../generated/model-mesh-bindings.js';

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
  if(!apiKey)return {ok:false,status:0,error:'provider_not_configured'};
  if(worker.endpoint_family==='gemini')return callGemini({baseUrl:worker.endpoint_url,apiKey,model:worker.model_id,messages,fetchImpl});
  if(worker.endpoint_family==='cloudflare_ai'){
    const accountId=env?.[worker.account_id_env||'CLOUDFLARE_ACCOUNT_ID'];
    if(!accountId)return {ok:false,status:0,error:'provider_account_not_configured'};
    return callCloudflareAI({accountId,apiKey,model:worker.model_id,messages,fetchImpl});
  }
  return callOpenAICompatible({baseUrl:worker.endpoint_url,apiKey,model:worker.model_id,messages,fetchImpl});
}

function normalizedResult(worker,route,startedAt,completedAt,result){
  const started=Date.parse(startedAt),completed=Date.parse(completedAt);
  return {task_id:`mesh-${route.primarySkill}`,subtask_id:`${worker.provider_id}:${worker.model_id}`,input_hash:null,authority_revision:route.sourceSha||null,primary_skill_id:route.primarySkill,capsule_hash:route.capsuleHash||null,domain_label:route.domain||'core',worker_role:worker.worker_role||'maker',provider_id:worker.provider_id,model_id:worker.model_id,model_family:worker.model_family,started_at:startedAt,completed_at:completedAt,latency_ms:Number.isFinite(completed-started)?Math.max(0,completed-started):0,quota_state:result.status===429?'COOLDOWN_QUOTA':'AVAILABLE',source_refs:[],verification_status:result.ok?'unverified_model_output':'provider_error',text:result.ok?redact(result.text):undefined,error:result.ok?undefined:redact(result.error),retry_after:result.status===429?result.retryAfter||null:undefined,reset_at:result.status===429?result.resetAt||null:undefined};
}

export function providerConfigurationStatus(modelSnapshot,env={}){
  const counts=new Map();
  for(const model of modelSnapshot?.models||[])counts.set(model.provider_id,(counts.get(model.provider_id)||0)+1);
  return Object.entries(MODEL_MESH_BINDINGS).map(([providerId,binding])=>({
    providerId,
    bindingEnabled:binding.enabled===true,
    configured:Boolean(binding.secret_name&&env?.[binding.secret_name])&&Boolean(!binding.account_id_env||env?.[binding.account_id_env]),
    eligibleModelCount:counts.get(providerId)||0,
    active:Boolean(binding.enabled===true&&counts.get(providerId)>0&&binding.secret_name&&env?.[binding.secret_name]&&(!binding.account_id_env||env?.[binding.account_id_env])),
  })).sort((a,b)=>a.providerId.localeCompare(b.providerId));
}

export function createMeshExecutor({fetchImpl=fetch}={}){
  return async function executeWorkers(request,env,{skillSnapshot,modelSnapshot,routeSkill}){
    if(String(env?.MODEL_MESH_EXECUTION_ENABLED||'0')!=='1')return json({ok:false,error:'mesh_execution_disabled'},503);
    const expected=String(env?.MODEL_MESH_EXECUTION_TOKEN||'');const supplied=String(request.headers.get('x-model-mesh-token')||'');
    if(!expected||!supplied||supplied!==expected)return json({ok:false,error:'unauthorized'},401);
    let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
    if(typeof body?.text!=='string'||!body.text.trim())return json({ok:false,error:'invalid_text'},400);
    const dataClass=sanitizeDataClass(body.dataClass);if(dataClass==='SECRET')return json({ok:false,error:'secret_external_mesh_forbidden'},403);
    const route=routeSkill({text:body.text});if(route.profile==='FAST')return json({ok:false,error:'fast_profile_external_execution_forbidden'},409);
    const capsule=skillSnapshot?.capsules?.[route.primarySkill]||{};
    const selected=selectModelWorkers({profile:route.profile,domain:route.domain||capsule.domain||'core',dataClass,models:modelSnapshot?.models||[]});
    if(!selected.length)return json({ok:false,error:'no_eligible_free_worker'},503);
    const messages=[{role:'user',content:body.text}];
    const run=async selectedWorker=>{
      const startedAt=nowIso();const worker=resolveRuntimeWorker(selectedWorker);
      const result=worker?await callProvider(worker,env,messages,fetchImpl):{ok:false,status:0,error:'provider_binding_not_configured'};
      const completedAt=nowIso();return normalizedResult(worker||selectedWorker,route,startedAt,completedAt,result);
    };
    const settled=await Promise.allSettled(selected.map(run));
    const results=settled.map((item,index)=>item.status==='fulfilled'?item.value:normalizedResult(selected[index],route,nowIso(),nowIso(),{ok:false,status:0,error:'worker_failure'}));
    return json({ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,workerCount:results.length,results});
  };
}
