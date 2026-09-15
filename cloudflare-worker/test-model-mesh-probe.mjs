import assert from 'node:assert/strict';
import {createProviderProbe} from './model-mesh/provider-client.js';

const modelSnapshot={source_sha:'a'.repeat(40),models:[{provider_id:'groq',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss-120b',free_status:'account_specific',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',context_window:131072,health:'degraded',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{}}]};
const rows=new Map();const TRADING_STATE={get:async key=>rows.get(key)||null,put:async(key,value)=>rows.set(key,value)};
const fetchImpl=async(_url,options)=>{
  const auth=String(options?.headers?.Authorization||'');
  assert.equal(auth,'Bearer probe-secret');
  return new Response(JSON.stringify({choices:[{message:{content:'OK'}}]}),{status:200,headers:{'content-type':'application/json'}});
};
const probe=createProviderProbe({fetchImpl});
const body=await probe({GROQ_API_KEY:'probe-secret',TRADING_STATE},{modelSnapshot});
assert.equal(body.ok,true);
assert.equal(body.mode,'FREE_ONLY');
assert.equal(body.results.length,1);
const result=body.results[0];
assert.equal(result.providerId,'groq');
assert.equal(result.modelId,'openai/gpt-oss-120b');
assert.equal(result.configured,true);
assert.equal(result.ok,true);
assert.equal(result.status,200);
assert.equal(result.state,'LIVE_HEALTHY');
assert.equal(result.evidencePersisted,true);
assert.equal(typeof result.latencyMs,'number');
const serialized=JSON.stringify(body);
assert.equal(serialized.includes('probe-secret'),false);
assert.equal(serialized.includes('GROQ_API_KEY'),false);
assert.equal(serialized.includes('OK'),false);
console.log('model mesh provider probe contract ok');
