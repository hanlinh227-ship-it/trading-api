import assert from 'node:assert/strict';
import {routeSkillRequest} from './skill-gateway.js';
import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';

const cases=[
  ['giải thích bác sĩ nội trú','core_reasoning','FAST'],
  ['sửa lỗi API này','debugging','STANDARD'],
  ['viết quảng cáo giày cho quý bà','advertising_copy','FAST'],
  ['so sánh hai phương án','comparison','FAST'],
  ['dịch đoạn này sang tiếng Anh','translation','FAST'],
  ['quét market BTC live','trading_router','DEEP'],
];
for(const [text,skill,profile] of cases){
  const route=routeSkillRequest({text},SKILL_GATEWAY_SNAPSHOT);
  assert.equal(route.primarySkill,skill,`${text}: skill`);
  assert.equal(route.profile,profile,`${text}: profile`);
  assert.equal(route.externalRoutingCalls,0,`${text}: external calls`);
  assert.equal(route.sourceSha,SKILL_GATEWAY_SNAPSHOT.source_sha,`${text}: source sha`);
  assert.ok(route.capsuleHash,`${text}: capsule`);
}
const fallback=routeSkillRequest({text:'zxqv một ý định chưa từng được định tuyến'},SKILL_GATEWAY_SNAPSHOT);
assert.equal(fallback.primarySkill,'core_reasoning');
assert.equal(fallback.externalRoutingCalls,0);
console.log(`SKILL_GATEWAY_REAL_SNAPSHOT_TESTS=PASS source_sha=${SKILL_GATEWAY_SNAPSHOT.source_sha}`);
