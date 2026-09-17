import assert from 'node:assert/strict';
import fs from 'node:fs';

const index=fs.readFileSync(new URL('./index.js',import.meta.url),'utf8');
const prepare=fs.readFileSync(new URL('./prepare-wrangler.mjs',import.meta.url),'utf8');
const example=fs.readFileSync(new URL('./wrangler.example.jsonc',import.meta.url),'utf8');
const projectState=fs.readFileSync(new URL('./brain-project-state.js',import.meta.url),'utf8');
const handler=fs.readFileSync(new URL('./project-continuity-handler.js',import.meta.url),'utf8');

for(const [name,source] of [['prepare-wrangler.mjs',prepare],['wrangler.example.jsonc',example]]){
  assert.match(source,/BRAIN_PROJECT_STATE/,`${name} must bind BRAIN_PROJECT_STATE`);
  assert.match(source,/BrainProjectState/,`${name} must name BrainProjectState`);
  assert.match(source,/brain-project-state-v1/,`${name} must carry the v1 migration`);
}

assert.match(index,/export \{BrainProjectState\} from '\.\/brain-project-state\.js';/);
assert.match(index,/import \{handleProjectContinuity\} from '\.\/project-continuity-active\.js';/);
assert.match(index,/handleProjectContinuity\(req,env,ctx\)/);
assert.doesNotMatch(projectState,/TRADING_STATE|BRAIN_STATE/,'canonical project state must not fall back to KV/trading state');
assert.doesNotMatch(handler,/TRADING_STATE|BRAIN_STATE/,'continuity handler must use the dedicated DO only');

const continuityImport=index.indexOf("import {handleProjectContinuity} from './project-continuity-active.js';");
const gatewayImport=index.indexOf("import {handleSkillGateway} from './skill-gateway-runtime.js';");
assert.ok(continuityImport>=0&&gatewayImport>=0);
const continuityCall=index.indexOf('handleProjectContinuity(req,env,ctx)');
const gatewayCall=index.indexOf('handleSkillGateway(req,env)');
assert.ok(continuityCall>=0&&gatewayCall>=0&&continuityCall<gatewayCall,'continuity must be resolved before generic Skill Gateway routing');

console.log('PROJECT_CONTINUITY_DEPLOY_WIRING_TESTS=PASS');
