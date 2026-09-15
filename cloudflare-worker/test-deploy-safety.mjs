import assert from 'node:assert/strict';
import fs from 'node:fs';
const workflow=fs.readFileSync('../.github/workflows/deploy-skill-mandatory-fast-gateway.yml','utf8');
assert.match(workflow,/TINY_FISH_API:\s*\$\{\{ secrets\.TINY_FISH_API \}\}/);
assert.match(workflow,/redact-deploy-output\.mjs/);
assert.match(workflow,/MODEL_MESH_PROBE_MATRIX/);
assert.match(workflow,/LIVE_HEALTHY/);
assert.doesNotMatch(workflow,/echo\s+['"]?\$\{?TINY_FISH_API/);
console.log('deployment secret and live-canary contracts ok');
