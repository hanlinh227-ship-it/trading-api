import assert from 'node:assert/strict';
import {createStateStores} from './universal-state.js';

class FakeKV{
  constructor(){this.rows=new Map();}
  async get(key,type){const v=this.rows.get(key);if(v===undefined)return null;return type==='json'?JSON.parse(v):v;}
  async put(key,value){this.rows.set(key,String(value));}
  async delete(key){this.rows.delete(key);}
}

const kv=new FakeKV();
const stores=createStateStores({BRAIN_STATE:kv});
assert.equal(stores.backend,'BRAIN_STATE');
assert.equal(stores.authority,false);
await stores.kv.put('health',{ok:true});
assert.deepEqual(await stores.kv.get('health'),{ok:true});
assert.equal(kv.rows.has('brain:v1:health'),true);

await stores.metadata.put('candidate:1',{state:'candidate'});
assert.deepEqual(await stores.metadata.get('candidate:1'),{state:'candidate'});
assert.equal(kv.rows.has('brain:v1:meta:candidate:1'),true);

await stores.kv.delete('health');
assert.equal(await stores.kv.get('health'),null);

const fallbackKv=new FakeKV();
const fallback=createStateStores({TRADING_STATE:fallbackKv});
assert.equal(fallback.backend,'TRADING_STATE_NAMESPACED');
await fallback.kv.put('x',{value:1});
assert.equal(fallbackKv.rows.has('brain:v1:x'),true);

const none=createStateStores({});
assert.equal(none.backend,'UNAVAILABLE');
assert.deepEqual(await none.kv.get('x'),{unavailable:true});
assert.deepEqual(await none.vector.query('hello'),{unavailable:true,items:[]});
assert.deepEqual(await none.queue.enqueue({job:'x'}),{unavailable:true});
assert.deepEqual(await none.locks.withLease('k',async()=>42),{unavailable:true});

console.log('UNIVERSAL_STATE_TESTS=PASS');
