import assert from 'node:assert/strict';
import {createModelMeshHandler} from './model-mesh-handler.js';

const skillSnapshot={source_sha:'a'.repeat(40),release_id:'test',schema_version:1,presentation:{mode:'plain',locale:'vi'},fallback_primary_skill:'core_reasoning',capsules:{core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'answer',permissions:[],risk_ceiling:'LOW_RISK',capsule_hash:'cap-core',tools:[],sources:[]}}};
const modelSnapshot={schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,generated_at:'2026-09-15T00:00:00Z',models:[]};
const routeSkill=({text})=>({profile:text==='fast'?'FAST':'STANDARD',primarySkill:'core_reasoning',externalRoutingCalls:0});
const handler=createModelMeshHandler({skillSnapshot,modelSnapshot,routeSkill});

let response=await handler(new Request('https://example.com/brain/mesh/health'));
assert.equal(response.status,200);
let body=await response.json();
assert.equal(body.ok,true);
assert.equal(body.mode,'FREE_ONLY');
assert.equal(body.routingAuthority,false);
assert.equal(body.reasoningAuthority,false);
assert.equal(body.maxParallelDeep,4);
assert.equal(body.sourceSha,modelSnapshot.source_sha);

response=await handler(new Request('https://example.com/brain/mesh/plan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'fast'})}));
assert.equal(response.status,200);
body=await response.json();
assert.equal(body.route.externalRoutingCalls,0);
assert.equal(body.workers.length,0);

response=await handler(new Request('https://example.com/brain/mesh/plan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'normal',dataClass:'SECRET'})}));
assert.equal(response.status,403);
console.log('model mesh handler contracts ok');
