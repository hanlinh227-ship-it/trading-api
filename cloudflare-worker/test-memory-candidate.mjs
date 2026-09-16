import assert from 'node:assert/strict';
import {createMemoryCandidateHandler} from './memory-candidate.js';

class FakeKV{
  constructor(){this.rows=new Map();}
  async get(key,type){const v=this.rows.get(key);if(v===undefined)return null;return type==='json'?JSON.parse(v):v;}
  async put(key,value){this.rows.set(key,String(value));}
  async delete(key){this.rows.delete(key);}
}
const kv=new FakeKV();
const env={BRAIN_CLIENT_CHATGPT_TOKEN:'cg',BRAIN_STATE:kv};
const handler=createMemoryCandidateHandler();
function req(body,token='cg'){
  return new Request('https://example.test/brain/memory/candidates',{method:'POST',headers:{'x-brain-client':'chatgpt',authorization:`Bearer ${token}`,'content-type':'application/json'},body:JSON.stringify(body)});
}

let res=await handler(req({candidate_id:'m1',domain:'engineering',scope:'project:ai_brain',content:'Use one canonical Brain authority.',source:'verified_test',confidence:0.9,created_at:'2026-09-16T03:00:00Z',evidence_refs:['spec:universal'],reusable:true,verified:true,non_sensitive:true}),env,{});
assert.equal(res.status,202);
let body=await res.json();
assert.equal(body.ok,true);
assert.equal(body.state,'candidate');
assert.equal(body.active,false);
assert.equal(body.stableWrite,false);
assert.ok(kv.rows.has('brain:v1:meta:candidate:m1'));

res=await handler(req({candidate_id:'m2',domain:'engineering',scope:'project:ai_brain',content:'api_key=SECRET123',source:'test',confidence:0.9,created_at:'2026-09-16T03:00:00Z',evidence_refs:['x'],reusable:true,verified:true,non_sensitive:true}),env,{});
assert.equal(res.status,400);
body=await res.json();
assert.equal(body.error,'candidate_rejected_sensitive');
assert.equal(kv.rows.has('brain:v1:meta:candidate:m2'),false);

res=await handler(req({candidate_id:'m3',domain:'engineering',scope:'project:ai_brain',content:'ok',source:'test',confidence:0.9,created_at:'2026-09-16T03:00:00Z',evidence_refs:['x'],raw_private_chat:'private'}),env,{});
assert.equal(res.status,400);

res=await handler(req({candidate_id:'m4',domain:'engineering',scope:'project:ai_brain',content:'ok',source:'test',confidence:0.9,created_at:'2026-09-16T03:00:00Z',evidence_refs:['x']},'bad'),env,{});
assert.equal(res.status,401);

// Cross-client separation: another principal may not overwrite an existing candidate id.
const envMulti={...env,BRAIN_CLIENT_CLAUDE_TOKEN:'cl'};
function reqAs(client,token,body){return new Request('https://example.test/brain/memory/candidates',{method:'POST',headers:{'x-brain-client':client,authorization:`Bearer ${token}`,'content-type':'application/json'},body:JSON.stringify(body)});}
const base={domain:'engineering',scope:'project:ai_brain',content:'Use one canonical Brain authority.',source:'verified_test',confidence:0.9,created_at:'2026-09-16T03:00:00Z',evidence_refs:['spec:universal'],reusable:true,verified:true,non_sensitive:true};
res=await handler(reqAs('claude','cl',{...base,candidate_id:'m1',content:'claude overwrote this'}),envMulti,{});
assert.equal(res.status,409,'another client must not overwrite an existing candidate id');
assert.equal((await res.json()).error,'candidate_conflict');
assert.equal(JSON.parse(kv.rows.get('brain:v1:meta:candidate:m1')).submitted_by,'chatgpt');
assert.equal(JSON.parse(kv.rows.get('brain:v1:meta:candidate:m1')).content,'Use one canonical Brain authority.');
// The owning client may still update its own pending candidate.
res=await handler(req({...base,candidate_id:'m1',content:'Use one canonical Brain authority (revised).'}),envMulti,{});
assert.equal(res.status,202);
// A reviewed candidate (confirmed/rejected/needs_reverify) can never be reset to 'candidate' by resubmission.
kv.rows.set('brain:v1:meta:candidate:m1',JSON.stringify({...JSON.parse(kv.rows.get('brain:v1:meta:candidate:m1')),state:'confirmed',active:true}));
res=await handler(req({...base,candidate_id:'m1',content:'reset attempt'}),envMulti,{});
assert.equal(res.status,409,'resubmission must not reset a reviewed candidate');
assert.equal(JSON.parse(kv.rows.get('brain:v1:meta:candidate:m1')).state,'confirmed');
// Credential patterns are rejected in every string field, not only content.
for(const patch of [{source:'Authorization: Bearer eyJabc.def.ghi'},{evidence_refs:['api_key=sk-live-123456']},{scope:'project:private_key=abc'},{content:'password: hunter2'}]){
  res=await handler(req({...base,candidate_id:'m9',...patch}),envMulti,{});
  assert.equal(res.status,400,`sensitive field must be rejected: ${JSON.stringify(patch)}`);
  assert.equal((await res.json()).error,'candidate_rejected_sensitive');
  assert.equal(kv.rows.has('brain:v1:meta:candidate:m9'),false);
}
// Identifier charset: key-delimiter and path characters cannot forge or collide KV keys, and never 500.
for(const patch of [{candidate_id:'a..b'},{candidate_id:'k:1'},{domain:'a:b'},{domain:'a b'},{scope:'x..y'},{candidate_id:'line\nbreak'}]){
  res=await handler(req({...base,candidate_id:'m10',...patch}),envMulti,{});
  assert.equal(res.status,400,`invalid identifier must be 400: ${JSON.stringify(patch)}`);
}

const passthrough=await handler(new Request('https://example.test/nope'),env,{});
assert.equal(passthrough,null);

console.log('MEMORY_CANDIDATE_TESTS=PASS');
