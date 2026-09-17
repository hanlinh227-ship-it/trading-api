import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';

const base={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'s'};
const auth={'x-image-render-token':'s'};
const caps=async(env,query='')=>(await (await handleImageRenderV3(new Request(`https://x/brain/image/v3/capabilities${query}`,{headers:auth}),env)).json());

// A binding that exists is not a runtime that works. Production proved this: the binding
// was present while every generation failed, yet capabilities reported AVAILABLE.
// Unprobed, a registered-but-unverified runtime must report UNVERIFIED, never AVAILABLE.
let payload=await caps({...base,AI:{run:async()=>({image:'x'})}});
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'UNVERIFIED');
assert.equal(payload.taskAvailability.INPAINT,'UNVERIFIED');
assert.equal(payload.referenceSafeRuntime,'UNVERIFIED');
assert.equal(payload.visualCriticRuntime,'UNVERIFIED');
assert.equal(payload.inferenceRuntime,'UNVERIFIED');

// With no binding at all it is unambiguously unavailable and reference work waits.
payload=await caps(base);
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.visualCriticRuntime,'UNAVAILABLE');

// probe=1 verifies for real. A runtime that answers becomes AVAILABLE.
payload=await caps({...base,AI:{run:async()=>({image:'x'})}},'?probe=1');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'AVAILABLE');
assert.equal(payload.referenceSafeRuntime,'AVAILABLE');
assert.equal(payload.visualCriticRuntime,'AVAILABLE');
assert.equal(payload.inferenceRuntime,'AVAILABLE');

// A runtime that fails the probe must not be reported available, even though it is bound.
payload=await caps({...base,AI:{run:async()=>{throw new Error('rejected');}}},'?probe=1');
assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.visualCriticRuntime,'UNAVAILABLE');
assert.equal(payload.inferenceRuntime,'UNAVAILABLE');

// An exhausted free allocation is a wait, not a missing runtime, and never a paid route.
payload=await caps({...base,AI:{run:async()=>{const e=new Error('neurons');e.status=429;throw e;}}},'?probe=1');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_FREE_COMPUTE');
assert.equal(payload.paidFallback,false);

// The volunteer provider's public text-to-image never depends on the AI binding.
payload=await caps(base);
assert.equal(payload.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');

console.log('image render v3 unverified capability contracts: PASS');
