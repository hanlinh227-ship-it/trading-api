import fs from 'node:fs/promises';
import {callOpenAICompatible} from './model-mesh/providers/openai-compatible.js';
import {callGemini} from './model-mesh/providers/gemini.js';
import {callCloudflareAI} from './model-mesh/providers/cloudflare-ai.js';

const activePath=process.argv[2]||'../AI_SKILL_LIBRARY/v4/model_mesh/active.json';
const bindingsPath=process.argv[3]||'../AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json';
const probePath=process.argv[4]||'/tmp/free-ai-probe.json';
const contextPath=process.argv[5]||'/tmp/free-ai-context-bounded.txt';
const outputPath=process.argv[6]||'/tmp/free-ai-all-model-results.json';

const active=JSON.parse(await fs.readFile(new URL(activePath, import.meta.url),'utf8'));
const bindings=JSON.parse(await fs.readFile(new URL(bindingsPath, import.meta.url),'utf8')).bindings||{};
const probe=JSON.parse(await fs.readFile(probePath,'utf8'));
const context=await fs.readFile(contextPath,'utf8');

const allowedFreeStatuses=new Set(['recurring','account_specific','free_quota_hard_stop','temporary_zero_price']);
const eligible=(active.models||[]).filter(m=>
  m.registry_state!=='NOT_ELIGIBLE' &&
  m.usage_terms==='production_allowed' &&
  allowedFreeStatuses.has(m.free_status)
);
const liveKeys=new Set((probe.results||[]).filter(r=>r.ok===true&&r.state==='LIVE_HEALTHY').map(r=>r.providerId+'\u0000'+r.modelId));

const taskByProvider={
  groq:'Find the highest-leverage focused test gaps in the AI CORE integration. Return exact files/commands only; no architecture redesign.',
  cloudflare_workers_ai:'Scan for likely integration conflicts or stale assumptions between Front Door, Survival, Always-On, Redundancy and Storage Mesh. Return concise actionable findings.',
  openrouter:'Act as an independent code-quality reviewer for the current AI CORE closure context. Prioritize correctness, fail-closed behavior, and duplicated work. Return only concrete findings.',
  alibaba_model_studio:'Identify up to five independent mechanical tasks that can shorten AI CORE closure without touching shared authority or Storage Mesh files. Include exact allowed paths and verification.',
  nvidia_nim:'Look for edge cases that could make final readiness gates pass falsely. Return a compact canary checklist with exact subsystem references.',
  gemini_developer_api:'Check long-context consistency of the supplied project state and identify contradictions in readiness or ownership claims. Return only contradictions and required verification.',
  mistral:'Review the final integration sequencing and suggest the smallest safe follow-up actions. Do not propose redesign or broad refactors.'
};

function bindingFor(model){return bindings[model.provider_id]||null;}
function envValue(name){return name?process.env[name]:undefined;}
function redact(text){
  return String(text??'')
    .replace(/sk-[A-Za-z0-9_.-]+/g,'[REDACTED]')
    .replace(/Bearer\s+\S+/gi,'Bearer [REDACTED]')
    .slice(0,6000);
}
async function callModel(model){
  const binding=bindingFor(model);
  if(!binding||binding.enabled!==true)return {ok:false,error:'binding_unavailable'};
  if(!liveKeys.has(model.provider_id+'\u0000'+model.model_id))return {ok:false,skipped:'not_live_healthy'};
  const apiKey=envValue(binding.secret_name);
  if(!apiKey)return {ok:false,skipped:'credential_not_present'};
  const prompt=(taskByProvider[model.provider_id]||'Review the AI CORE integration context and return only concrete acceleration actions.')+
    '\n\nConstraints: GITHUB_BRAIN_V4 is sole Brain authority; task_router is sole routing authority; no merge/deploy/trading authority; public context only.\n\n'+context;
  const messages=[{role:'user',content:prompt}];
  let result;
  if(binding.endpoint_family==='gemini'){
    result=await callGemini({baseUrl:binding.endpoint_url,apiKey,model:model.model_id,messages,timeoutMs:90000});
  }else if(binding.endpoint_family==='cloudflare_ai'){
    const accountId=envValue(binding.account_id_env||'CLOUDFLARE_ACCOUNT_ID');
    if(!accountId)return {ok:false,skipped:'account_id_not_present'};
    result=await callCloudflareAI({accountId,apiKey,model:model.model_id,messages,timeoutMs:90000});
  }else{
    result=await callOpenAICompatible({baseUrl:binding.endpoint_url,apiKey,model:model.model_id,messages,timeoutMs:90000});
  }
  return {
    ok:Boolean(result?.ok),
    status:Number(result?.status||0),
    category:result?.category||null,
    text:result?.ok?redact(result.text):undefined,
    retryAfter:result?.retryAfter||null,
    resetAt:result?.resetAt||null
  };
}

const settled=await Promise.allSettled(eligible.map(async model=>({model,result:await callModel(model)})));
const rows=settled.map((item,index)=>{
  const model=eligible[index];
  if(item.status==='fulfilled')return {
    provider_id:model.provider_id,
    model_id:model.model_id,
    free_status:model.free_status,
    ...item.value.result
  };
  return {provider_id:model.provider_id,model_id:model.model_id,free_status:model.free_status,ok:false,error:'runner_failure'};
});
await fs.writeFile(outputPath,JSON.stringify({eligible_count:eligible.length,live_count:rows.filter(r=>r.ok).length,rows},null,2));
console.log('FREE_AI_ALL_MODELS_ELIGIBLE='+eligible.length);
console.log('FREE_AI_ALL_MODELS_LIVE_USED='+rows.filter(r=>r.ok).length);
for(const r of rows)console.log('FREE_AI_MODEL='+r.provider_id+'|'+r.model_id+'|'+(r.ok?'USED':(r.skipped||r.category||r.error||'FAILED')));
