import assert from 'node:assert/strict';
import {createBrainAdapter} from './index.mjs';

const snapshot={
  schema_version:1,source_sha:'a'.repeat(40),release_id:'4.11.0-test',generated_at:'2026-09-16T00:00:00Z',fallback_primary_skill:'core_reasoning',
  presentation:{locale:'vi',mode:'plain',hide_internal_ids:true,no_underscore_display_names:true},
  profiles:{FAST:{primary_skill_count:1,skill_capsule_required:true},STANDARD:{primary_skill_count:1,skill_capsule_required:true},DEEP:{primary_skill_count:1,skill_capsule_required:true}},
  domains:{core:['core_reasoning'],trading:['trading_router']},
  skills:{
    core_reasoning:{id:'core_reasoning',display_name:'Giải thích',domain:'core',aliases:['giải thích'],triggers:['explain','research'],excludes:[],priority:80,tools:[],primary_selectable:true},
    trading_router:{id:'trading_router',display_name:'Phân tích giao dịch',domain:'trading',aliases:['giao dịch'],triggers:['trading'],excludes:[],priority:90,tools:[],primary_selectable:true},
  },
  capsules:{
    core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'Explain precisely.',permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:'core-hash'},
    trading_router:{skill_id:'trading_router',domain:'trading',output_contract:'Research trading.',permissions:['read_only'],risk_ceiling:'financial',capsule_hash:'trade-hash'},
  },
  profile_escalation:{STANDARD:['project','research'],DEEP:['deploy','production','live','trading','giao dịch']},fresh_state_terms:['hiện tại','live'],hashes:{router:'r',runtime:'u'}
};

let calls=0;
const unreachable=async()=>{calls++;throw new Error('network');};
const adapter=createBrainAdapter({clientId:'chatgpt',token:'token',endpoint:'https://brain.example',hotSnapshot:snapshot,stableSnapshot:snapshot,fetchImpl:unreachable});

const fast=await adapter.route({text:'explain recursion',request_id:'r1',session_id:'s1',data_class:'PUBLIC'});
assert.equal(fast.profile,'FAST');
assert.equal(fast.local,true);
assert.equal(fast.degraded,false);
assert.equal(calls,0,'safe FAST must be zero RTT');

const standard=await adapter.route({text:'research project architecture',request_id:'r2',session_id:'s1',data_class:'PUBLIC'});
assert.equal(calls,1);
assert.equal(standard.profile,'STANDARD');
assert.equal(standard.degraded,true);
assert.equal(standard.degradedReason,'cloud_brain_unavailable');

await assert.rejects(()=>adapter.route({text:'trading BTC live',request_id:'r3',session_id:'s1',data_class:'PUBLIC',freshness:'live'}),/brain_unavailable_fail_closed/);
assert.equal(calls,2,'protected request must attempt online Brain before failing closed');

await assert.rejects(()=>adapter.queryContext({profile:'FAST',domain:'core',scope:'x',query:'x'}),/fast_memory_preload_forbidden/);

let captured=null;
const okFetch=async(url,init)=>{calls++;captured={url,init};return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});};
const online=createBrainAdapter({clientId:'claude',token:'secret-token',endpoint:'https://brain.example/',hotSnapshot:null,fetchImpl:okFetch});
const onlineResult=await online.route({text:'research source',request_id:'r4',session_id:'s2',data_class:'PUBLIC'});
assert.equal(onlineResult.ok,true);
assert.equal(captured.url,'https://brain.example/brain/universal/route');
assert.equal(captured.init.headers['x-brain-client'],'claude');
assert.equal(captured.init.headers.authorization,'Bearer secret-token');
assert.equal(JSON.stringify(onlineResult).includes('secret-token'),false);

console.log('UNIVERSAL_BRAIN_ADAPTER_TESTS=PASS');
