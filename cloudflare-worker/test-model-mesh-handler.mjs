import assert from 'node:assert/strict';
import {createModelMeshHandler} from './model-mesh-handler.js';

const skillSnapshot={source_sha:'a'.repeat(40),release_id:'test',schema_version:1,presentation:{mode:'plain',locale:'vi'},fallback_primary_skill:'core_reasoning',capsules:{core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'answer',permissions:[],risk_ceiling:'LOW_RISK',capsule_hash:'cap-core',tools:[],sources:[]}}};
const activeModel={provider_id:'groq',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss-120b',free_status:'account_specific',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',context_window:131072,health:'degraded',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{}};
const modelSnapshot={schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,generated_at:'2026-09-15T00:00:00Z',models:[activeModel]};
const activeIndex={schema_version:1,source_sha:modelSnapshot.source_sha,mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,generated_at:'2026-09-15T00:00:00Z',hard_gate_policy:{default_enabled:false,min_verified_candidates:2,min_coverage_ratio:0.8,overrides:{}},coverage:{},entries:[{candidate_key:'groq:openai/gpt-oss-120b',provider_id:'groq',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss-120b',capability_evidence:{text_reasoning:{state:'PROVISIONAL',score:0.8,evidence_ids:[],measured_at:null}}}]};
const routeSkill=({text})=>({profile:text==='fast'?'FAST':'STANDARD',primarySkill:'core_reasoning',domain:'core',externalRoutingCalls:0});
const probeProviders=async(_env)=>({ok:true,mode:'FREE_ONLY',results:[{providerId:'groq',modelId:'openai/gpt-oss-120b',configured:true,ok:true,status:200,latencyMs:12}]});
const handler=createModelMeshHandler({skillSnapshot,modelSnapshot,activeIndex,routeSkill,probeProviders});
const rows=new Map();const TRADING_STATE={get:async key=>rows.get(key)||null,put:async(key,value)=>rows.set(key,value)};
const {writeProbeHealth}=await import('./model-mesh/health-store.js');
await writeProbeHealth(TRADING_STATE,activeModel,{ok:true,latencyMs:12},{sourceSha:modelSnapshot.source_sha,delay:async()=>{}});

let response=await handler(new Request('https://example.com/brain/mesh/health'),{GROQ_API_KEY:'do-not-leak',MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',TRADING_STATE});
assert.equal(response.status,200);
let body=await response.json();
assert.equal(body.ok,true);
assert.equal(body.mode,'FREE_ONLY');
assert.equal(body.routingAuthority,false);
assert.equal(body.reasoningAuthority,false);
assert.equal(body.maxParallelDeep,4);
assert.equal(body.sourceSha,modelSnapshot.source_sha);
assert.equal(body.executionEnabled,true);
assert.equal(body.executionTokenConfigured,true);
assert.equal(body.eligibleModelCount,1);
assert.equal(body.activeProviderCount,1);
assert.deepEqual(body.capabilityEvidence,{indexLoaded:true,verifiedRecords:0,enabledHardGates:0});
const groq=body.providers.find(row=>row.providerId==='groq');
const nvidia=body.providers.find(row=>row.providerId==='nvidia_nim');
assert.equal(groq.configured,true);
assert.equal(groq.active,true);
assert.equal(groq.liveHealthyModelCount,1);
assert.equal(nvidia.configured,false);
assert.equal(JSON.stringify(body).includes('do-not-leak'),false);
assert.equal(JSON.stringify(body).includes('GROQ_API_KEY'),false);
assert.equal(JSON.stringify(body).includes('provider-declaration'),false);

response=await handler(new Request('https://example.com/brain/mesh/probe',{method:'POST'}),{MODEL_MESH_EXECUTION_TOKEN:'token'});
assert.equal(response.status,401);
response=await handler(new Request('https://example.com/brain/mesh/probe',{method:'POST',headers:{'x-model-mesh-token':'token'}}),{MODEL_MESH_EXECUTION_TOKEN:'token',TRADING_STATE});
assert.equal(response.status,200);
// The manual/deploy probe is the same work as the cron and self-heal probes, so it must
// record the shared claim: otherwise the Worker cron fires right after a deploy probe,
// re-spends free quota and races the deploy's health writes (last-writer-wins per key).
assert.ok(rows.has('brain:model-mesh:self-heal:v1:lock'),'manual probe must record the shared self-heal claim');
body=await response.json();
assert.equal(body.ok,true);
assert.equal(body.results[0].providerId,'groq');
assert.equal(JSON.stringify(body).includes('token'),false);

response=await handler(new Request('https://example.com/brain/mesh/plan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'fast'})}),{GROQ_API_KEY:'do-not-leak',TRADING_STATE});
assert.equal(response.status,200);
body=await response.json();
assert.equal(body.route.externalRoutingCalls,0);
assert.equal(body.workers.length,0);

response=await handler(new Request('https://example.com/brain/mesh/plan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'normal',dataClass:'SECRET'})}));
assert.equal(response.status,403);
assert.throws(()=>createModelMeshHandler({skillSnapshot,modelSnapshot,activeIndex:{...activeIndex,source_sha:'b'.repeat(40)},routeSkill}),/MODEL_MESH_SOURCE_SHA_MISMATCH/);
console.log('model mesh handler contracts, probe auth and sanitized provider health ok');
