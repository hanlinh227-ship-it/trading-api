import assert from 'node:assert/strict';
import {createMemoryContextHandler} from './memory-context-handler.js';
import {createStateStores} from './universal-state.js';

class FakeKV{
  constructor(){this.rows=new Map();}
  async get(key,type){const v=this.rows.get(key);if(v===undefined)return null;return type==='json'?JSON.parse(v):v;}
  async put(key,value){this.rows.set(key,String(value));}
  async delete(key){this.rows.delete(key);}
  async list({prefix='',limit=100}={}){const names=[...this.rows.keys()].filter(k=>k.startsWith(prefix)).sort().slice(0,limit);return {keys:names.map(name=>({name})),list_complete:true,cursor:''};}
}

const kv=new FakeKV();
const env={BRAIN_STATE:kv,BRAIN_EVERGREEN_TOKEN:'evergreen-token',BRAIN_CLIENT_CHATGPT_TOKEN:'chatgpt-token',BRAIN_CLIENT_CLAUDE_TOKEN:'claude-token',BRAIN_CLIENT_GEMINI_TOKEN:'gemini-token'};
const stores=createStateStores(env);
const handler=createMemoryContextHandler();
const candidate={candidate_id:'m-123',domain:'coding',scope:'project:trading-api',content:'Universal Fabric uses one canonical Brain authority and exact SHA metadata.',source:'verified-task',confidence:0.92,created_at:'2026-09-16T00:00:00Z',evidence_refs:['eval:1'],reusable:true,verified:true,non_sensitive:true,conflicts_with:[],submitted_by:'chatgpt',state:'candidate',active:false,stable_write:false};
await stores.metadata.put('candidate:m-123',candidate);

function request(client,token,path,body){return new Request(`https://example.test${path}`,{method:'POST',headers:{'x-brain-client':client,authorization:`Bearer ${token}`,'content-type':'application/json'},body:JSON.stringify(body)});}

let res=await handler(request('chatgpt','chatgpt-token','/brain/memory/review',{candidate_id:'m-123',evidence_count:2,current:true,conflict:false,reviewed_at:'2026-09-16T01:00:00Z'}),env);
assert.equal(res.status,403,'normal user adapter may not review candidate memory');

res=await handler(request('evergreen','evergreen-token','/brain/memory/review',{candidate_id:'m-123',evidence_count:2,current:true,conflict:false,reviewed_at:'2026-09-16T01:00:00Z'}),env);
assert.equal(res.status,200);
let body=await res.json();
assert.equal(body.decision,'confirmed');
assert.equal(body.state,'active');
const active=await stores.metadata.get('memory:coding:project:trading-api:m-123');
assert.equal(active.state,'active');
assert.equal(active.active,true);

res=await handler(request('chatgpt','chatgpt-token','/brain/context/query',{domain:'coding',scope:'project:trading-api',profile:'FAST',query:'canonical brain',limit:1}),env);
assert.equal(res.status,400);
body=await res.json();
assert.equal(body.error,'fast_memory_preload_forbidden');

res=await handler(request('chatgpt','chatgpt-token','/brain/context/query',{domain:'coding',scope:'project:trading-api',profile:'STANDARD',query:'canonical Brain authority',limit:4}),env);
assert.equal(res.status,200);
body=await res.json();
assert.equal(body.ok,true);
assert.equal(body.retrievalMode,'lexical');
assert.equal(body.count,1);
assert.equal(body.items[0].memory_id,'m-123');
assert.equal('raw_private_chat' in body.items[0],false);

await stores.metadata.put('memory:coding:project:trading-api:m-old',{...active,memory_id:'m-old',state:'superseded',active:false,content:'canonical Brain old'});
await stores.metadata.put('candidate:not-active',{...candidate,candidate_id:'not-active',content:'canonical Brain candidate'});
res=await handler(request('chatgpt','chatgpt-token','/brain/context/query',{domain:'coding',scope:'project:trading-api',profile:'DEEP',query:'canonical Brain',limit:8}),env);
body=await res.json();
assert.equal(body.items.some(item=>item.memory_id==='m-old'),false);
assert.equal(body.items.some(item=>item.memory_id==='not-active'),false);

res=await handler(new Request('https://example.test/not-memory'),env);
assert.equal(res,null);

console.log('MEMORY_CONTEXT_HANDLER_TESTS=PASS');
