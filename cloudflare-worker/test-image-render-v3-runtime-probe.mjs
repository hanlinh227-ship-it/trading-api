import assert from 'node:assert/strict';
import {probeImageRuntimes} from './image-render/runtime-probe.js';

let result=await probeImageRuntimes({});
assert.equal(result.ok,true);
const cf=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(cf.health.ok,false);
assert.equal(cf.health.detail,'workers_ai_binding_unavailable');
assert.equal(cf.runtimeDiscovered.ok,false);
assert.deepEqual(cf.taskHealth,{});

const criticJson=JSON.stringify({overallScore:100,confidence:1,dimensions:{promptAdherence:100,objectCount:100,composition:100,anatomy:100,styleAccuracy:100,textAccuracy:100},problems:[]});
const calls=[];
const env={AI:{async run(model,input){
  calls.push({model,input});
  if(String(model).includes('flux-1-schnell'))return {image:'ZmFrZQ=='};
  if(String(model).includes('stable-diffusion-v1-5-img2img'))return new ReadableStream({start(c){c.close();}});
  if(String(model).includes('stable-diffusion-v1-5-inpainting'))return new ReadableStream({start(c){c.close();}});
  if(String(model).includes('llama-3.2-11b-vision-instruct'))return {response:criticJson};
  throw new Error(`unexpected model ${model}`);
}}};
result=await probeImageRuntimes(env);
const ok=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(ok.runtimeDiscovered.ok,true);
assert.equal(ok.health.ok,true);
assert.ok(ok.health.at);
assert.ok(ok.health.detail.includes('@cf/'));
for(const task of ['TEXT_TO_IMAGE','REFERENCE_GENERATION','INPAINT','VISUAL_CRITIC']){
  assert.equal(ok.taskHealth[task]?.ok,true,`${task} must have independent passing evidence`);
  assert.ok(ok.taskHealth[task]?.model);
}
assert.ok(calls.length>=4,'probe must exercise each materially different runtime path');
const fluxCall=calls.find(c=>String(c.model).includes('flux-1-schnell'));
assert.equal(fluxCall.input.steps,1,'T2I probe must use the fewest diffusion steps');
assert.equal(fluxCall.input.width,undefined,'FLUX probe must not send rejected width');
assert.ok(calls.some(c=>String(c.model).includes('stable-diffusion-v1-5-img2img')));
assert.ok(calls.some(c=>String(c.model).includes('stable-diffusion-v1-5-inpainting')));
assert.ok(calls.some(c=>String(c.model).includes('llama-3.2-11b-vision-instruct')));

// A provider can have a healthy baseline T2I path while other capabilities fail; the task
// evidence must preserve that distinction rather than upgrading every task together.
const partial={AI:{async run(model){
  if(String(model).includes('flux-1-schnell'))return {image:'ZmFrZQ=='};
  throw new Error('task unavailable');
}}};
result=await probeImageRuntimes(partial);
const partialCf=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(partialCf.health.ok,true);
assert.equal(partialCf.taskHealth.TEXT_TO_IMAGE.ok,true);
assert.equal(partialCf.taskHealth.REFERENCE_GENERATION.ok,false);
assert.equal(partialCf.taskHealth.INPAINT.ok,false);
assert.equal(partialCf.taskHealth.VISUAL_CRITIC.ok,false);

// Provider failures must preserve enough sanitized evidence to debug the exact hosted-model
// contract in production, while never leaking bearer/API credentials into activation logs.
const diagnostic={AI:{async run(model){
  if(String(model).includes('flux-1-schnell'))return {image:'ZmFrZQ=='};
  const e=new Error('input validation failed: num_steps rejected; Authorization: Bearer super-secret-token');
  e.status=400;
  e.code=10049;
  throw e;
}}};
result=await probeImageRuntimes(diagnostic);
const diagnosticCf=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
const refFailure=diagnosticCf.taskHealth.REFERENCE_GENERATION;
assert.equal(refFailure.ok,false);
assert.equal(refFailure.detail,'provider_request_failed');
assert.equal(refFailure.diagnostic?.status,400);
assert.equal(refFailure.diagnostic?.code,'10049');
assert.match(refFailure.diagnostic?.message||'',/input validation failed/i);
assert.doesNotMatch(refFailure.diagnostic?.message||'',/super-secret-token/i);
assert.match(refFailure.diagnostic?.message||'',/\[REDACTED\]/);

const broken={AI:{async run(){throw new Error('nope');}}};
result=await probeImageRuntimes(broken);
const bad=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(bad.runtimeDiscovered.ok,true,'the binding exists, so the runtime is discovered');
assert.equal(bad.health.ok,false,'baseline T2I did not answer, so provider health is not verified');

const exhausted={AI:{async run(){const e=new Error('neurons');e.status=429;throw e;}}};
result=await probeImageRuntimes(exhausted);
const spent=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(spent.health.ok,false);
assert.equal(spent.health.waitState,'WAITING_FOR_FREE_COMPUTE');
assert.equal(spent.health.paidFallback,false);
assert.equal(spent.taskHealth.TEXT_TO_IMAGE.waitState,'WAITING_FOR_FREE_COMPUTE');

assert.ok(result.providers.some(p=>p.providerId==='ai_horde'));
assert.equal(result.mode,'FREE_ONLY');
assert.equal(result.paidFallback,false);

console.log('image render v3 runtime probe contracts: PASS');
