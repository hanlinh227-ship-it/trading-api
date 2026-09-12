import assert from 'node:assert/strict';
import {createSkillGatewayHandler} from './skill-gateway-handler.js';

const makeCapsule=(id,domain)=>({skill_id:id,domain,output_contract:`contract:${id}`,capsule_hash:`hash-${id}`,tools:[],sources:[],permissions:['read_only'],risk_ceiling:'read_only'});
const SNAPSHOT={
  schema_version:1,source_sha:'b'.repeat(40),fallback_primary_skill:'core_reasoning',
  profiles:{FAST:{primary_skill_count:1,skill_capsule_required:true,max_supporting_skills:0},STANDARD:{primary_skill_count:1,skill_capsule_required:true,max_supporting_skills:2},DEEP:{primary_skill_count:1,skill_capsule_required:true,max_supporting_skills:2}},
  skills:{
    core_reasoning:{id:'core_reasoning',domain:'core',triggers:['explain'],aliases:['giải thích'],excludes:[],priority:80,tools:[],sources:[]},
    trading_router:{id:'trading_router',domain:'trading',triggers:['trade request'],aliases:['quét market'],excludes:[],priority:90,tools:[],sources:[]},
  },
  capsules:{core_reasoning:makeCapsule('core_reasoning','core'),trading_router:makeCapsule('trading_router','trading')},
};
const handler=createSkillGatewayHandler({snapshot:SNAPSHOT});
const call=(path,init={})=>handler(new Request(`https://example.test${path}`,init),{});

for(const path of ['/runtime/contract','/health','/research/market','/bybit/health'])assert.equal(await call(path),null);

let response=await call('/brain/health');
assert.equal(response.status,200);
let body=await response.json();
assert.equal(body.ok,true);
assert.equal(body.sourceSha,SNAPSHOT.source_sha);
assert.equal(body.schemaVersion,1);
assert.equal(body.freshGitContext,true);
assert.equal(body.externalRoutingCalls,0);

response=await call('/brain/route',{method:'GET'});
assert.equal(response.status,405);

response=await call('/brain/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:''})});
assert.equal(response.status,400);

response=await call('/brain/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'unknown nonsense'})});
assert.equal(response.status,200);
body=await response.json();
assert.equal(body.primarySkill,'core_reasoning');
assert.equal(body.capsule.skillId,'core_reasoning');
assert.equal(body.externalRoutingCalls,0);
assert.equal('reasoning' in body,false);

response=await call('/brain/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'quét market BTC live'})});
assert.equal(response.status,200);
body=await response.json();
assert.equal(body.profile,'DEEP');
assert.equal(body.primarySkill,'trading_router');
assert.equal(body.requiresFreshState,true);
assert.equal(body.externalRoutingCalls,0);

response=await call('/brain/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'x',trustedHints:{skill:'trading_router'}})});
assert.equal(response.status,400,'user payload must not be able to forge trusted hints');
console.log('SKILL_GATEWAY_HANDLER_TEST=PASS');
