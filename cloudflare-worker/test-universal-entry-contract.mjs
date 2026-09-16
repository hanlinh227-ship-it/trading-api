import assert from 'node:assert/strict';
import {normalizeUniversalRequest,classifyEntrySafety,effectiveProfile,degradedDecision} from './universal-entry-contract.js';

let req=normalizeUniversalRequest({text:'giải thích API',request_id:'r1',session_id:'s1'},'chatgpt','1.0');
let cls=classifyEntrySafety(req);
assert.equal(cls.profileFloor,'FAST');
assert.equal(cls.requiresOnlineBrain,false);
assert.equal(cls.safeDegradedAllowed,true);
assert.equal(effectiveProfile('FAST',cls.profileFloor),'FAST');
assert.deepEqual(degradedDecision({classification:cls,stableSnapshotAvailable:true}),{allowed:true,mode:'last_verified_stable',disclosureRequired:true});

req=normalizeUniversalRequest({text:'quét BTC live tìm entry',request_id:'r2',session_id:'s1',freshness:'live'},'chatgpt','1.0');
cls=classifyEntrySafety(req);
assert.equal(cls.profileFloor,'DEEP');
assert.equal(cls.requiresOnlineBrain,true);
assert.equal(cls.safeDegradedAllowed,false);
assert.equal(effectiveProfile('STANDARD',cls.profileFloor),'DEEP');
assert.equal(degradedDecision({classification:cls,stableSnapshotAvailable:true}).allowed,false);

req=normalizeUniversalRequest({text:'tạo báo cáo',request_id:'r3',session_id:'s1',tool_classes:['artifact_creation']},'claude','1.0');
cls=classifyEntrySafety(req);
assert.equal(cls.profileFloor,'STANDARD');
assert.equal(effectiveProfile('DEEP',cls.profileFloor),'DEEP','safety floor may never downgrade canonical router');
assert.equal(degradedDecision({classification:cls,stableSnapshotAvailable:true}).allowed,true);
assert.equal(degradedDecision({classification:cls,stableSnapshotAvailable:false}).allowed,false);

req=normalizeUniversalRequest({text:'x',request_id:'r4',session_id:'s1',data_class:'unknown'},'gemini','1.0');
assert.equal(req.data_class,'SECRET');
cls=classifyEntrySafety(req);
assert.equal(cls.profileFloor,'DEEP');
assert.equal(cls.safeDegradedAllowed,false);
assert.equal(degradedDecision({classification:cls,stableSnapshotAvailable:true}).allowed,false);

assert.throws(()=>normalizeUniversalRequest({text:'',request_id:'r5',session_id:'s1'},'chatgpt','1.0'),/invalid_text/);
assert.throws(()=>normalizeUniversalRequest({text:'ok',request_id:'',session_id:'s1'},'chatgpt','1.0'),/invalid_request_id/);

// A client may raise its own action class but never lower it: an explicit 'informational' on a
// live-trading text must not unlock safe-degraded serving from a stale snapshot.
req=normalizeUniversalRequest({text:'giao dịch BTC live, tìm entry ngay',request_id:'r6',session_id:'s1',freshness:'none',requested_action_class:'informational'},'chatgpt','1.0');
assert.equal(req.requested_action_class,'live_or_trading','explicit informational must not downgrade an inferred high-impact action');
cls=classifyEntrySafety(req);
assert.equal(cls.profileFloor,'DEEP');
assert.equal(cls.safeDegradedAllowed,false);
assert.equal(degradedDecision({classification:cls,stableSnapshotAvailable:true}).allowed,false);
req=normalizeUniversalRequest({text:'withdraw funds to my wallet',request_id:'r7',session_id:'s1',requested_action_class:'ordinary_research'},'claude','1.0');
assert.equal(req.requested_action_class,'financial');
// Raising is still allowed.
req=normalizeUniversalRequest({text:'giải thích bác sĩ nội trú',request_id:'r8',session_id:'s1',requested_action_class:'deployment_or_runtime_claim'},'gemini','1.0');
assert.equal(req.requested_action_class,'deployment_or_runtime_claim');

console.log('UNIVERSAL_ENTRY_CONTRACT_TESTS=PASS');
