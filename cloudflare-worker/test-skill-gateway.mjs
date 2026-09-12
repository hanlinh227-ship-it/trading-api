import assert from 'node:assert/strict';
import {routeSkillRequest,assertResponseQuality} from './skill-gateway.js';

const capsule=id=>({skill_id:id,domain:id==='trading_router'?'trading':id==='advertising_copy'?'writing':id==='debugging'?'engineering':'core',output_contract:'bounded output',capsule_hash:`hash-${id}`,tools:[],sources:[],permissions:['read_only'],risk_ceiling:'read_only'});
const SNAPSHOT={
  schema_version:1,
  source_sha:'a'.repeat(40),
  fallback_primary_skill:'core_reasoning',
  profiles:{
    FAST:{primary_skill_count:1,skill_capsule_required:true,max_supporting_skills:0,tool_candidates:0,durable_memory_items:0},
    STANDARD:{primary_skill_count:1,skill_capsule_required:true,max_supporting_skills:2,tool_candidates:3,durable_memory_items:4},
    DEEP:{primary_skill_count:1,skill_capsule_required:true,max_supporting_skills:2,tool_candidates:5,durable_memory_items:8},
  },
  skills:{
    core_reasoning:{id:'core_reasoning',domain:'core',triggers:['explain','why'],aliases:['giải thích','tại sao'],excludes:[],priority:80,tools:[],sources:[]},
    debugging:{id:'debugging',domain:'engineering',triggers:['bug','debug'],aliases:['sửa lỗi','lỗi code'],excludes:[],priority:80,tools:[],sources:[]},
    advertising_copy:{id:'advertising_copy',domain:'writing',triggers:['ad copy','advertising copy'],aliases:['viết quảng cáo','kịch bản quảng cáo'],excludes:[],priority:80,tools:[],sources:[]},
    trading_router:{id:'trading_router',domain:'trading',triggers:['trade request'],aliases:['quét market','quét thị trường'],excludes:[],priority:80,tools:[],sources:[]},
  },
  capsules:{
    core_reasoning:capsule('core_reasoning'),debugging:capsule('debugging'),advertising_copy:capsule('advertising_copy'),trading_router:capsule('trading_router'),
  },
};

const originalFetch=globalThis.fetch;
let fetchCalls=0;
globalThis.fetch=()=>{fetchCalls+=1;throw new Error('FAST_ROUTER_MUST_NOT_FETCH');};
try{
  const explain=routeSkillRequest({text:'giải thích bác sĩ nội trú'},SNAPSHOT);
  assert.equal(explain.profile,'FAST');
  assert.equal(explain.primarySkill,'core_reasoning');
  assert.equal(explain.capsuleId,'core_reasoning');

  const debug=routeSkillRequest({text:'sửa lỗi API này'},SNAPSHOT);
  assert.equal(debug.primarySkill,'debugging');

  const ad=routeSkillRequest({text:'viết kịch bản quảng cáo giày'},SNAPSHOT);
  assert.equal(ad.primarySkill,'advertising_copy');

  const live=routeSkillRequest({text:'quét market BTC live'},SNAPSHOT);
  assert.equal(live.profile,'DEEP');
  assert.equal(live.primarySkill,'trading_router');
  assert.equal(live.requiresFreshState,true);
  assert.equal(live.requiresAuthority,true);

  const unknown=routeSkillRequest({text:'zxqv plmno nonsense'},SNAPSHOT);
  assert.equal(unknown.primarySkill,'core_reasoning');

  const hinted=routeSkillRequest({text:'xin hỗ trợ',trustedHints:{skill:'debugging'}},SNAPSHOT);
  assert.equal(hinted.primarySkill,'debugging');

  assert.equal(fetchCalls,0);
  assert.deepEqual(assertResponseQuality({route:ad,execution:{answer:'copy',appliedCapsuleHash:ad.capsuleHash}}),{ok:true});
  assert.throws(()=>assertResponseQuality({route:{...ad,primarySkill:null},execution:{answer:'x',appliedCapsuleHash:ad.capsuleHash}}),/primary_skill/);
  assert.throws(()=>assertResponseQuality({route:ad,execution:{answer:'x',appliedCapsuleHash:'wrong'}}),/capsule/);
  assert.throws(()=>assertResponseQuality({route:ad,execution:{answer:'' ,appliedCapsuleHash:ad.capsuleHash}}),/answer/);
} finally {
  globalThis.fetch=originalFetch;
}
console.log('SKILL_GATEWAY_ROUTER_TEST=PASS');
