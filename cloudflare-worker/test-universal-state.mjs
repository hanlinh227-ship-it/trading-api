import assert from 'node:assert/strict';
import {createStateStores,UNIVERSAL_STATE_META_PREFIX,UNIVERSAL_STATE_PREFIX} from './universal-state.js';

class FakeKV{
  constructor(){this.rows=new Map();}
  async get(key,type){const v=this.rows.get(key);if(v===undefined)return null;return type==='json'?JSON.parse(v):v;}
  async put(key,value){this.rows.set(key,String(value));}
  async delete(key){this.rows.delete(key);}
  async list({prefix='',limit=100}={}){
    const names=[...this.rows.keys()].filter(k=>k.startsWith(prefix)).sort().slice(0,limit);
    return {keys:names.map(name=>({name})),list_complete:true,cursor:''};
  }
}

assert.equal(UNIVERSAL_STATE_PREFIX,'brain:v1:');
assert.equal(UNIVERSAL_STATE_META_PREFIX,'brain:v1:meta:');

const kv=new FakeKV();
kv.rows.set('trading:live','{"protected":true}');
const stores=createStateStores({BRAIN_STATE:kv});
assert.equal(stores.backend,'BRAIN_STATE');
assert.equal(stores.authority,false);
await stores.kv.put('health',{ok:true});
assert.deepEqual(await stores.kv.get('health'),{ok:true});
assert.equal(kv.rows.has('brain:v1:health'),true);
assert.equal(kv.rows.get('trading:live'),'{"protected":true}');

await stores.metadata.put('candidate:a',{state:'candidate'});
await stores.metadata.put('candidate:b',{state:'candidate'});
assert.deepEqual(await stores.metadata.get('candidate:a'),{state:'candidate'});
assert.equal(kv.rows.has('brain:v1:meta:candidate:a'),true);
const rows=await stores.metadata.list('candidate:',20);
assert.equal(rows.unavailable,false);
assert.deepEqual(rows.items.map(x=>x.key),['candidate:a','candidate:b']);
assert.deepEqual(rows.items[0].value,{state:'candidate'});
assert.equal(rows.cursor,null);
assert.throws(()=>stores.metadata.list('candidate:',0),/invalid_state_limit/);
assert.throws(()=>stores.metadata.list('candidate:',101),/invalid_state_limit/);

await stores.kv.delete('health');
assert.equal(await stores.kv.get('health'),null);

const fallbackKv=new FakeKV();
fallbackKv.rows.set('position:BTCUSDT','{"qty":1}');
const fallback=createStateStores({TRADING_STATE:fallbackKv});
assert.equal(fallback.backend,'TRADING_STATE_NAMESPACED');
await fallback.kv.put('x',{value:1});
assert.equal(fallbackKv.rows.has('brain:v1:x'),true);
assert.equal(fallbackKv.rows.get('position:BTCUSDT'),'{"qty":1}');

const none=createStateStores({});
assert.equal(none.backend,'UNAVAILABLE');
assert.deepEqual(await none.kv.get('x'),{unavailable:true});
assert.deepEqual(await none.kv.list('x',5),{unavailable:true,items:[],cursor:null});
assert.deepEqual(await none.vector.query('hello'),{unavailable:true,items:[]});
assert.deepEqual(await none.queue.enqueue({job:'x'}),{unavailable:true});
assert.deepEqual(await none.locks.withLease('k',async()=>42),{unavailable:true});

console.log('UNIVERSAL_STATE_TESTS=PASS');
