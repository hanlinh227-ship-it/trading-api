import {ACTIVE_SKILL_GATEWAY_SNAPSHOT} from './skill-gateway-runtime.js';
import {routeSkillRequest} from './skill-gateway.js';
import {MODEL_MESH_SNAPSHOT} from './generated/model-mesh-snapshot.js';
import {createModelMeshHandler} from './model-mesh-handler.js';
import {createMeshExecutor,createProviderProbe} from './model-mesh/provider-client.js';
import {handleBrainEvidence} from './brain-evidence-active.js';

export const ACTIVE_MODEL_MESH_SNAPSHOT=MODEL_MESH_SNAPSHOT;
const probeProviders=createProviderProbe();
const handleMeshOnly=createModelMeshHandler({
  skillSnapshot:ACTIVE_SKILL_GATEWAY_SNAPSHOT,
  modelSnapshot:ACTIVE_MODEL_MESH_SNAPSHOT,
  routeSkill:({text})=>routeSkillRequest({text},ACTIVE_SKILL_GATEWAY_SNAPSHOT),
  executeWorkers:createMeshExecutor({selfHealProbe:probeProviders}),
  probeProviders,
});

export async function handleModelMesh(request,env={},ctx={}){
  return await handleMeshOnly(request,env,ctx)||await handleBrainEvidence(request,env,ctx);
}
