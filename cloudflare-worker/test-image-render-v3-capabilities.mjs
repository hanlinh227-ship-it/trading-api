import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';

const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'secret'};
const auth={'x-image-render-token':'secret'};
const get=path=>handleImageRenderV3(new Request(`https://x${path}`,{headers:auth}),env);

const payload=await (await get('/brain/image/v3/capabilities')).json();

assert.ok(Array.isArray(payload.tasks)&&payload.tasks.length>=15);
assert.equal(typeof payload.taskAvailability,'object');
for(const task of payload.tasks){
  assert.ok(['AVAILABLE','UNVERIFIED','UNAVAILABLE','WAITING_FOR_SAFE_FREE_RUNTIME','WAITING_FOR_FREE_COMPUTE'].includes(payload.taskAvailability[task]),`${task}: ${payload.taskAvailability[task]}`);
}

assert.equal(payload.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');
assert.equal(payload.taskAvailability.MULTI_SCENE_BATCH,'AVAILABLE');
for(const task of ['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','TARGETED_REPAIR']){
  assert.equal(payload.taskAvailability[task],'WAITING_FOR_SAFE_FREE_RUNTIME',task);
}

assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.visualCriticRuntime,'UNAVAILABLE');
assert.equal(payload.quality.strictVisualRequiresRealCritic,true);
assert.equal(payload.quality.missingVisualCriticAction,'complete_unverified');

assert.equal(payload.modelVault.ACTIVE,0);
assert.equal(payload.modelVault.BENCHMARKED,0);
assert.ok(payload.modelVault.CANDIDATE>=4);

assert.equal(payload.mode,'FREE_ONLY');
assert.equal(payload.paidFallback,false);
assert.equal(payload.autoPurchase,false);
assert.equal(payload.privacy.aiHordePublicOnly,true);

console.log('image render v3 capability availability contracts: PASS');

// Binding presence alone is UNVERIFIED. With probe=1, every AVAILABLE capability needs
// evidence from its own task path, including a parseable visual critic response.
const criticJson=JSON.stringify({overallScore:96,confidence:1,dimensions:{promptAdherence:96,objectCount:96,composition:96,anatomy:96,styleAccuracy:96,textAccuracy:96},problems:[]});
const withAi={...env,AI:{async run(model){
  if(String(model).includes('llama-3.2-11b-vision-instruct'))return {response:criticJson};
  return {image:'x'};
}}};
const unprobed=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities',{headers:auth}),withAi)).json();
assert.equal(unprobed.visualCriticRuntime,'UNVERIFIED');
assert.equal(unprobed.runtimeVerifiedThisRequest,false);

const live=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities?probe=1',{headers:auth}),withAi)).json();
assert.equal(live.runtimeVerifiedThisRequest,true);
assert.equal(live.visualCriticRuntime,'AVAILABLE');
assert.equal(live.visualCriticProvider,'cloudflare_workers_ai');
assert.match(live.visualCriticModel,/^@cf\//);
assert.equal(live.inferenceRuntime,'AVAILABLE');
assert.equal(live.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');
assert.equal(live.taskAvailability.REFERENCE_GENERATION,'AVAILABLE');
assert.equal(live.taskAvailability.INPAINT,'AVAILABLE');
assert.equal(live.referenceSafeRuntime,'AVAILABLE');
assert.equal(live.quality.strictVisualRequiresRealCritic,true);
assert.equal(live.quality.missingVisualCriticAction,'complete_unverified');

// A partial probe cannot inherit T2I health for reference/edit/critic paths.
const partialEnv={...env,AI:{async run(model){
  if(String(model).includes('flux-1-schnell'))return {image:'x'};
  throw new Error('task unavailable');
}}};
const partial=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities?probe=1',{headers:auth}),partialEnv)).json();
assert.equal(partial.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');
assert.notEqual(partial.taskAvailability.REFERENCE_GENERATION,'AVAILABLE');
assert.notEqual(partial.taskAvailability.INPAINT,'AVAILABLE');
assert.notEqual(partial.visualCriticRuntime,'AVAILABLE');

console.log('image render v3 capability runtime state contracts: PASS');
