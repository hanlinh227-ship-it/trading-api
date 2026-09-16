import {MODEL_MESH_BINDINGS} from '../generated/model-mesh-bindings.js';
import {freeOnlyEligible,selectionCandidate} from './contracts.js';
import {readModelHealth} from './health-store.js';

export function providerConfigured(model,env={}){
  const binding=MODEL_MESH_BINDINGS?.[model?.provider_id];
  return Boolean(binding?.enabled===true&&binding.secret_name&&env?.[binding.secret_name]&&(!binding.account_id_env||env?.[binding.account_id_env]));
}

export async function resolveLiveModels(modelSnapshot,env={},options={}){
  return Promise.all((modelSnapshot?.models||[]).map(async model=>{
    if(!selectionCandidate(model,'PUBLIC',{nowMs:options.nowMs??Date.now()}))return {...model,runtimeState:'NOT_ELIGIBLE',runtimeCategory:freeOnlyEligible(model,{nowMs:options.nowMs??Date.now()})?'SELECTION_POLICY':'FREE_ONLY_POLICY',health:'unavailable',configured:providerConfigured(model,env)};
    const configured=providerConfigured(model,env);
    if(!configured)return {...model,runtimeState:'CONFIGURED',runtimeCategory:'CREDENTIAL_OR_BINDING_MISSING',health:'unavailable',configured:false};
    const evidence=await readModelHealth(env?.TRADING_STATE,model,{sourceSha:modelSnapshot?.source_sha||'',nowMs:options.nowMs});
    return {...model,runtimeState:evidence.state,runtimeCategory:evidence.category||null,health:evidence.state==='LIVE_HEALTHY'?'healthy':'unavailable',configured:true,liveEvidence:evidence};
  }));
}

export async function providerRuntimeStatus(modelSnapshot,env={},options={}){
  const models=await resolveLiveModels(modelSnapshot,env,options),byProvider=new Map();
  for(const [providerId,binding] of Object.entries(MODEL_MESH_BINDINGS))byProvider.set(providerId,{providerId,bindingEnabled:binding.enabled===true,configured:false,eligibleModelCount:0,liveHealthyModelCount:0,active:false,states:[]});
  for(const model of models){
    if(!byProvider.has(model.provider_id))byProvider.set(model.provider_id,{providerId:model.provider_id,bindingEnabled:false,configured:false,eligibleModelCount:0,liveHealthyModelCount:0,active:false,states:[]});
    const row=byProvider.get(model.provider_id);row.configured=row.configured||model.configured;
    if(selectionCandidate(model))row.eligibleModelCount+=1;
    if(model.runtimeState==='LIVE_HEALTHY')row.liveHealthyModelCount+=1;
    row.states.push({modelId:model.model_id,state:model.runtimeState,category:model.runtimeCategory||null});
  }
  for(const row of byProvider.values())row.active=row.liveHealthyModelCount>0;
  return [...byProvider.values()].sort((a,b)=>a.providerId.localeCompare(b.providerId));
}
