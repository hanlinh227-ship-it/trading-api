import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';

const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'secret'};
const auth={'x-image-render-token':'secret'};
const get=path=>handleImageRenderV3(new Request(`https://x${path}`,{headers:auth}),env);

const payload=await (await get('/brain/image/v3/capabilities')).json();

// A supported intent is not an executable capability. Every task must carry an honest
// availability, and nothing may be reported executable without an eligible free provider.
assert.ok(Array.isArray(payload.tasks)&&payload.tasks.length>=15);
assert.equal(typeof payload.taskAvailability,'object');
for(const task of payload.tasks){
  assert.ok(['AVAILABLE','WAITING_FOR_SAFE_FREE_RUNTIME','WAITING_FOR_FREE_COMPUTE'].includes(payload.taskAvailability[task]),`${task}: ${payload.taskAvailability[task]}`);
}

// AI Horde is the only currently registered provider: prompt-only public generation is
// executable, and everything needing a reference must wait for a reference-safe runtime.
assert.equal(payload.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');
assert.equal(payload.taskAvailability.MULTI_SCENE_BATCH,'AVAILABLE');
for(const task of ['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','TARGETED_REPAIR']){
  assert.equal(payload.taskAvailability[task],'WAITING_FOR_SAFE_FREE_RUNTIME',task);
}

// Runtime claims must match what is actually configured.
assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.visualCriticRuntime,'UNAVAILABLE');
assert.equal(payload.quality.strictVisualRequiresRealCritic,true);
assert.equal(payload.quality.missingVisualCriticAction,'complete_unverified');

// A candidate model is never counted as an active runtime capability.
assert.equal(payload.modelVault.ACTIVE,0);
assert.equal(payload.modelVault.BENCHMARKED,0);
assert.ok(payload.modelVault.CANDIDATE>=4);

// FREE_ONLY boundaries are reported, not assumed.
assert.equal(payload.mode,'FREE_ONLY');
assert.equal(payload.paidFallback,false);
assert.equal(payload.autoPurchase,false);
assert.equal(payload.privacy.aiHordePublicOnly,true);

console.log('image render v3 capability availability contracts: PASS');

// With the AI binding present the critic and inference runtimes report AVAILABLE, and the
// reference-safe runtime follows the registered providers rather than a hardcoded answer.
// Only a runtime that answered a probe may be reported AVAILABLE; a bound but unprobed
// runtime is UNVERIFIED, which is what production would have shown had this been right.
const withAi={...env,AI:{run:async()=>({image:'x'})}};
const unprobed=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities',{headers:auth}),withAi)).json();
assert.equal(unprobed.visualCriticRuntime,'UNVERIFIED');
assert.equal(unprobed.runtimeVerifiedThisRequest,false);

const live=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities?probe=1',{headers:auth}),withAi)).json();
assert.equal(live.runtimeVerifiedThisRequest,true);
assert.equal(live.visualCriticRuntime,'AVAILABLE');
assert.equal(live.visualCriticProvider,'cloudflare_workers_ai');
assert.match(live.visualCriticModel,/^@cf\//);
assert.equal(live.inferenceRuntime,'AVAILABLE');
// Even with a critic available, STRICT_VISUAL still requires a real critic pass.
assert.equal(live.quality.strictVisualRequiresRealCritic,true);
assert.equal(live.quality.missingVisualCriticAction,'complete_unverified');

console.log('image render v3 capability runtime state contracts: PASS');
