import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';
import {AI_HORDE_ADAPTER,listProviderAdapters} from './image-render/provider-adapter-registry.js';
import {validateProviderAdapter} from './image-render/provider-adapter.js';

const adapters=listProviderAdapters();
assert.ok(adapters.length>=1);
for(const adapter of adapters)assert.equal(validateProviderAdapter(adapter).ok,true,`${adapter.id}: ${validateProviderAdapter(adapter).errors}`);

assert.equal(AI_HORDE_ADAPTER.referenceSafe,false);
assert.deepEqual(AI_HORDE_ADAPTER.privacyClasses,['PUBLIC']);
assert.equal(AI_HORDE_ADAPTER.monetaryCost,'zero');
assert.equal(AI_HORDE_ADAPTER.paidFallback,false);
assert.equal(AI_HORDE_ADAPTER.autoPurchase,false);

const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'secret'};
const auth={'x-image-render-token':'secret'};
const response=await handleImageRenderV3(new Request('https://x/brain/image/v3/activation',{headers:auth}),env);
assert.equal(response.status,200);
const payload=await response.json();

assert.equal(payload.mode,'FREE_ONLY');
assert.equal(payload.paidFallback,false);
assert.equal(payload.autoPurchase,false);
assert.ok(Array.isArray(payload.providers)&&payload.providers.length>=1);
assert.ok(Array.isArray(payload.models)&&payload.models.length>=4);

for(const model of payload.models){
  assert.ok(Array.isArray(model.tasks)&&model.tasks.length>=1,model.modelId);
  for(const task of model.tasks){
    assert.ok(['CANDIDATE','RUNTIME_DISCOVERED','HEALTH_VERIFIED','LICENSE_VERIFIED','PRIVACY_VERIFIED','BENCHMARKED','ACTIVE','DEGRADED','DISABLED'].includes(task.status));
    if(task.status==='ACTIVE')assert.ok(model.runtimeProviders.length>0,model.modelId);
    else assert.ok(task.blockers.length>0,`${model.modelId}/${task.taskType} must say why it is not active`);
  }
}

assert.equal(payload.summary.ACTIVE,0);
assert.ok(payload.models.filter(m=>m.runtimeProviders.length===0).every(m=>m.tasks.every(t=>t.blockers.includes('runtime_not_discovered'))));
assert.ok(payload.nextBottleneck);

assert.ok(Array.isArray(payload.benchmarkSuites));
assert.ok(payload.benchmarkSuites.some(s=>s.taskType==='REFERENCE_GENERATION'&&s.dimensions.includes('identitySimilarity')));

console.log('image render v3 activation report contracts: PASS');

// ?probe=1 must exercise each Workers AI task family independently. The critic mock must
// return parseable critic JSON; a generic image response is not visual-critic evidence.
const criticJson=JSON.stringify({overallScore:96,confidence:1,dimensions:{promptAdherence:96,objectCount:96,composition:96,anatomy:96,styleAccuracy:96,textAccuracy:96},problems:[]});
const probeEnv={
  ...env,
  AI:{async run(model){
    if(String(model).includes('llama-3.2-11b-vision-instruct'))return {response:criticJson};
    return {image:'ZmFrZQ=='};
  }},
};
const probed=await (await handleImageRenderV3(
  new Request('https://x/brain/image/v3/activation?probe=1',{headers:auth}),
  probeEnv,
)).json();
assert.ok(probed.probe,'probe evidence must be reported');
const cfModels=probed.models.filter(m=>m.runtimeProviders.includes('cloudflare_workers_ai'));
assert.ok(cfModels.length>=4);
for(const model of cfModels){
  for(const task of model.tasks){
    assert.ok(!task.blockers.includes('runtime_not_discovered'),`${model.modelId}/${task.taskType} should be discovered`);
    assert.ok(!task.blockers.includes('runtime_health_not_verified'),`${model.modelId}/${task.taskType} should have its own health evidence`);
    assert.notEqual(task.status,'ACTIVE','no empirical benchmark evidence has been recorded');
    assert.ok(task.blockers.includes('benchmark_not_passed'),`${model.modelId}/${task.taskType} should stop at benchmark evidence`);
    assert.ok(task.evidenceTrail.some(e=>e.stage==='HEALTH_VERIFIED'));
    assert.ok(task.evidenceTrail.some(e=>e.stage==='LICENSE_VERIFIED'));
    assert.ok(task.evidenceTrail.some(e=>e.stage==='PRIVACY_VERIFIED'));
  }
}

// A partial runtime proves that baseline provider health cannot be reused for every task.
const partial=await (await handleImageRenderV3(
  new Request('https://x/brain/image/v3/activation?probe=1',{headers:auth}),
  {...env,AI:{async run(model){if(String(model).includes('flux-1-schnell'))return {image:'ZmFrZQ=='};throw new Error('task unavailable');}}},
)).json();
const flux=partial.models.find(m=>m.modelId==='flux-1-schnell');
assert.ok(flux.tasks.every(t=>!t.blockers.includes('runtime_health_not_verified')),'FLUX T2I family should be healthy');
const ref=partial.models.find(m=>m.modelId==='stable-diffusion-v1-5-img2img');
assert.ok(ref.tasks.every(t=>t.blockers.includes('runtime_health_not_verified')),'img2img must not inherit FLUX health');
const inpaint=partial.models.find(m=>m.modelId==='stable-diffusion-v1-5-inpainting');
assert.ok(inpaint.tasks.every(t=>t.blockers.includes('runtime_health_not_verified')),'inpainting must not inherit FLUX health');
const critic=partial.models.find(m=>m.modelId==='llama-3.2-11b-vision-instruct');
assert.ok(critic.tasks.every(t=>t.blockers.includes('runtime_health_not_verified')),'critic must not inherit FLUX health');

const unprobed=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/activation?probe=1',{headers:auth}),env)).json();
for(const model of unprobed.models.filter(m=>m.runtimeProviders.includes('cloudflare_workers_ai'))){
  assert.ok(model.tasks[0].blockers.includes('runtime_not_discovered'),model.modelId);
}

console.log('image render v3 activation probe contracts: PASS');
