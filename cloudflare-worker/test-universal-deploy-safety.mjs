import assert from 'node:assert/strict';
import fs from 'node:fs';

const workflow=fs.readFileSync('../.github/workflows/deploy-skill-mandatory-fast-gateway.yml','utf8');
const wranglerPrep=fs.readFileSync('prepare-wrangler.mjs','utf8');
const universalSecrets=['BRAIN_CLIENT_CHATGPT_TOKEN','BRAIN_CLIENT_CLAUDE_TOKEN','BRAIN_CLIENT_GEMINI_TOKEN','BRAIN_EVERGREEN_TOKEN'];

for(const key of universalSecrets){
  assert.match(workflow,new RegExp(`${key}:\\s*\\$\\{\\{ secrets\\.${key} \\}\\}`),`${key} must come from GitHub secrets`);
  assert.doesNotMatch(wranglerPrep,new RegExp(key),`${key} must never enter generated wrangler vars/config`);
}
const loopPattern=new RegExp(`for key in[^\\n]*${universalSecrets.join('[^\\n]*')}[^\\n]*; do`);
assert.match(workflow,loopPattern,'all Universal Brain credentials must be handled by one bounded explicit secret loop');
assert.match(workflow,/wrangler secret put "\$key" --name trading-v77-scanner/,'Universal Brain tokens must be synced only through Cloudflare Worker secrets');
assert.match(workflow,/validate-universal-canary\.mjs/,'Universal canary must gate production');
assert.match(workflow,/UNIVERSAL_BRAIN_HEALTH=PASS/);
assert.match(workflow,/UNIVERSAL_ADAPTER_CANARY=PASS/);
assert.match(workflow,/UNIVERSAL_HIGH_RISK_FAIL_CLOSED=PASS/);
assert.match(workflow,/name: Roll back to previously live exact revision\n\s+if: failure\(\)/,'Universal canary failures must reuse deterministic rollback');
console.log('UNIVERSAL_DEPLOY_SAFETY_TESTS=PASS');
