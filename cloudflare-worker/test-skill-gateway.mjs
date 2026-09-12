import assert from 'node:assert/strict';
import {routeSkillRequest, assertResponseQuality} from './skill-gateway.js';

const capsule = (skill_id, domain) => ({skill_id,domain,output_contract:`${skill_id} output`,permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:`hash-${skill_id}`});
const skill = (id,domain,aliases,{tools=[],priority=80,triggers=[]}={}) => ({id,domain,aliases,triggers,excludes:[],priority,requires:['task_router'],conflicts_with:[],tools,sources:[],output_contract:`${id} output`,primary_selectable:true});
const snapshot={
  schema_version:1, source_sha:'a'.repeat(40), release_id:'4.0.1', fallback_primary_skill:'core_reasoning',
  profiles:{FAST:{max_supporting_skills:0},STANDARD:{max_supporting_skills:2},DEEP:{max_supporting_skills:2}},
  domains:{core:['core_reasoning'],engineering:['debugging'],writing:['advertising_copy'],trading:['trading_router']},
  skills:{
    core_reasoning:skill('core_reasoning','core',['giải thích','là gì']),
    debugging:skill('debugging','engineering',['sửa lỗi','debug'],{tools:['software_development_workflow'],priority:90}),
    advertising_copy:skill('advertising_copy','writing',['viết quảng cáo','kịch bản quảng cáo'],{priority:90}),
    trading_router:skill('trading_router','trading',['quét market','tìm entry'],{tools:['multi_asset_market_data'],priority:95}),
  },
  capsules:{
    core_reasoning:capsule('core_reasoning','core'),debugging:capsule('debugging','engineering'),
    advertising_copy:capsule('advertising_copy','writing'),trading_router:capsule('trading_router','trading'),
  },
  profile_escalation:{STANDARD:['dự án'],DEEP:['live','trading','deploy','production']},
  fresh_state_terms:['mới nhất','hiện tại','live','realtime'],
};

function expectRoute(text, expectedSkill, expectedProfile){
  const route=routeSkillRequest({text},snapshot);
  assert.equal(route.primarySkill,expectedSkill,text);
  if(expectedProfile)assert.equal(route.profile,expectedProfile,text);
  assert.equal(route.externalRoutingCalls,0);
  assert.equal(route.sourceSha,snapshot.source_sha);
  assert.ok(route.capsuleHash);
  return route;
}

expectRoute('giải thích bác sĩ nội trú','core_reasoning','FAST');
expectRoute('sửa lỗi API này','debugging','STANDARD');
expectRoute('viết kịch bản quảng cáo giày','advertising_copy','FAST');
const live=expectRoute('quét market BTC live','trading_router','DEEP');
assert.equal(live.requiresFreshState,true);
assert.equal(live.requiresAuthority,true);

const unknown=expectRoute('một câu hỏi rất lạ chưa có alias','core_reasoning','FAST');
assertResponseQuality({route:unknown,execution:{answered:true,capsuleApplied:true,authorityAllowed:true,freshStateSatisfied:true,toolRequirementSatisfied:true}});
assert.throws(()=>assertResponseQuality({route:{...unknown,primarySkill:''},execution:{answered:true,capsuleApplied:true,authorityAllowed:true,freshStateSatisfied:true,toolRequirementSatisfied:true}}),/primary_skill/i);
assert.throws(()=>assertResponseQuality({route:unknown,execution:{answered:true,capsuleApplied:false,authorityAllowed:true,freshStateSatisfied:true,toolRequirementSatisfied:true}}),/capsule/i);

const oldFetch=globalThis.fetch;
globalThis.fetch=()=>{throw new Error('NETWORK_FORBIDDEN_ON_FAST_ROUTE');};
try{
  expectRoute('giải thích khái niệm đơn giản','core_reasoning','FAST');
}finally{globalThis.fetch=oldFetch;}

const hinted=routeSkillRequest({text:'nội dung chung',trustedHints:{skill:'advertising_copy'}},snapshot);
assert.equal(hinted.primarySkill,'advertising_copy');
assert.equal(hinted.domain,'writing');

console.log('SKILL_GATEWAY_ROUTER_TESTS=PASS');
