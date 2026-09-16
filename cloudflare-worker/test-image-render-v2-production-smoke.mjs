import assert from 'node:assert/strict';
import fs from 'node:fs';

const workflow=fs.readFileSync('../.github/workflows/image-render-v2-production-smoke.yml','utf8');

assert.match(workflow,/workflow_run:/);
assert.match(workflow,/Deploy Skill-Mandatory Fast Gateway/);
assert.match(workflow,/workflow_run\.conclusion == 'success'/);
assert.match(workflow,/workflow_run\.head_branch == 'main'/);
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
assert.doesNotMatch(workflow,/referenceImages|sourceImage/);

console.log('IMAGE_RENDER_V2_PRODUCTION_SMOKE_CONTRACT_TEST=PASS');
