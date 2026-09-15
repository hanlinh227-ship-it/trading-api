import {selectModelWorkers} from './model-mesh/selector.js';
import {buildTaskGraph} from './model-mesh/task-graph.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';

export async function buildModelMeshPlan(input,{skillSnapshot,modelSnapshot,fetchImpl=fetch}={}){
  void fetchImpl;
  if(!skillSnapshot||!modelSnapshot)throw new Error('MODEL_MESH_SNAPSHOTS_REQUIRED');
  if(skillSnapshot.source_sha!==modelSnapshot.source_sha)throw new Error('MODEL_MESH_SOURCE_SHA_MISMATCH');
  const route=input.route||{profile:String(input.profile||'STANDARD').toUpperCase(),primarySkill:skillSnapshot.fallback_primary_skill||'core_reasoning',externalRoutingCalls:0};
  route.externalRoutingCalls=0;
  const capsule=skillSnapshot.capsules?.[route.primarySkill]||skillSnapshot.capsules?.[skillSnapshot.fallback_primary_skill]||{};
  const profile=String(route.profile||input.profile||'STANDARD').toUpperCase();
  const dataClass=sanitizeDataClass(input.dataClass);
  const workers=profile==='FAST'?[]:selectModelWorkers({profile,domain:capsule.domain||'core',dataClass,models:modelSnapshot.models||[]});
  return {ok:true,mode:'FREE_ONLY',sourceSha:modelSnapshot.source_sha,routingAuthority:false,reasoningAuthority:false,route,capsuleHash:capsule.capsule_hash||null,dataClass,workers,taskGraph:buildTaskGraph({text:input.text,route,workers})};
}
