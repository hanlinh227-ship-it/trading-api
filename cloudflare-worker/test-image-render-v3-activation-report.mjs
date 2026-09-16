import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';
import {AI_HORDE_ADAPTER,listProviderAdapters} from './image-render/provider-adapter-registry.js';
import {validateProviderAdapter} from './image-render/provider-adapter.js';

// The shipped adapters must satisfy the section 15 contract.
const adapters=listProviderAdapters();
assert.ok(adapters.length>=1);
for(const adapter of adapters)assert.equal(validateProviderAdapter(adapter).ok,true,`${adapter.id}: ${validateProviderAdapter(adapter).errors}`);

// AI Horde stays PUBLIC-only and reference-unsafe.
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

// The activation report says, per model and task, exactly which gate is blocking.
assert.equal(payload.mode,'FREE_ONLY');
assert.equal(payload.paidFallback,false);
assert.equal(payload.autoPurchase,false);
assert.ok(Array.isArray(payload.providers)&&payload.providers.length>=1);
assert.ok(Array.isArray(payload.models)&&payload.models.length>=4);

for(const model of payload.models){
  assert.ok(Array.isArray(model.tasks)&&model.tasks.length>=1,model.modelId);
  for(const task of model.tasks){
    assert.ok(['CANDIDATE','RUNTIME_DISCOVERED','HEALTH_VERIFIED','LICENSE_VERIFIED','PRIVACY_VERIFIED','BENCHMARKED','ACTIVE','DEGRADED','DISABLED'].includes(task.status));
    // Nothing may claim ACTIVE without a runtime provider behind it.
    if(task.status==='ACTIVE')assert.ok(model.runtimeProviders.length>0,model.modelId);
    else assert.ok(task.blockers.length>0,`${model.modelId}/${task.taskType} must say why it is not active`);
  }
}

// Today no free runtime serves these models, so every one is blocked at discovery.
assert.equal(payload.summary.ACTIVE,0);
assert.ok(payload.summary.CANDIDATE>=4);
assert.ok(payload.models.every(m=>m.tasks.every(t=>t.blockers.includes('runtime_not_discovered'))));
assert.equal(payload.nextBottleneck,'runtime_not_discovered');

// Benchmark suites are published so the gap to frontier quality is measurable, not asserted.
assert.ok(Array.isArray(payload.benchmarkSuites));
assert.ok(payload.benchmarkSuites.some(s=>s.taskType==='REFERENCE_GENERATION'&&s.dimensions.includes('identitySimilarity')));

console.log('image render v3 activation report contracts: PASS');

// ?probe=1 folds live runtime evidence into the report, so a model backed by a runtime
// that actually answered advances past runtime_not_discovered.
const probed=await (await handleImageRenderV3(
  new Request('https://x/brain/image/v3/activation?probe=1',{headers:auth}),
  {...env,AI:{run:async()=>({image:'ZmFrZQ=='})}},
)).json();
assert.ok(probed.probe,'probe evidence must be reported');
const cfModels=probed.models.filter(m=>m.runtimeProviders.includes('cloudflare_workers_ai'));
assert.ok(cfModels.length>=4);
for(const model of cfModels){
  const task=model.tasks[0];
  assert.ok(!task.blockers.includes('runtime_not_discovered'),`${model.modelId} should be discovered`);
  assert.ok(!task.blockers.includes('runtime_health_not_verified'),`${model.modelId} should be health verified`);
  // Licence, privacy and benchmark evidence still gate ACTIVE.
  assert.notEqual(task.status,'ACTIVE');
  assert.ok(task.blockers.length>0);
  assert.ok(task.evidenceTrail.some(e=>e.stage==='HEALTH_VERIFIED'));
}
// A provider that never answered must not have its models advanced.
const unprobed=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/activation?probe=1',{headers:auth}),env)).json();
for(const model of unprobed.models.filter(m=>m.runtimeProviders.includes('cloudflare_workers_ai'))){
  assert.ok(model.tasks[0].blockers.includes('runtime_not_discovered'),model.modelId);
}

console.log('image render v3 activation probe contracts: PASS');
