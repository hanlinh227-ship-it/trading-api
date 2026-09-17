import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';

const base={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'s'};
const auth={'x-image-render-token':'s'};
const caps=async(env,query='')=>(await (await handleImageRenderV3(new Request(`https://x/brain/image/v3/capabilities${query}`,{headers:auth}),env)).json());

let payload=await caps({...base,AI:{run:async()=>({image:'x'})}});
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'UNVERIFIED');
assert.equal(payload.taskAvailability.INPAINT,'UNVERIFIED');
assert.equal(payload.referenceSafeRuntime,'UNVERIFIED');
assert.equal(payload.visualCriticRuntime,'UNVERIFIED');
assert.equal(payload.inferenceRuntime,'UNVERIFIED');

payload=await caps(base);
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.visualCriticRuntime,'UNAVAILABLE');

// probe=1 upgrades only task paths that actually answered. The critic must return its own
// parseable JSON response; an image response from another model is not critic evidence.
const criticJson=JSON.stringify({overallScore:96,confidence:1,dimensions:{promptAdherence:96,objectCount:96,composition:96,anatomy:96,styleAccuracy:96,textAccuracy:96},problems:[]});
const healthy={...base,AI:{async run(model){
  if(String(model).includes('llama-3.2-11b-vision-instruct'))return {response:criticJson};
  return {image:'x'};
}}};
payload=await caps(healthy,'?probe=1');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'AVAILABLE');
assert.equal(payload.taskAvailability.INPAINT,'AVAILABLE');
assert.equal(payload.referenceSafeRuntime,'AVAILABLE');
assert.equal(payload.visualCriticRuntime,'AVAILABLE');
assert.equal(payload.inferenceRuntime,'AVAILABLE');

// Prove that provider-level T2I health cannot leak into reference/edit/critic availability.
const t2iOnly={...base,AI:{async run(model){
  if(String(model).includes('flux-1-schnell'))return {image:'x'};
  throw new Error('task-specific runtime rejected');
}}};
payload=await caps(t2iOnly,'?probe=1');
assert.equal(payload.inferenceRuntime,'AVAILABLE');
assert.notEqual(payload.taskAvailability.REFERENCE_GENERATION,'AVAILABLE');
assert.notEqual(payload.taskAvailability.INPAINT,'AVAILABLE');
assert.notEqual(payload.referenceSafeRuntime,'AVAILABLE');
assert.notEqual(payload.visualCriticRuntime,'AVAILABLE');

payload=await caps({...base,AI:{run:async()=>{throw new Error('rejected');}}},'?probe=1');
assert.equal(payload.referenceSafeRuntime,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(payload.visualCriticRuntime,'UNAVAILABLE');
assert.equal(payload.inferenceRuntime,'UNAVAILABLE');

payload=await caps({...base,AI:{run:async()=>{const e=new Error('neurons');e.status=429;throw e;}}},'?probe=1');
assert.equal(payload.taskAvailability.REFERENCE_GENERATION,'WAITING_FOR_FREE_COMPUTE');
assert.equal(payload.paidFallback,false);

payload=await caps(base);
assert.equal(payload.taskAvailability.TEXT_TO_IMAGE,'AVAILABLE');

console.log('image render v3 unverified capability contracts: PASS');
