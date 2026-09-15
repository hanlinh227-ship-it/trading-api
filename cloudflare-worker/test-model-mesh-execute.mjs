import assert from 'node:assert/strict';
import {createMeshExecutor} from './model-mesh/provider-client.js';

const skillSnapshot={source_sha:'a'.repeat(40),fallback_primary_skill:'core_reasoning',capsules:{core_reasoning:{skill_id:'core_reasoning',domain:'core',capsule_hash:'cap-core'}}};
const model={provider_id:'groq',model_id:'free-model',model_family:'family-free',free_status:'recurring',health:'healthy',privacy_class:'public_safe',endpoint_family:'openai_compatible',endpoint_url:'https://provider.invalid/v1',secret_name:'GROQ_API_KEY',capabilities:{text_reasoning:{supported:true,score:0.9}},quality_scores:{core:0.9}};
const modelSnapshot={schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,models:[model]};
const routeSkill=({text})=>({profile:text==='fast'?'FAST':'STANDARD',primarySkill:'core_reasoning',domain:'core',capsuleHash:'cap-core',externalRoutingCalls:0});
let calls=0;
const fetchImpl=async(_url,init)=>{calls+=1;assert.equal(String(init.headers.Authorization).includes('topsecret'),true);return new Response(JSON.stringify({choices:[{message:{content:'ok'}}]}),{status:200,headers:{'content-type':'application/json'}});};
const execute=createMeshExecutor({fetchImpl});
const request=(body,headers={})=>new Request('https://example.com/brain/mesh/execute',{method:'POST',headers:{'content-type':'application/json',...headers},body:JSON.stringify(body)});

let response=await execute(request({text:'hello'}),{MODEL_MESH_EXECUTION_ENABLED:'0',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,503);
response=await execute(request({text:'hello'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,401);
response=await execute(request({text:'fast'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,409);
response=await execute(request({text:'hello',dataClass:'SECRET'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,403);
response=await execute(request({text:'hello'},{'x-model-mesh-token':'token'}),{MODEL_MESH_EXECUTION_ENABLED:'1',MODEL_MESH_EXECUTION_TOKEN:'token',GROQ_API_KEY:'topsecret'},{skillSnapshot,modelSnapshot,routeSkill});
assert.equal(response.status,200);
const body=await response.json();
assert.equal(calls,1);
assert.equal(JSON.stringify(body).includes('topsecret'),false);
assert.equal(body.results[0].verification_status,'unverified_model_output');
console.log('model mesh execution boundaries ok');
