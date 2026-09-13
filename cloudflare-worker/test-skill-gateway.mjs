import assert from 'node:assert/strict';
import {routeSkillRequest, assertResponseQuality} from './skill-gateway.js';

const capsule = (skill_id, domain) => ({skill_id,domain,output_contract:`${skill_id} output`,permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:`hash-${skill_id}`});
const skill = (id,domain,aliases,display_name,{tools=[],priority=80,triggers=[]}={}) => ({id,domain,aliases,triggers,excludes:[],priority,requires:['task_router'],conflicts_with:[],tools,sources:[],output_contract:`${id} output`,primary_selectable:true,display_name});
const snapshot={
  schema_version:1, source_sha:'a'.repeat(40), release_id:'4.5.0', fallback_primary_skill:'core_reasoning',
  presentation:{locale:'vi',mode:'plain',hide_internal_ids:true,no_underscore_display_names:true,technical_output_allowed:true,preserve_exact_machine_tokens:true},
  profiles:{FAST:{max_supporting_skills:0},STANDARD:{max_supporting_skills:2},DEEP:{max_supporting_skills:2}},
  domains:{core:['core_reasoning'],engineering:['debugging'],writing:['advertising_copy'],trading:['trading_router']},
  skills:{
    core_reasoning:skill('core_reasoning','core',['giải thích','là gì'],'Giải thích'),
    debugging:skill('debugging','engineering',['sửa lỗi','debug'],'Sửa lỗi',{tools:['software_development_workflow'],priority:90}),
    advertising_copy:skill('advertising_copy','writing',['viết quảng cáo','kịch bản quảng cáo'],'Viết quảng cáo',{priority:90}),
    trading_router:skill('trading_router','trading',['quét market','tìm entry'],'Phân tích giao dịch',{tools:['multi_asset_market_data'],priority:95}),
  },
  capsules:{
    core_reasoning:capsule('core_reasoning','core'),debugging:capsule('debugging','engineering'),
    advertising_copy:capsule('advertising_copy','writing'),trading_router:capsule('trading_router','trading'),
  },
  profile_escalation:{STANDARD:['dự án'],DEEP:['live','trading','deploy','production']},
  fresh_state_terms:['mới nhất','hiện tại','live','realtime'],
};

function expectRoute(text, expectedSkill, expectedProfile, expectedName){
  const route=routeSkillRequest({text},snapshot);
  assert.equal(route.primarySkill,expectedSkill,text);
  if(expectedProfile)assert.equal(route.profile,expectedProfile,text);
  if(expectedName)assert.equal(route.primarySkillName,expectedName,text);
  assert.equal(route.externalRoutingCalls,0);
  assert.equal(route.sourceSha,snapshot.source_sha);
  assert.ok(route.capsuleHash);
  return route;
}

expectRoute('giải thích bác sĩ nội trú','core_reasoning','FAST','Giải thích');
expectRoute('sửa lỗi API này','debugging','STANDARD','Sửa lỗi');
expectRoute('viết kịch bản quảng cáo giày','advertising_copy','FAST','Viết quảng cáo');
const live=expectRoute('quét market BTC live','trading_router','DEEP','Phân tích giao dịch');
assert.equal(live.requiresFreshState,true);
assert.equal(live.requiresAuthority,true);

const unknown=expectRoute('một câu hỏi rất lạ chưa có alias','core_reasoning','FAST','Giải thích');
const goodExecution={answered:true,capsuleApplied:true,authorityAllowed:true,freshStateSatisfied:true,toolRequirementSatisfied:true,answerText:'Cách này giúp giải thích vấn đề bằng từ dễ hiểu.',technicalOutput:false};
assertResponseQuality({route:unknown,execution:goodExecution,snapshot});
assert.throws(()=>assertResponseQuality({route:{...unknown,primarySkill:''},execution:goodExecution,snapshot}),/primary_skill/i);
assert.throws(()=>assertResponseQuality({route:unknown,execution:{...goodExecution,capsuleApplied:false},snapshot}),/capsule/i);
assert.throws(()=>assertResponseQuality({route:unknown,execution:{...goodExecution,answerText:'Hệ thống đang dùng core_reasoning để xử lý.'},snapshot}),/internal_identifier/i);
assertResponseQuality({route:unknown,execution:{...goodExecution,answerText:'Mã nội bộ chính xác là core_reasoning.',technicalOutput:true},snapshot});

const exactPlain='Giới hạn là 150 USD vào ngày 13/09/2026. Kết quả này chưa chắc chắn và cần kiểm tra lại.';
assertResponseQuality({route:unknown,execution:{...goodExecution,answerText:exactPlain},snapshot});
assert.equal(exactPlain,'Giới hạn là 150 USD vào ngày 13/09/2026. Kết quả này chưa chắc chắn và cần kiểm tra lại.');
const exactTechnical='Chạy lệnh `python tool.py --skill core_reasoning`; giữ nguyên 150 USD và ngày 13/09/2026.';
assertResponseQuality({route:unknown,execution:{...goodExecution,answerText:exactTechnical,technicalOutput:true},snapshot});
assert.equal(exactTechnical,'Chạy lệnh `python tool.py --skill core_reasoning`; giữ nguyên 150 USD và ngày 13/09/2026.');

const oldFetch=globalThis.fetch;
globalThis.fetch=()=>{throw new Error('NETWORK_FORBIDDEN_ON_FAST_ROUTE');};
try{
  expectRoute('giải thích khái niệm đơn giản','core_reasoning','FAST','Giải thích');
}finally{globalThis.fetch=oldFetch;}

const hinted=routeSkillRequest({text:'nội dung chung',trustedHints:{skill:'advertising_copy'}},snapshot);
assert.equal(hinted.primarySkill,'advertising_copy');
assert.equal(hinted.primarySkillName,'Viết quảng cáo');
assert.equal(hinted.domain,'writing');

console.log('SKILL_GATEWAY_ROUTER_TESTS=PASS');
