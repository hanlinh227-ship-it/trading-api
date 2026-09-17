import assert from 'node:assert/strict';
import {createImageProviderMesh} from './image-render/provider-mesh.js';
import {handleImageRenderV3} from './image-render-v3-entry.js';

const refIntent={taskType:'REFERENCE_GENERATION',privacyClass:'CONFIDENTIAL',referenceAssets:[{id:'r'}],target:{width:512,height:512}};
const publicIntent={taskType:'TEXT_TO_IMAGE',privacyClass:'PUBLIC',referenceAssets:[],target:{width:512,height:512}};

// Without the AI binding the reference-safe runtime is simply not there. Registering an
// adapter is not the same as having a runtime, and the mesh must not pretend otherwise.
let mesh=createImageProviderMesh({env:{}});
assert.equal(mesh.eligible(refIntent).length,0,'no reference-safe provider without the AI binding');
assert.ok(mesh.listRegistrations().every(r=>r.providerId!=='cloudflare_workers_ai'));
assert.ok(mesh.eligible(publicIntent).length>=1,'the volunteer provider still serves public prompt-only work');

// With the binding present the reference-safe runtime becomes eligible for private work.
mesh=createImageProviderMesh({env:{AI:{run:async()=>({})}}});
const eligible=mesh.eligible(refIntent);
assert.ok(eligible.length>=1);
assert.ok(eligible.every(r=>r.referenceSafe===true),'only reference-safe providers may take a reference');
assert.ok(eligible.every(r=>r.providerId!=='ai_horde'),'the volunteer provider must never appear for reference work');
assert.equal(eligible[0].providerId,'cloudflare_workers_ai');

// The mesh is derived from the adapter registry: there is one provider authority.
for(const registration of mesh.listRegistrations()){
  assert.equal(registration.monetaryCost,'zero',registration.providerId);
  assert.equal(registration.paidFallback,false,registration.providerId);
  assert.equal(registration.autoPurchase,false,registration.providerId);
  if(registration.referenceSafe===false)assert.deepEqual(registration.supportedDataClasses,['PUBLIC'],registration.providerId);
}

// Capabilities follow the same truth: reference work waits until the binding exists.
const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'s'};
const auth={'x-image-render-token':'s'};
const get=async e=>(await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities',{headers:auth}),e)).json());

let payload=await get(env);
assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.taskAvailability.INPAINT,'WAITING_FOR_SAFE_FREE_RUNTIME');

// A bound runtime is registered, not verified: production showed the binding present while
// every generation failed. Unprobed it reports UNVERIFIED; only probe=1 upgrades it.
payload=await get({...env,AI:{run:async()=>({})}});
assert.equal(payload.referenceSafeRuntime,'UNVERIFIED');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'UNVERIFIED');
assert.equal(payload.taskAvailability.IMAGE_EDIT_LOCAL,'UNVERIFIED');
assert.equal(payload.taskAvailability.INPAINT,'UNVERIFIED');
// Public text-to-image is also served by providers that need no binding, so it stays live.
assert.equal(payload.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');

const verified=await (await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities?probe=1',{headers:auth}),{...env,AI:{run:async()=>({image:'x'})}})).json();
assert.equal(verified.referenceSafeRuntime,'AVAILABLE');
assert.equal(verified.taskAvailability.REFERENCE_GENERATION,'AVAILABLE');
// A task no registered provider serves still waits rather than being claimed.
assert.equal(payload.taskAvailability.MULTI_IMAGE_COMPOSE,'WAITING_FOR_SAFE_FREE_RUNTIME');

console.log('image render v3 mesh runtime binding contracts: PASS');
