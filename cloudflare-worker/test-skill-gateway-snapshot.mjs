import assert from 'node:assert/strict';
import {routeSkillRequest} from './skill-gateway.js';
import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';

assert.equal(SKILL_GATEWAY_SNAPSHOT.presentation?.locale,'vi');
assert.equal(SKILL_GATEWAY_SNAPSHOT.presentation?.mode,'plain');
assert.equal(SKILL_GATEWAY_SNAPSHOT.presentation?.hide_internal_ids,true);
for(const [skillId,meta] of Object.entries(SKILL_GATEWAY_SNAPSHOT.skills)){
  assert.equal(typeof meta.display_name,'string',`${skillId}: display name type`);
  assert.ok(meta.display_name.trim(),`${skillId}: display name required`);
  assert.equal(meta.display_name.includes('_'),false,`${skillId}: display name underscore`);
}

const cases=[
  ['giải thích bác sĩ nội trú','core_reasoning','FAST','Giải thích và suy luận'],
  ['sửa lỗi API này','debugging','STANDARD','Sửa lỗi'],
  ['viết quảng cáo giày cho quý bà','advertising_copy','FAST','Viết quảng cáo'],
  ['so sánh hai phương án','comparison','FAST','So sánh'],
  ['dịch đoạn này sang tiếng Anh','translation','FAST','Dịch thuật'],
  ['quét market BTC live','trading_router','DEEP','Phân tích giao dịch'],
];
for(const [text,skill,profile,name] of cases){
  const route=routeSkillRequest({text},SKILL_GATEWAY_SNAPSHOT);
  assert.equal(route.primarySkill,skill,`${text}: skill`);
  assert.equal(route.primarySkillName,name,`${text}: easy name`);
  assert.equal(route.profile,profile,`${text}: profile`);
  assert.equal(route.externalRoutingCalls,0,`${text}: external calls`);
  assert.equal(route.sourceSha,SKILL_GATEWAY_SNAPSHOT.source_sha,`${text}: source sha`);
  assert.ok(route.capsuleHash,`${text}: capsule`);
}
const fallback=routeSkillRequest({text:'zxqv một ý định chưa từng được định tuyến'},SKILL_GATEWAY_SNAPSHOT);
assert.equal(fallback.primarySkill,'core_reasoning');
assert.equal(fallback.primarySkillName,'Giải thích và suy luận');
assert.equal(fallback.externalRoutingCalls,0);
console.log(`SKILL_GATEWAY_REAL_SNAPSHOT_TESTS=PASS source_sha=${SKILL_GATEWAY_SNAPSHOT.source_sha}`);
