import {selectModelWorkers} from './model-mesh/selector.js';
import {buildTaskGraph} from './model-mesh/task-graph.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';
import {resolveLiveModels} from './model-mesh/runtime-health.js';
import {applyCapabilityEvidence,enabledHardCapabilities} from './model-mesh/capability-evidence.js';

export async function buildModelMeshPlan(input,{skillSnapshot,modelSnapshot,activeIndex,env={},fetchImpl=fetch}={}){
  void fetchImpl;
  if(!skillSnapshot||!modelSnapshot||!activeIndex)throw new Error('MODEL_MESH_SNAPSHOTS_REQUIRED');
  if(skillSnapshot.source_sha!==modelSnapshot.source_sha||activeIndex.source_sha!==modelSnapshot.source_sha)throw new Error('MODEL_MESH_SOURCE_SHA_MISMATCH');
  const sourceRoute=input.route||{profile:String(input.profile||'STANDARD').toUpperCase(),primarySkill:skillSnapshot.fallback_primary_skill||'core_reasoning',externalRoutingCalls:0};
  const route={...sourceRoute,externalRoutingCalls:0};
  const capsule=skillSnapshot.capsules?.[route.primarySkill]||skillSnapshot.capsules?.[skillSnapshot.fallback_primary_skill]||{};
  const profile=String(route.profile||input.profile||'STANDARD').toUpperCase();
  const dataClass=sanitizeDataClass(input.dataClass);
  const domain=capsule.domain||'core';
  const evidenceSnapshot={...modelSnapshot,models:applyCapabilityEvidence(modelSnapshot.models,activeIndex)};
  const liveModels=profile==='FAST'||dataClass==='SECRET'?[]:await resolveLiveModels(evidenceSnapshot,env);
  const hardCapabilities=enabledHardCapabilities(activeIndex,domain);
  const workers=profile==='FAST'||dataClass==='SECRET'?[]:selectModelWorkers({profile,domain,dataClass,models:liveModels,hardCapabilities});
  const selectionReason=workers.length?'live_healthy_provider_selected':(profile==='FAST'?'fast_external_mesh_forbidden':dataClass==='SECRET'?'secret_external_mesh_forbidden':'no_live_healthy_provider');
  return {ok:true,mode:'FREE_ONLY',sourceSha:modelSnapshot.source_sha,routingAuthority:false,reasoningAuthority:false,route,capsuleHash:capsule.capsule_hash||null,dataClass,workers,selectionReason,taskGraph:buildTaskGraph({text:input.text,route,workers})};
}
