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

const passthrough=await handler(new Request('https://example.test/nope'),env,{});
assert.equal(passthrough,null);

console.log('MEMORY_CANDIDATE_TESTS=PASS');
