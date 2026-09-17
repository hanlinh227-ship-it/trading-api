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
// The SHA under test is still the deployed one. A manual re-run has to name it, so a
// re-check can never silently verify a revision production is not serving.
assert.match(workflow,/EXPECTED_SHA:\s*\$\{\{ github\.event\.inputs\.expected_sha \|\| github\.event\.workflow_run\.head_sha \}\}/);
assert.match(workflow,/expected_sha:/);
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

// Scene 1 acceptance: a real reference scene goes through the canonical V3 job path in
// production. The V1/V2 volunteer routes still upload nothing -- what changed is that the
// reference-safe route now exists, so it has to be exercised rather than assumed.
assert.match(workflow,/name: Scene 1 reference acceptance/);
assert.match(workflow,/\/brain\/image\/v3\/jobs/);
assert.match(workflow,/\/brain\/image\/v3\/jobs\/status/);
assert.match(workflow,/\/brain\/image\/v3\/assets/);
assert.match(workflow,/taskType:'REFERENCE_GENERATION'/);
assert.match(workflow,/dataClass:'CONFIDENTIAL'/);
assert.match(workflow,/MAX_REF/);
assert.match(workflow,/MOMMY_REF/);
assert.match(workflow,/BG01/);
// Reaching the volunteer provider on a reference scene fails the smoke outright.
assert.match(workflow,/IMAGE_SCENE1_REFERENCE_SAFE=FAIL volunteer_provider_reached/);
assert.match(workflow,/IMAGE_SCENE1_ACCEPTANCE=RENDERED/);
assert.match(workflow,/IMAGE_SCENE1_ACCEPTANCE=WAITING/);
// The V2 volunteer batch in this smoke still carries no image of any kind.
assert.doesNotMatch(workflow,/"referenceImages":/);
assert.doesNotMatch(workflow,/"sourceImage":/);

// A failed task probe has to name why, and which models were rejected, or the next
// engineer is back to guessing.
assert.match(workflow,/diagnostic=/);
assert.match(workflow,/attempted=/);

// Production must collect live runtime evidence and print the per-model activation state,
// so the gap between "registered" and "actually runnable" is visible on every deploy.
assert.match(workflow,/v3\/activation\?probe=1/);
assert.match(workflow,/IMAGE_RUNTIME_PROBE provider=/);
assert.match(workflow,/IMAGE_ACTIVATION model=/);
// Capabilities must be read with a probe, and a runtime may only read AVAILABLE when that
// probe verified it in the same request.
assert.match(workflow,/v3\/capabilities\?probe=1/);
assert.match(workflow,/runtimeVerifiedThisRequest/);
assert.match(workflow,/refRuntime=/);

console.log('IMAGE_RENDER_V2_PRODUCTION_SMOKE_CONTRACT_TEST=PASS');
