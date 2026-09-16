import assert from 'node:assert/strict';
import {isSensitiveMemoryContent,promoteMemoryCandidate,reviewMemoryCandidate,supersedeMemory} from './memory-lifecycle.js';

const candidate={
  candidate_id:'m-123',domain:'coding',scope:'project:trading-api',content:'Universal Fabric uses one canonical Brain authority.',source:'verified-task',confidence:0.9,created_at:'2026-09-16T00:00:00Z',evidence_refs:['eval:1'],reusable:true,verified:true,non_sensitive:true,conflicts_with:[],submitted_by:'chatgpt',state:'candidate',active:false,
};

const review=reviewMemoryCandidate(candidate,{evidence_count:2,conflict:false,current:true,reviewed_at:'2026-09-16T01:00:00Z'});
assert.equal(review.decision,'confirmed');
const active=promoteMemoryCandidate(candidate,review);
assert.equal(active.state,'active');
assert.equal(active.active,true);
assert.equal(active.last_verified,'2026-09-16T01:00:00Z');
assert.deepEqual(active.provenance.evidence_refs,['eval:1']);

assert.throws(()=>promoteMemoryCandidate({...candidate,non_sensitive:false},review),/memory_promotion_blocked/);
assert.throws(()=>promoteMemoryCandidate({...candidate,confidence:0.54},review),/memory_promotion_blocked/);
assert.equal(reviewMemoryCandidate({...candidate,conflicts_with:['m-old']},{evidence_count:2,current:true,conflict:false}).decision,'rejected');
assert.equal(reviewMemoryCandidate(candidate,{evidence_count:0,current:true,conflict:false}).decision,'needs_reverify');
assert.equal(reviewMemoryCandidate(candidate,{evidence_count:1,current:true,conflict:true}).decision,'rejected');

const superseded=supersedeMemory(active,{memory_id:'m-124',last_verified:'2026-09-16T02:00:00Z'});
assert.equal(superseded.state,'superseded');
assert.equal(superseded.active,false);
assert.equal(superseded.superseded_by,'m-124');
assert.deepEqual(superseded.provenance,active.provenance);

const secret={...candidate,content:'api_key = top-secret-value'};
assert.equal(isSensitiveMemoryContent(secret),true);
assert.equal(reviewMemoryCandidate(secret,{evidence_count:10,current:true,conflict:false}).decision,'rejected');
assert.throws(()=>promoteMemoryCandidate(secret,{decision:'confirmed',evidence_count:10,current:true,conflict:false}),/memory_promotion_blocked/);
const rawChat={...candidate,raw_private_chat:'private text'};
assert.equal(isSensitiveMemoryContent(rawChat),true);
assert.equal(reviewMemoryCandidate(rawChat,{evidence_count:10,current:true,conflict:false}).decision,'rejected');

console.log('MEMORY_LIFECYCLE_TESTS=PASS');
