// Model-level probe-and-select.
//
// A provider is a catalog, not a single model. Before this, the probe took the
// first admitted model per provider and let its verdict stand for the whole
// provider, which is how NVIDIA was written off for a retired model id and
// SambaNova for one 402 on a model its free tier does not include. These tests
// pin the rule: a model-scoped failure costs the model and moves to the next
// candidate; only every candidate failing costs the provider.
import assert from 'node:assert/strict';
import {createProviderProbe} from './model-mesh/provider-client.js';

const zeroCost={price_model:'account_free',input_price_per_million:0,output_price_per_million:0,quota_model:'unknown',hard_stop_verified:false,quota_headroom_ratio:null,price_verified_at:'2026-09-15T00:00:00Z',evidence:['docs']};
const model=(provider,id)=>({provider_id:provider,model_id:id,model_family:id,free_status:'account_specific',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',context_window:131072,health:'degraded',privacy_class:'public_safe',capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{},zero_cost:zeroCost});
const store=()=>{const rows=new Map();return {get:async key=>rows.get(key)||null,put:async(key,value)=>{rows.set(key,value);}};};
const ok=()=>new Response(JSON.stringify({choices:[{message:{content:'OK'}}]}),{status:200,headers:{'content-type':'application/json'}});
const fail=status=>new Response(JSON.stringify({error:{message:'nope'}}),{status,headers:{'content-type':'application/json'}});

// --- NVIDIA: listed is not live -------------------------------------------
// Two listed model ids answer 410 and 404 on chat completions; the third works.
// The provider must end LIVE_HEALTHY on the model that actually completed.
{
  const calls=[];
  const fetchImpl=async(url,options)=>{
    const body=JSON.parse(String(options?.body||'{}'));calls.push(body.model);
    if(body.model==='retired-model')return fail(410);
    if(body.model==='never-existed')return fail(404);
    return ok();
  };
  const probe=createProviderProbe({fetchImpl});
  const snapshot={source_sha:'a'.repeat(40),models:[model('nvidia_nim','retired-model'),model('nvidia_nim','never-existed'),model('nvidia_nim','live-model')]};
  const body=await probe({NVIDIA_API_KEY:'k',TRADING_STATE:store()},{modelSnapshot:snapshot});
  assert.equal(body.results.length,1,'one row per provider, not per model');
  const row=body.results[0];
  assert.equal(row.providerId,'nvidia_nim');
  assert.equal(row.modelId,'live-model','the persisted selection is the model that completed');
  assert.equal(row.ok,true);
  assert.equal(row.state,'LIVE_HEALTHY');
  assert.equal(row.candidatesProbed,3);
  assert.deepEqual(row.attemptedModelIds,['retired-model','never-existed','live-model']);
  assert.equal(row.providerExhausted,false);
  assert.equal(body.successfulProviderCount,1);
  assert.deepEqual(calls,['retired-model','never-existed','live-model']);
}

// --- SambaNova: one 402 is not a provider verdict --------------------------
{
  const fetchImpl=async(_url,options)=>JSON.parse(String(options?.body||'{}')).model==='paid-only'?fail(402):ok();
  const probe=createProviderProbe({fetchImpl});
  const snapshot={source_sha:'a'.repeat(40),models:[model('sambanova','paid-only'),model('sambanova','free-tier')]};
  const body=await probe({SAMBANOVA_API_KEY:'k',TRADING_STATE:store()},{modelSnapshot:snapshot});
  const row=body.results[0];
  assert.equal(row.ok,true,'a free-tier model that works keeps the provider alive');
  assert.equal(row.modelId,'free-tier');
  assert.equal(body.successfulProviderCount,1);
}

// --- every candidate 402: now the provider is genuinely unavailable --------
{
  const probe=createProviderProbe({fetchImpl:async()=>fail(402)});
  const snapshot={source_sha:'a'.repeat(40),models:[model('sambanova','a'),model('sambanova','b')]};
  const body=await probe({SAMBANOVA_API_KEY:'k',TRADING_STATE:store()},{modelSnapshot:snapshot});
  const row=body.results[0];
  assert.equal(row.ok,false);
  assert.equal(row.category,'FREE_ENTITLEMENT_INVALID');
  // 402 means the next request would be billable, so the model leaves the pool
  // at once rather than after a second confirming failure.
  assert.equal(row.state,'QUARANTINED');
  assert.equal(row.providerExhausted,true,'exhaustion is recorded, not inferred');
  assert.equal(body.successfulProviderCount,0);
}

// --- a rate limit is not a model problem, so it stops the round ------------
// Trying the provider's next model would only burn the same shared quota.
{
  const calls=[];
  const fetchImpl=async(_url,options)=>{calls.push(JSON.parse(String(options?.body||'{}')).model);return fail(429);};
  const probe=createProviderProbe({fetchImpl});
  const snapshot={source_sha:'a'.repeat(40),models:[model('groq','first'),model('groq','second')]};
  const body=await probe({GROQ_API_KEY:'k',TRADING_STATE:store()},{modelSnapshot:snapshot});
  assert.deepEqual(calls,['first'],'a 429 ends the provider round immediately');
  assert.equal(body.results[0].state,'COOLDOWN');
  assert.equal(body.results[0].category,'RATE_LIMITED');
}

// --- a 5xx degrades the provider and never fails the mesh ------------------
{
  const probe=createProviderProbe({fetchImpl:async(_url,options)=>JSON.parse(String(options?.body||'{}')).model.startsWith('down')?fail(503):ok()});
  const snapshot={source_sha:'a'.repeat(40),models:[model('mistral','down-1'),model('groq','healthy')]};
  const body=await probe({MISTRAL_API_KEY:'k',GROQ_API_KEY:'k',TRADING_STATE:store()},{modelSnapshot:snapshot});
  assert.equal(body.ok,true,'one provider being down never fails the envelope');
  const mistral=body.results.find(row=>row.providerId==='mistral');
  assert.equal(mistral.category,'PROVIDER_5XX');
  assert.equal(mistral.state,'DEGRADED');
  assert.equal(body.successfulProviderCount,1,'the healthy provider still carries the round');
}

// --- the candidate list stays bounded --------------------------------------
{
  const calls=[];
  const probe=createProviderProbe({fetchImpl:async(_url,options)=>{calls.push(JSON.parse(String(options?.body||'{}')).model);return fail(404);},maxCandidatesPerProvider:2});
  const snapshot={source_sha:'a'.repeat(40),models:['m1','m2','m3','m4','m5'].map(id=>model('nvidia_nim',id))};
  await probe({NVIDIA_API_KEY:'k',TRADING_STATE:store()},{modelSnapshot:snapshot});
  assert.equal(calls.length,2,'replacement discovery is bounded, never a catalog sweep');
}

// --- nothing in the envelope leaks a credential ----------------------------
{
  const probe=createProviderProbe({fetchImpl:async()=>ok()});
  const snapshot={source_sha:'a'.repeat(40),models:[model('groq','free')]};
  const body=await probe({GROQ_API_KEY:'sk-should-never-appear',TRADING_STATE:store()},{modelSnapshot:snapshot});
  const serialized=JSON.stringify(body);
  assert.equal(serialized.includes('sk-should-never-appear'),false);
  assert.equal(serialized.includes('GROQ_API_KEY'),false);
}

console.log('model mesh bounded probe-and-select contracts ok');
