import assert from 'node:assert/strict';
import {probeImageRuntimes} from './image-render/runtime-probe.js';

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

const result=await probeImageRuntimes(env);
const cf=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.ok(cf,'Workers AI provider evidence required');
assert.equal(cf.runtimeDiscovered.ok,true);
assert.ok(cf.taskHealth&&typeof cf.taskHealth==='object','taskHealth evidence required');
for(const task of ['TEXT_TO_IMAGE','REFERENCE_GENERATION','INPAINT','VISUAL_CRITIC']){
  assert.equal(cf.taskHealth[task]?.ok,true,`${task} must be independently probed`);
  assert.ok(cf.taskHealth[task]?.model,`${task} must record the exact model probed`);
}
assert.ok(calls.some(c=>String(c.model).includes('flux-1-schnell')));
assert.ok(calls.some(c=>String(c.model).includes('stable-diffusion-v1-5-img2img')));
assert.ok(calls.some(c=>String(c.model).includes('stable-diffusion-v1-5-inpainting')));
assert.ok(calls.some(c=>String(c.model).includes('llama-3.2-11b-vision-instruct')));

const partial={AI:{async run(model){
  if(String(model).includes('flux-1-schnell'))return {image:'ZmFrZQ=='};
  throw new Error('task runtime unavailable');
}}};
const partialResult=await probeImageRuntimes(partial);
const partialCf=partialResult.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(partialCf.taskHealth.TEXT_TO_IMAGE.ok,true);
assert.equal(partialCf.taskHealth.REFERENCE_GENERATION.ok,false);
assert.equal(partialCf.taskHealth.INPAINT.ok,false);
assert.equal(partialCf.taskHealth.VISUAL_CRITIC.ok,false);
assert.equal(partialCf.health.ok,true,'provider health may pass while task health remains mixed');

console.log('image render v3 task-specific runtime probe: PASS');
