import assert from 'node:assert/strict';
import {buildModelMeshPlan} from './model-mesh-runtime.js';

const skillSnapshot={
  source_sha:'a'.repeat(40),release_id:'test',schema_version:1,presentation:{mode:'plain',locale:'vi'},fallback_primary_skill:'core_reasoning',
  capsules:{core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'answer',permissions:[],risk_ceiling:'LOW_RISK',capsule_hash:'cap-core',tools:[],sources:[]}},
};
const modelSnapshot={
  schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,generated_at:'2026-09-15T00:00:00Z',
  models:[
    {provider_id:'groq',model_id:'m1',model_family:'family-1',free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',context_window:131072,health:'healthy',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.9}},quality_scores:{core:0.9}},
    {provider_id:'openrouter',model_id:'m2',model_family:'family-2',free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',context_window:131072,health:'healthy',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{core:0.8}},
  ],
};
const activeIndex={
  schema_version:1,source_sha:modelSnapshot.source_sha,mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,generated_at:'2026-09-15T00:00:00Z',
  hard_gate_policy:{default_enabled:false,min_verified_candidates:2,min_coverage_ratio:0.8,overrides:{}},coverage:{},
  entries:modelSnapshot.models.map(model=>({candidate_key:`${model.provider_id}:${model.model_id}`,provider_id:model.provider_id,model_id:model.model_id,model_family:model.model_family,capability_evidence:{text_reasoning:{state:'PROVISIONAL',score:model.capabilities.text_reasoning.score,evidence_ids:[],measured_at:null}}})),
};

let externalFetchCount=0;
const noFetch=async()=>{externalFetchCount+=1;throw new Error('planner must not fetch');};
const rows=new Map();const TRADING_STATE={get:async key=>rows.get(key)||null,put:async(key,value)=>rows.set(key,value)};
const {writeProbeHealth}=await import('./model-mesh/health-store.js');
for(const model of modelSnapshot.models)await writeProbeHealth(TRADING_STATE,model,{ok:true,latencyMs:10},{sourceSha:modelSnapshot.source_sha,delay:async()=>{}});
const env={GROQ_API_KEY:'unused',OPENROUTER_API_KEY:'unused',TRADING_STATE};

const fast=await buildModelMeshPlan({text:'hello',dataClass:'PUBLIC',hasImage:false,profile:'FAST',route:{profile:'FAST',primarySkill:'core_reasoning',externalRoutingCalls:0}}, {skillSnapshot,modelSnapshot,activeIndex,fetchImpl:noFetch});
assert.equal(fast.route.externalRoutingCalls,0);
assert.equal(fast.workers.length,0);

const standard=await buildModelMeshPlan({text:'analyze this architecture',dataClass:'PUBLIC',hasImage:false,profile:'STANDARD',route:{profile:'STANDARD',primarySkill:'core_reasoning',externalRoutingCalls:0}}, {skillSnapshot,modelSnapshot,activeIndex,env,fetchImpl:noFetch});
assert.equal(standard.route.externalRoutingCalls,0);
assert.ok(standard.workers.length<=2);
assert.equal(externalFetchCount,0);
assert.equal(standard.routingAuthority,false);
assert.equal(standard.reasoningAuthority,false);

const frozenRoute=Object.freeze({profile:'STANDARD',primarySkill:'core_reasoning',externalRoutingCalls:0,sourceSha:'a'.repeat(40)});
const emptySnapshot={...modelSnapshot,models:[]};
const emptyIndex={...activeIndex,entries:[]};
const frozenPlan=await buildModelMeshPlan({text:'debug api',dataClass:'PUBLIC',hasImage:false,route:frozenRoute}, {skillSnapshot,modelSnapshot:emptySnapshot,activeIndex:emptyIndex,fetchImpl:noFetch});
assert.equal(frozenPlan.ok,true);
assert.equal(frozenPlan.route.externalRoutingCalls,0);
assert.equal(frozenPlan.route.sourceSha,'a'.repeat(40));
assert.equal(frozenPlan.workers.length,0);
assert.equal(externalFetchCount,0);

await assert.rejects(
  buildModelMeshPlan({text:'drift',route:frozenRoute},{skillSnapshot,modelSnapshot,activeIndex:{...activeIndex,source_sha:'b'.repeat(40)}}),
  /MODEL_MESH_SOURCE_SHA_MISMATCH/,
);

console.log('model mesh planner contracts ok');
