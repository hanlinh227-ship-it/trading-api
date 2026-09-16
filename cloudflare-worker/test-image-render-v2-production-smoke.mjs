import assert from 'node:assert/strict';
import fs from 'node:fs';

const workflow=fs.readFileSync('../.github/workflows/image-render-v2-production-smoke.yml','utf8');

assert.match(workflow,/workflow_run:/);
assert.match(workflow,/Deploy Skill-Mandatory Fast Gateway/);
assert.match(workflow,/workflow_run\.conclusion == 'success'/);
assert.match(workflow,/workflow_run\.head_branch == 'main'/);
assert.match(workflow,/workflow_run\.event == 'push'/);
assert.match(workflow,/name: Production Image Render V2 smoke/);
assert.match(workflow,/MODEL_MESH_EXECUTION_TOKEN:\s*\$\{\{ secrets\.MODEL_MESH_EXECUTION_TOKEN \}\}/);
assert.match(workflow,/EXPECTED_SHA:\s*\$\{\{ github\.event\.workflow_run\.head_sha \}\}/);
assert.match(workflow,/runtime\/contract/);
assert.match(workflow,/x-image-render-token: \$MODEL_MESH_EXECUTION_TOKEN/);
assert.match(workflow,/\/brain\/image\/health/);
assert.match(workflow,/\/brain\/image\/models/);
assert.match(workflow,/\/brain\/image\/batch/);
assert.match(workflow,/\/brain\/image\/batch\/status/);
assert.match(workflow,/-X DELETE/);
assert.match(workflow,/"dataClass":"PUBLIC"/);
assert.match(workflow,/IMAGE_RENDER_MODELS=PROVIDER_DEGRADED/);
assert.match(workflow,/IMAGE_RENDER_V2_PRODUCTION_SMOKE=PASS/);
assert.doesNotMatch(workflow,/"referenceImages"\s*:/);
assert.doesNotMatch(workflow,/"sourceImage"\s*:/);

// Runtime discovery evidence: production must report which models the free provider
// actually serves, so the vault can only record a runtime for a model seen with capacity.
assert.match(workflow,/IMAGE_RUNTIME_DISCOVERED model=/);
assert.match(workflow,/IMAGE_RUNTIME_DISCOVERY=PASS/);

// The V3 planes are verified in production too, not just V2.
assert.match(workflow,/\/brain\/image\/v3\/activation/);
assert.match(workflow,/\/brain\/image\/v3\/capabilities/);
assert.match(workflow,/IMAGE_V3_ACTIVATION=PASS/);
assert.match(workflow,/IMAGE_V3_CAPABILITIES=PASS/);
// An ACTIVE model with no runtime provider must fail the smoke.
assert.match(workflow,/runtimeProviders/);
// Reference work must stay fail-closed in production until a safe free runtime exists.
assert.match(workflow,/WAITING_FOR_SAFE_FREE_RUNTIME/);
// The smoke still renders nothing and uploads nothing.
assert.doesNotMatch(workflow,/"referenceAssets"\s*:/);

console.log('IMAGE_RENDER_V2_PRODUCTION_SMOKE_CONTRACT_TEST=PASS');
