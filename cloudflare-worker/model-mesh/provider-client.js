import {callOpenAICompatible} from './providers/openai-compatible.js';
import {callGemini} from './providers/gemini.js';
import {callCloudflareAI} from './providers/cloudflare-ai.js';
import {selectModelWorkers} from './selector.js';
import {sanitizeDataClass} from './contracts.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const nowIso=()=>new Date().toISOString();
const redact=value=>String(value??'').replace(/sk-[A-Za-z0-9_-]+/g,'[REDACTED]').replace(/Bearer\s+\S+/gi,'Bearer [REDACTED]');

async function callProvider(worker,env,messages,fetchImpl){
  const secretName=String(worker.secret_name||'');const apiKey=secretName?env?.[secretName]:undefined;
  if(!apiKey)return {ok:false,status:0,error:'provider_not_configured'};
  if(worker.endpoint_family==='gemini')return callGemini({baseUrl:worker.endpoint_url,apiKey,model:worker.model_id,messages,fetchImpl});
  if(worker.endpoint_family==='cloudflare_ai')return callCloudflareAI({accountId:env?.[worker.account_id_env||'CLOUDFLARE_ACCOUNT_ID'],apiKey,model:worker.model_id,messages,fetchImpl});
  return callOpenAICompatible({baseUrl:worker.endpoint_url,apiKey,model:worker.model_id,messages,fetchImpl});
}

function normalizedResult(worker,route,startedAt,completedAt,result){
  const started=Date.parse(startedAt),completed=Date.parse(completedAt);
  return {task_id:`mesh-${route.primarySkill}`,subtask_id:`${worker.provider_id}:${worker.model_id}`,input_hash:null,authority_revision:route.sourceSha||null,primary_skill_id:route.primarySkill,capsule_hash:route.capsuleHash||null,domain_label:route.domain||'core',worker_role:worker.worker_role||'maker',provider_id:worker.provider_id,model_id:worker.model_id,model_family:worker.model_family,started_at:startedAt,completed_at:completedAt,latency_ms:Number.isFinite(completed-started)?Math.max(0,completed-started):0,quota_state:result.status===429?'COOLDOWN_QUOTA':'AVAILABLE',source_refs:[],verification_status:result.ok?'unverified_model_output':'provider_error',text:result.ok?redact(result.text):undefined,error:result.ok?undefined:redact(result.error),retry_after:result.status===429?result.retryAfter||null:undefined,reset_at:result.status===429?result.resetAt||null:undefined};
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
    const workers=selectModelWorkers({profile:route.profile,domain:route.domain||capsule.domain||'core',dataClass,models:modelSnapshot?.models||[]});
    if(!workers.length)return json({ok:false,error:'no_eligible_free_worker'},503);
    const messages=[{role:'user',content:body.text}];
    const run=async worker=>{const startedAt=nowIso();const result=await callProvider(worker,env,messages,fetchImpl);const completedAt=nowIso();return normalizedResult(worker,route,startedAt,completedAt,result);};
    const settled=await Promise.allSettled(workers.map(run));
    const results=settled.map((item,index)=>item.status==='fulfilled'?item.value:normalizedResult(workers[index],route,nowIso(),nowIso(),{ok:false,status:0,error:'worker_failure'}));
    return json({ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,workerCount:results.length,results});
  };
}
