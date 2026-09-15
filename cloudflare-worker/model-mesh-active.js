import {ACTIVE_SKILL_GATEWAY_SNAPSHOT} from './skill-gateway-runtime.js';
import {routeSkillRequest} from './skill-gateway.js';
import {MODEL_MESH_SNAPSHOT} from './generated/model-mesh-snapshot.js';
import {createModelMeshHandler} from './model-mesh-handler.js';
import {createMeshExecutor,createProviderProbe} from './model-mesh/provider-client.js';

export const ACTIVE_MODEL_MESH_SNAPSHOT=MODEL_MESH_SNAPSHOT;
export const handleModelMesh=createModelMeshHandler({
  skillSnapshot:ACTIVE_SKILL_GATEWAY_SNAPSHOT,
  modelSnapshot:ACTIVE_MODEL_MESH_SNAPSHOT,
  routeSkill:({text})=>routeSkillRequest({text},ACTIVE_SKILL_GATEWAY_SNAPSHOT),
  executeWorkers:createMeshExecutor(),
  probeProviders:createProviderProbe(),
});
