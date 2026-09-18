import assert from 'node:assert/strict';
import {healthKey,modelFingerprint,readModelHealth,recordModelExecutionHealth,writeProbeHealth} from './model-mesh/health-store.js';

class FakeKV{
  constructor(){this.rows=new Map();this.puts=[];}
  async get(key){return this.rows.get(key)||null;}
  async put(key,value,options){this.rows.set(key,value);this.puts.push({key,value,options});}
}

const model={provider_id:'groq',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss',free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z'};
const sourceSha='a'.repeat(40),nowMs=Date.parse('2026-09-15T12:00:00Z');
const fingerprint=await modelFingerprint(model);
assert.match(fingerprint,/^[a-f0-9]{64}$/);
// Evidence lives in a per-revision bucket. Two revisions therefore cannot
// share a slot, so a probe belonging to one can never overwrite the other's.
assert.equal(healthKey(model,fingerprint,sourceSha),`brain:model-mesh:health:v1:groq:${sourceSha}:${fingerprint}`);
assert.notEqual(healthKey(model,fingerprint,sourceSha),healthKey(model,fingerprint,'b'.repeat(40)));
// Unpinned evidence gets its own bucket rather than answering for a revision.
assert.equal(healthKey(model,fingerprint),`brain:model-mesh:health:v1:groq:unpinned:${fingerprint}`);
assert.equal(healthKey(model,fingerprint,'not-a-sha!!'),`brain:model-mesh:health:v1:groq:unpinned:${fingerprint}`.replace('unpinned','aa'));

assert.equal((await readModelHealth(null,model,{sourceSha,nowMs})).state,'CONFIGURED');
assert.equal((await readModelHealth(null,{...model,free_status:'trial_credit'},{sourceSha,nowMs})).state,'NOT_ELIGIBLE');

const kv=new FakeKV();
const pass=await writeProbeHealth(kv,model,{ok:true,latencyMs:42},{sourceSha,nowMs,delay:async()=>{}});
assert.equal(pass.state,'LIVE_HEALTHY');
assert.equal((await readModelHealth(kv,model,{sourceSha,nowMs})).state,'LIVE_HEALTHY');
assert.equal(kv.puts.length,1);
const skipped=await recordModelExecutionHealth(kv,model,{ok:true,latencyMs:5},{sourceSha,nowMs:nowMs+1000,delay:async()=>{}});
assert.equal(skipped.storeCategory,'SCHEDULED_PROBE_OWNS_SUCCESS_REFRESH');assert.equal(kv.puts.length,1);
assert.ok(kv.puts[0].options.expirationTtl>=60);
for(const forbidden of ['prompt','response','credential','secret','token','apiKey'])assert.equal(kv.puts[0].value.includes(forbidden),false,forbidden);

const cooldown=await writeProbeHealth(kv,model,{ok:false,category:'RATE_LIMITED',latencyMs:12},{sourceSha,nowMs:nowMs+1000,delay:async()=>{}});
assert.equal(cooldown.state,'COOLDOWN');
assert.equal(cooldown.category,'RATE_LIMITED');

const quarantined=await writeProbeHealth(kv,model,{ok:false,category:'AUTH_FAILED'},{sourceSha,nowMs:nowMs+2000,delay:async()=>{}});
assert.equal(quarantined.state,'QUARANTINED');

const stale=await readModelHealth(kv,model,{sourceSha,nowMs:Date.parse(quarantined.expiresAt)+1});
assert.equal(stale.state,'DEGRADED');
assert.equal(stale.category,'STALE_EVIDENCE');

// Cross-revision leakage is now structural, not merely detected: another
// revision reads its OWN bucket, which is empty, so there is nothing of ours
// for it to inherit or to overwrite.
const otherRevision=await readModelHealth(kv,model,{sourceSha:'b'.repeat(40),nowMs:nowMs+3000});
assert.notEqual(otherRevision.state,'LIVE_HEALTHY');
assert.equal(otherRevision.category,'NO_LIVE_EVIDENCE');

// The body check stays as defence in depth: a record that somehow lands in the
// right bucket while claiming another revision is still refused.
const planted=await modelFingerprint(model);
kv.rows.set(healthKey(model,planted,sourceSha),JSON.stringify({
  schemaVersion:1,providerId:'groq',modelId:model.model_id,fingerprint:planted,
  sourceSha:'c'.repeat(40),state:'LIVE_HEALTHY',category:null,
  observedAt:new Date(nowMs).toISOString(),expiresAt:new Date(nowMs+600000).toISOString(),
  latencyMs:1,consecutiveFailures:0,cooldownUntil:null,
}));
const mismatch=await readModelHealth(kv,model,{sourceSha,nowMs:nowMs+3000});
assert.equal(mismatch.state,'DEGRADED');
assert.equal(mismatch.category,'SOURCE_REVISION_MISMATCH');

const changed={...model,model_id:'new-model'};
assert.equal((await readModelHealth(kv,changed,{sourceSha,nowMs:nowMs+3000})).state,'CONFIGURED');

console.log('model mesh health store contracts ok');
