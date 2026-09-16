import assert from 'node:assert/strict';
import {sanitizeEvent,recordUniversalEvent} from './universal-telemetry.js';
import {createStateStores} from './universal-state.js';

class FakeKV{
  constructor(){this.rows=new Map();}
  async get(key,type){const v=this.rows.get(key);if(v===undefined)return null;return type==='json'?JSON.parse(v):v;}
  async put(key,value){this.rows.set(key,String(value));}
  async delete(key){this.rows.delete(key);}
}

const sanitized=sanitizeEvent({
  event_type:'route',client_id:'chatgpt',request_id:'r1',profile:'DEEP',domain:'engineering',primary_skill:'software_architecture',capsule_hash:'abc',release_id:'4.10.1',source_sha:'f'.repeat(40),latency_ms:12.3,status:'ok',
  raw_private_chat:'secret chat',prompt:'do not store me',credentials:'pw',chain_of_thought:'hidden',account_data:'x',private_tool_payload:{x:1},
});
assert.equal(sanitized.client_id,'chatgpt');
assert.equal(sanitized.profile,'DEEP');
for(const forbidden of ['raw_private_chat','prompt','credentials','chain_of_thought','account_data','private_tool_payload'])assert.equal(forbidden in sanitized,false);

const kv=new FakeKV();
const stores=createStateStores({BRAIN_STATE:kv});
const result=await recordUniversalEvent(stores,{event_type:'route',client_id:'claude',request_id:'r2',profile:'STANDARD',status:'ok'});
assert.equal(result.ok,true);
assert.equal([...kv.rows.keys()].some(k=>k.startsWith('brain:v1:meta:telemetry:')),true);

const unavailable=await recordUniversalEvent(createStateStores({}),{event_type:'route',client_id:'gemini',request_id:'r3',profile:'DEEP',status:'failed'});
assert.equal(unavailable.ok,false);
assert.equal(unavailable.unavailable,true);

assert.throws(()=>sanitizeEvent({event_type:'route',request_id:'x'.repeat(5000)}),/telemetry_field_too_large/);
console.log('UNIVERSAL_TELEMETRY_TESTS=PASS');
