import assert from 'node:assert/strict';
import {createSkillGatewayHandler} from './skill-gateway-handler.js';

const snapshot={
  schema_version:1,source_sha:'b'.repeat(40),release_id:'4.0.1',generated_at:'2026-09-12T00:00:00Z',fallback_primary_skill:'core_reasoning',
  profiles:{FAST:{max_supporting_skills:0},STANDARD:{max_supporting_skills:2},DEEP:{max_supporting_skills:2}},
  domains:{core:['core_reasoning'],writing:['advertising_copy']},
  skills:{
    core_reasoning:{id:'core_reasoning',domain:'core',aliases:['giải thích'],triggers:['explain'],excludes:[],priority:80,requires:['task_router'],conflicts_with:[],tools:[],sources:[],output_contract:'Explain precisely.',primary_selectable:true},
    advertising_copy:{id:'advertising_copy',domain:'writing',aliases:['viết quảng cáo'],triggers:['ad copy'],excludes:[],priority:80,requires:['task_router'],conflicts_with:[],tools:[],sources:[],output_contract:'Write audience-fit advertising copy.',primary_selectable:true},
  },
  capsules:{
    core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'Explain precisely.',permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:'core-hash'},
    advertising_copy:{skill_id:'advertising_copy',domain:'writing',output_contract:'Write audience-fit advertising copy.',permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:'ad-hash'},
  },
  profile_escalation:{STANDARD:[],DEEP:[]},fresh_state_terms:[],hashes:{router:'r',runtime:'u'}
};

const handler=createSkillGatewayHandler({snapshot});

let res=await handler(new Request('https://example.test/brain/health'));
assert.equal(res.status,200);
let body=await res.json();
assert.equal(body.ok,true);
assert.equal(body.sourceSha,snapshot.source_sha);
assert.equal(body.schemaVersion,1);
assert.equal(body.primarySkillRequired,true);
assert.equal(body.externalRoutingCalls,0);

res=await handler(new Request('https://example.test/brain/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'viết quảng cáo giày'})}));
assert.equal(res.status,200);
body=await res.json();
assert.equal(body.ok,true);
assert.equal(body.route.primarySkill,'advertising_copy');
assert.equal(body.route.domain,'writing');
assert.equal(body.route.externalRoutingCalls,0);
assert.equal(body.capsule.skill_id,'advertising_copy');
assert.equal(body.capsule.output_contract,'Write audience-fit advertising copy.');
assert.equal('reasoning' in body,false);
assert.equal('chainOfThought' in body,false);

res=await handler(new Request('https://example.test/brain/route',{method:'POST',headers:{'content-type':'application/json'},body:'{}'}));
assert.equal(res.status,400);
body=await res.json();
assert.equal(body.ok,false);

const passthrough=await handler(new Request('https://example.test/runtime/contract'));
assert.equal(passthrough,null);

console.log('SKILL_GATEWAY_HANDLER_TESTS=PASS');
