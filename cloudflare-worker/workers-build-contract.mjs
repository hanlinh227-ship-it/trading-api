import path from 'node:path';

export function canonicalPreparationEnv(baseEnv,root,sourceSha){
  return {
    ...baseEnv,
    GITHUB_SHA:sourceSha,
    RUNTIME_REVISION:sourceSha,
    SKILL_GATEWAY_SNAPSHOT_PATH:path.join(root,'AI_SKILL_LIBRARY','v4','runtime','generated','skill-gateway-snapshot.json'),
    MODEL_MESH_SNAPSHOT_PATH:path.join(root,'AI_SKILL_LIBRARY','v4','runtime','generated','model-mesh-snapshot.json'),
    MODEL_MESH_BINDINGS_PATH:path.join(root,'AI_SKILL_LIBRARY','v4','model_mesh','runtime_bindings.json'),
    MODEL_MESH_FREE_POLICY_PATH:path.join(root,'AI_SKILL_LIBRARY','v4','model_mesh','free_only_policy.json'),
  };
}
