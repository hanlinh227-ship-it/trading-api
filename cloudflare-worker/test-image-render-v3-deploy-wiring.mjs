import assert from 'node:assert/strict';
import fs from 'node:fs';

const wranglerPrep=fs.readFileSync('prepare-wrangler.mjs','utf8');
const wranglerExample=fs.readFileSync('wrangler.example.jsonc','utf8');
const index=fs.readFileSync('index.js','utf8');
const logicalState=fs.readFileSync('image-render/logical-job-state.js','utf8');
const v3Entry=fs.readFileSync('image-render-v3-entry.js','utf8');

// The logical job plane needs its own durable binding in both the generated and the
// reference wrangler config, and the exported class name must match the binding.
for(const source of [wranglerPrep,wranglerExample]){
  assert.match(source,/IMAGE_LOGICAL_JOB/);
  assert.match(source,/ImageLogicalJobState/);
  assert.match(source,/image-logical-job-v1/);
}
assert.match(index,/export \{ImageLogicalJobState\} from '\.\/image-render\/logical-job-state\.js';/);
assert.match(index,/handleImageRenderV3/);

// Image state is never allowed to reach trading state, and the V3 plane keeps its own key.
assert.doesNotMatch(logicalState,/TRADING_STATE/);
assert.match(logicalState,/image-logical-job-state-v3/);

// V3 must stay authenticated: the token comparison is awaited, never a truthy Promise.
assert.match(v3Entry,/!await timingSafeToken\(/);

// No provider credential may ever be generated into Worker vars.
assert.doesNotMatch(wranglerPrep,/AI_HORDE_API_KEY:/);

console.log('IMAGE_RENDER_V3_DEPLOY_WIRING_TEST=PASS');
