import assert from 'node:assert/strict';
import {listAiHordeModels,submitAiHordeImage} from './image-render/ai-horde.js';
import {createImageProviderRegistry} from './image-render/provider-registry.js';

const requests=[];
const fetchImpl=async(url,init={})=>{
  requests.push({url:String(url),init});
  if(String(url).endsWith('/status/models?type=image')){
    return new Response(JSON.stringify([
      {name:'Model A',count:4,performance:25.5,eta:2,queued:1},
      {name:'Model B',count:0,performance:10,eta:40,queued:9},
    ]),{status:200,headers:{'content-type':'application/json'}});
  }
  if(String(url).endsWith('/status/heartbeat'))return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
  if(String(url).endsWith('/generate/async'))return new Response(JSON.stringify({id:'12345678-1234-1234-1234-123456789abc',kudos:1}),{status:202,headers:{'content-type':'application/json'}});
  return new Response(JSON.stringify({message:'not found'}),{status:404,headers:{'content-type':'application/json'}});
};

const listed=await listAiHordeModels({fetchImpl});
assert.equal(listed.ok,true);
assert.equal(listed.provider,'ai_horde');
assert.deepEqual(listed.models[0],{name:'Model A',workerCount:4,performance:25.5,eta:2,queued:1});
assert.deepEqual(listed.models[1],{name:'Model B',workerCount:0,performance:10,eta:40,queued:9});
assert.ok(requests.some(row=>row.url.endsWith('/status/models?type=image')));

const registry=createImageProviderRegistry({fetchImpl});
// The registry carries both free providers: the volunteer one and the reference-safe
// first-party runtime that reference, edit and inpaint work needs an execution path on.
assert.deepEqual(registry.list(),['cloudflare_workers_ai','ai_horde']);
assert.equal(registry.get('unknown',{}),null);
// Declaring the reference-safe runtime is not the same as having it. Without the binding
// the registry hands out nothing, so a route to it fails closed instead of falling
// through to a provider that must never see a reference image.
assert.equal(registry.get('cloudflare_workers_ai',{}),null);
const workersAi=registry.get('cloudflare_workers_ai',{AI:{run:async()=>({image:''})}});
assert.equal(workersAi.id,'cloudflare_workers_ai');
assert.equal(workersAi.referenceSafe,true);
assert.equal(workersAi.monetaryCost,'zero');
assert.equal(workersAi.paidFallback,false);
assert.equal(workersAi.autoPurchase,false);
const provider=registry.get('ai_horde',{});
assert.equal(provider.id,'ai_horde');
assert.equal(provider.mode,'FREE_ONLY');
assert.equal(provider.monetaryCost,'zero');
assert.equal(provider.paidFallback,false);
const registryModels=await provider.listModels();
assert.equal(registryModels.models.length,2);
assert.equal((await provider.health()).ok,true);

// When the router names a concrete model, the volunteer provider must not silently
// downgrade to an unselected model because that would invalidate routing/benchmark evidence.
requests.length=0;
let submitted=await submitAiHordeImage({prompt:'test',models:['Model A'],fetchImpl});
assert.equal(submitted.ok,true);
let generationRequest=requests.find(row=>row.url.endsWith('/generate/async'));
let payload=JSON.parse(generationRequest.init.body);
assert.deepEqual(payload.models,['Model A']);
assert.equal(payload.allow_downgrade,false);

// When no concrete model is selected, provider-managed fallback remains allowed so
// PUBLIC prompt-only work can still use available volunteer capacity.
requests.length=0;
submitted=await submitAiHordeImage({prompt:'test',models:[],fetchImpl});
assert.equal(submitted.ok,true);
generationRequest=requests.find(row=>row.url.endsWith('/generate/async'));
payload=JSON.parse(generationRequest.init.body);
assert.ok(!('models' in payload));
assert.equal(payload.allow_downgrade,true);

console.log('IMAGE_RENDER_V2_PROVIDER_TEST=PASS');
