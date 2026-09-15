import assert from 'node:assert/strict';
import {createMeshExecutor,resolveRuntimeWorker,providerConfigurationStatus} from './model-mesh/provider-client.js';

const skillSnapshot={source_sha:'a'.repeat(40),fallback_primary_skill:'core_reasoning',capsules:{core_reasoning:{skill_id:'core_reasoning',domain:'core',capsule_hash:'cap-core'}}};
const model={provider_id:'groq',model_id:'free-model',model_family:'family-free',free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',health:'healthy',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.9}},quality_scores:{core:0.9}};
const modelSnapshot={schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,models:[model]};
const routeSkill=({text})=>({profile:text==='fast'?'FAST':'STANDARD',primarySkill:'core_reasoning',domain:'core',capsuleHash:'cap-core',externalRoutingCalls:0});
let calls=0;
const fetchImpl=async(url,init)=>{calls+=1;assert.equal(String(url).startsWith('https://api.groq.com/openai/v1/'),true);assert.equal(String(init.headers.Authorization).includes('topsecret'),true);return new Response(JSON.stringify({choices:[{message:{content:'ok'}}]}),{status:200,headers:{'content-type':'application/json'}});};
const execute=createMeshExecutor({fetchImpl});
const rows=new Map();const TRADING_STATE={get:async key=>rows.get(key)||null,put:async(key,value)=>rows.set(key,value)};
const request=(body,headers={})=>new Request('https://example.com/brain/mesh/execute',{method:'POST',headers:{'content-type':'application/json',...headers},body:JSON.stringify(body)});

const resolved=resolveRuntimeWorker(model);
assert.equal(resolved.secret_name,'GROQ_API_KEY');
assert.equal(resolved.endpoint_url,'https://api.groq.com/openai/v1');
assert.equal('secret_value' in resolved,false);

let response=await execute(request({text:'hello'}),{MODEL_MESH_EXECUTION_ENABLED:'0',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,503);
response=await execute(request({text:'hello'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,401);
response=await execute(request({text:'fast'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,409);
response=await execute(request({text:'hello',dataClass:'SECRET'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,403);
response=await execute(request({text:'hello'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret',TRADING_STATE},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,503);
const {writeProbeHealth}=await import('./model-mesh/health-store.js');
await writeProbeHealth(TRADING_STATE,model,{ok:true,latencyMs:10},{sourceSha:modelSnapshot.source_sha,delay:async()=>{}});
response=await execute(request({text:'hello'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret',TRADING_STATE},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,200);
const body=await response.json();
assert.equal(calls,1);
assert.equal(JSON.stringify(body).includes('topsecret'),false);
assert.equal(body.results[0].verification_status,'unverified_model_output');

const statuses=await providerConfigurationStatus(modelSnapshot,{GROQ_API_KEY:'topsecret',TRADING_STATE});
const groq=statuses.find(row=>row.providerId==='groq');
const nvidia=statuses.find(row=>row.providerId==='nvidia_nim');
assert.equal(groq.configured,true);
assert.equal(groq.active,true);
assert.equal(groq.eligibleModelCount,1);
assert.equal(nvidia.configured,false);
assert.equal(JSON.stringify(statuses).includes('topsecret'),false);
console.log('model mesh execution boundaries and runtime bindings ok');
