import {ACTIVE_SKILL_GATEWAY_SNAPSHOT} from './skill-gateway-runtime.js';
import {routeSkillRequest} from './skill-gateway.js';
import {handleScheduledHealthRefresh as runScheduledHealthRefresh} from './model-mesh/scheduled-health.js';
import {MODEL_MESH_SNAPSHOT} from './generated/model-mesh-snapshot.js';
import {MODEL_MESH_ACTIVE_CANDIDATE_INDEX} from './generated/model-mesh-active-candidate-index.js';
import {createModelMeshHandler} from './model-mesh-handler.js';
import {createMeshExecutor,createProviderProbe} from './model-mesh/provider-client.js';
import {handleBrainEvidence} from './brain-evidence-active.js';

export const ACTIVE_MODEL_MESH_SNAPSHOT=MODEL_MESH_SNAPSHOT;
export const ACTIVE_MODEL_MESH_CANDIDATE_INDEX=MODEL_MESH_ACTIVE_CANDIDATE_INDEX;
const probeProviders=createProviderProbe();
const handleMeshOnly=createModelMeshHandler({
  skillSnapshot:ACTIVE_SKILL_GATEWAY_SNAPSHOT,
  modelSnapshot:ACTIVE_MODEL_MESH_SNAPSHOT,
  activeIndex:ACTIVE_MODEL_MESH_CANDIDATE_INDEX,
  routeSkill:({text})=>routeSkillRequest({text},ACTIVE_SKILL_GATEWAY_SNAPSHOT),
  executeWorkers:createMeshExecutor({selfHealProbe:probeProviders}),
  probeProviders,
});

export async function handleModelMesh(request,env={},ctx={}){
  return await handleMeshOnly(request,env,ctx)||await handleBrainEvidence(request,env,ctx);
}

// Worker cron entry point. Bound to the same canonical provider probe and
// snapshot the manual refresh uses, so the scheduled path can never drift into
// a second health mechanism.
export async function handleScheduledHealthRefresh(event,env={},ctx={}){
  return runScheduledHealthRefresh({event,env,ctx,probeProviders,modelSnapshot:ACTIVE_MODEL_MESH_SNAPSHOT});
}
