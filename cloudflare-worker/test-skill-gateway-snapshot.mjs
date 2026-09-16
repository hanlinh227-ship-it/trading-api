import assert from 'node:assert/strict';
import {routeSkillRequest} from './skill-gateway.js';
import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';
import {UNIVERSAL_ENTRY_DEEP_TERMS} from './universal-entry-contract.js';

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
  ['quét market BTC live','multi_market_analysis','DEEP','Phân tích nhiều thị trường'],
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
// runtime.yaml: financial / destructive / credential-sensitive / live / deploy requests are DEEP and
// require authority. They must never route FAST regardless of which specialist skill wins.
const highRisk=[
  'withdraw my funds now','rút tiền về ví','rut tien ve vi','chuyển tiền cho tôi','chuyen tien cho toi','transfer funds to this address','send money to my friend',
  'seed phrase của tôi là gì','cụm từ khôi phục ví','private key','passphrase','api key của tôi','secret token','mật khẩu','mat khau',
  'sign transaction','ký giao dịch này','broadcast transaction','swap tokens on uniswap','bridge assets to arbitrum','payment for the invoice','thanh toan hoa don',
  'wallet balance transfer','xóa database','xoa du lieu','delete production database','rm -rf /var/www','drop table users','destroy the cluster',
  'summarize how to rút tiền','translate rút tiền to english','cấp quyền admin cho user','revoke scope for this token','deploy now','triển khai lên production',
];
for(const text of highRisk){
  const route=routeSkillRequest({text},SKILL_GATEWAY_SNAPSHOT);
  assert.equal(route.profile,'DEEP',`${text}: high-risk request must be DEEP, got ${route.profile}`);
  assert.equal(route.requiresAuthority,true,`${text}: high-risk request must require authority`);
}
// Benign requests must still be FAST so escalation vocabulary does not silently kill the FAST path.
for(const text of ['giải thích bác sĩ nội trú','so sánh hai phương án','viết quảng cáo giày cho quý bà']){
  assert.equal(routeSkillRequest({text},SKILL_GATEWAY_SNAPSHOT).profile,'FAST',`${text}: must stay FAST`);
}
// The adapter-side DEEP floor table is a mirror, never a second router: every term must be in the snapshot.
const norm=v=>String(v).normalize('NFKC').toLocaleLowerCase('und').replace(/\s+/g,' ').trim();
const snapshotDeep=new Set((SKILL_GATEWAY_SNAPSHOT.profile_escalation?.DEEP||[]).map(norm));
for(const [,terms] of UNIVERSAL_ENTRY_DEEP_TERMS)for(const term of terms)assert.ok(snapshotDeep.has(norm(term)),`universal-entry DEEP term missing from canonical routing_aliases DEEP escalation: ${term.trim()}`);
console.log(`SKILL_GATEWAY_REAL_SNAPSHOT_TESTS=PASS source_sha=${SKILL_GATEWAY_SNAPSHOT.source_sha}`);
