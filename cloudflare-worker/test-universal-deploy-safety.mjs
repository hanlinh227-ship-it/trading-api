import assert from 'node:assert/strict';
import fs from 'node:fs';

const workflow=fs.readFileSync('../.github/workflows/deploy-skill-mandatory-fast-gateway.yml','utf8');
const wranglerPrep=fs.readFileSync('prepare-wrangler.mjs','utf8');
const canary=fs.readFileSync('validate-universal-canary.mjs','utf8');
const universalSecrets=['BRAIN_CLIENT_CHATGPT_TOKEN','BRAIN_CLIENT_CLAUDE_TOKEN','BRAIN_CLIENT_GEMINI_TOKEN','BRAIN_EVERGREEN_TOKEN'];

for(const key of universalSecrets){
  assert.match(workflow,new RegExp(`${key}:\\s*\\$\\{\\{ secrets\\.${key} \\}\\}`),`${key} must come from GitHub secrets`);
  assert.doesNotMatch(wranglerPrep,new RegExp(key),`${key} must never enter generated wrangler vars/config`);
}
const loopPattern=new RegExp(`for key in[^\\n]*${universalSecrets.join('[^\\n]*')}[^\\n]*; do`);
assert.match(workflow,loopPattern,'all Universal Brain credentials must be handled by one bounded explicit secret loop');
assert.match(workflow,/wrangler secret put "\$key" --name trading-v77-scanner/,'Universal Brain tokens must be synced only through Cloudflare Worker secrets');
assert.match(workflow,/validate-universal-canary\.mjs/,'Universal canary must gate production');
assert.match(canary,/UNIVERSAL_BRAIN_HEALTH=PASS/,'Universal canary must report Brain health success');
assert.match(canary,/UNIVERSAL_ADAPTER_CANARY=PASS/,'Universal canary must report adapter-route success');
assert.match(canary,/UNIVERSAL_HIGH_RISK_FAIL_CLOSED=PASS/,'Universal canary must report the high-risk fail-closed proof');
assert.match(canary,/UNIVERSAL_PROJECT_CONTINUITY=PASS/,'Universal canary must report cross-session project continuity proof');
assert.match(canary,/UNIVERSAL_PROJECT_ISOLATION=PASS/,'Universal canary must report production project-isolation proof');
assert.match(canary,/FRONT_DOOR_BACKEND_READY=PASS/,'Universal canary must report backend Front Door proof');
assert.match(canary,/CLIENT_ADAPTER_READY=PASS/,'Universal canary must report client-adapter proof');
assert.match(canary,/NEW_SESSION_RESUME_PASS=PASS/,'Universal canary must report Session A to Session B proof');
assert.match(canary,/VERSION_CONFLICT_409_PASS=PASS/,'Universal canary must report optimistic conflict proof');
assert.match(canary,/ACCOUNT_INTEGRATION_PROVEN=FALSE/,'Universal canary must not misrepresent native account authorization');
assert.match(canary,/FRONT_DOOR_READY=FALSE/,'Universal canary must fail closed until native account authorization is proven');
assert.match(workflow,/name: Roll back to previously live exact revision\n\s+if: failure\(\)/,'Universal canary failures must reuse deterministic rollback');
console.log('UNIVERSAL_DEPLOY_SAFETY_TESTS=PASS');
