import assert from 'node:assert/strict';
import {CLOUDFLARE_WORKERS_AI_ADAPTER,POLLINATIONS_ADAPTER,listProviderAdapters} from './image-render/provider-adapter-registry.js';
import {validateProviderAdapter} from './image-render/provider-adapter.js';

// Every shipped adapter satisfies the contract.
for(const adapter of listProviderAdapters()){
  assert.equal(validateProviderAdapter(adapter).ok,true,`${adapter.id}: ${validateProviderAdapter(adapter).errors}`);
  assert.equal(adapter.costMode,'FREE_ONLY');
  assert.equal(adapter.monetaryCost,'zero');
  assert.equal(adapter.paidFallback,false);
  assert.equal(adapter.autoPurchase,false);
}
assert.ok(listProviderAdapters().length>=3);

// Cloudflare Workers AI: first-party to the Worker already handling this data, so it is
// the reference-safe runtime. Free allocation hard-stops, so it cannot bill.
const cf=CLOUDFLARE_WORKERS_AI_ADAPTER;
assert.equal(cf.id,'cloudflare_workers_ai');
assert.equal(cf.referenceSafe,true);
assert.deepEqual([...cf.privacyClasses].sort(),['CONFIDENTIAL','INTERNAL','PUBLIC']);
assert.equal(cf.rateLimitBehavior,'fail_closed');
// It must carry an explicit free-allocation budget that fails closed rather than billing.
assert.equal(cf.freeAllocation.hardStop,true);
assert.ok(cf.freeAllocation.dailyNeurons>0);
assert.equal(cf.freeAllocation.overageBillingEnabled,false);
// Only model IDs verified against Cloudflare's own model catalogue.
for(const id of cf.supportedModels)assert.match(id,/^@cf\//,id);
assert.ok(cf.supportedModels.includes('@cf/black-forest-labs/flux-1-schnell'));
assert.ok(cf.supportedModels.includes('@cf/runwayml/stable-diffusion-v1-5-img2img'));
assert.ok(cf.supportedModels.includes('@cf/runwayml/stable-diffusion-v1-5-inpainting'));
// It claims the reference and edit tasks its models actually support.
for(const task of ['TEXT_TO_IMAGE','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','REFERENCE_GENERATION'])assert.ok(cf.supportedTasks.includes(task),task);

// Pollinations: no account and no key, so it has no way to bill us, but it is a public
// third-party service and therefore PUBLIC-only and reference-unsafe.
const poll=POLLINATIONS_ADAPTER;
assert.equal(poll.id,'pollinations');
assert.equal(poll.referenceSafe,false);
assert.deepEqual(poll.privacyClasses,['PUBLIC']);
assert.deepEqual(poll.supportedTasks,['TEXT_TO_IMAGE','MULTI_SCENE_BATCH']);
assert.equal(poll.authentication,'none');
assert.equal(poll.freeAllocation.hardStop,true);
assert.equal(poll.freeAllocation.overageBillingEnabled,false);

// No adapter may be reference-safe while advertising a provider that could bill.
for(const adapter of listProviderAdapters()){
  assert.equal(adapter.freeAllocation.overageBillingEnabled,false,adapter.id);
  if(adapter.referenceSafe===false)assert.deepEqual(adapter.privacyClasses,['PUBLIC'],adapter.id);
}

console.log('image render v3 provider adapters contracts: PASS');
