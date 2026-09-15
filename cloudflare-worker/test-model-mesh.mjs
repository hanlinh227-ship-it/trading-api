import assert from 'node:assert/strict';
import {buildModelMeshPlan} from './model-mesh-runtime.js';

const skillSnapshot={
  source_sha:'a'.repeat(40),release_id:'test',schema_version:1,presentation:{mode:'plain',locale:'vi'},fallback_primary_skill:'core_reasoning',
  capsules:{core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'answer',permissions:[],risk_ceiling:'LOW_RISK',capsule_hash:'cap-core',tools:[],sources:[]}},
};
const modelSnapshot={
  schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,generated_at:'2026-09-15T00:00:00Z',
  models:[
    {provider_id:'p1',model_id:'m1',model_family:'family-1',free_status:'recurring',health:'healthy',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.9}},quality_scores:{core:0.9},context_window:32000},
    {provider_id:'p2',model_id:'m2',model_family:'family-2',free_status:'recurring',health:'healthy',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{core:0.8},context_window:32000},
  ],
};

let externalFetchCount=0;
const noFetch=async()=>{externalFetchCount+=1;throw new Error('planner must not fetch');};

const fast=await buildModelMeshPlan({text:'hello',dataClass:'PUBLIC',hasImage:false,profile:'FAST',route:{profile:'FAST',primarySkill:'core_reasoning',externalRoutingCalls:0}}, {skillSnapshot,modelSnapshot,fetchImpl:noFetch});
assert.equal(fast.route.externalRoutingCalls,0);
assert.equal(fast.workers.length,0);

const standard=await buildModelMeshPlan({text:'analyze this architecture',dataClass:'PUBLIC',hasImage:false,profile:'STANDARD',route:{profile:'STANDARD',primarySkill:'core_reasoning',externalRoutingCalls:0}}, {skillSnapshot,modelSnapshot,fetchImpl:noFetch});
assert.equal(standard.route.externalRoutingCalls,0);
assert.ok(standard.workers.length<=2);
assert.equal(externalFetchCount,0);
assert.equal(standard.routingAuthority,false);
assert.equal(standard.reasoningAuthority,false);
console.log('model mesh planner contracts ok');
