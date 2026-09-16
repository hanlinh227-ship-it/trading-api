import assert from 'node:assert/strict';
import {
  WORKERS_AI_MODELS,
  createWorkersAiClient,
  selectWorkersAiModel,
  workersAiHealth,
} from './image-render/workers-ai.js';

// Task -> model mapping uses only verified catalogue IDs, and every reference/edit task
// routes to a model that actually accepts a source image.
assert.equal(selectWorkersAiModel('TEXT_TO_IMAGE'),'@cf/black-forest-labs/flux-1-schnell');
assert.equal(selectWorkersAiModel('MULTI_SCENE_BATCH'),'@cf/black-forest-labs/flux-1-schnell');
assert.equal(selectWorkersAiModel('IMAGE_EDIT_GLOBAL'),'@cf/runwayml/stable-diffusion-v1-5-img2img');
assert.equal(selectWorkersAiModel('STYLE_TRANSFER'),'@cf/runwayml/stable-diffusion-v1-5-img2img');
assert.equal(selectWorkersAiModel('INPAINT'),'@cf/runwayml/stable-diffusion-v1-5-inpainting');
assert.equal(selectWorkersAiModel('IMAGE_EDIT_LOCAL'),'@cf/runwayml/stable-diffusion-v1-5-inpainting');
assert.equal(selectWorkersAiModel('UNSUPPORTED_TASK'),null);
for(const id of Object.values(WORKERS_AI_MODELS))assert.match(id,/^@cf\//,id);

// With no AI binding the provider is unavailable — it never silently degrades to another one.
let health=await workersAiHealth({});
assert.equal(health.ok,false);
assert.equal(health.error,'workers_ai_binding_unavailable');

const calls=[];
const env={AI:{async run(model,input){calls.push({model,input});return {image:'ZmFrZQ=='};}}};

health=await workersAiHealth(env);
assert.equal(health.ok,true);
assert.equal(health.provider,'cloudflare_workers_ai');

const client=createWorkersAiClient();

// Text to image: prompt only, no reference, dimensions passed through.
let result=await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'a blue square',width:512,height:512});
assert.equal(result.ok,true);
assert.equal(result.provider,'cloudflare_workers_ai');
assert.equal(result.model,'@cf/black-forest-labs/flux-1-schnell');
assert.equal(calls[0].input.prompt,'a blue square');
assert.equal(calls[0].input.width,512);

// An edit task without a source image fails closed rather than rendering from the prompt.
result=await client.generate(env,{taskType:'IMAGE_EDIT_GLOBAL',prompt:'make it night'});
assert.equal(result.ok,false);
assert.equal(result.error,'source_image_required');

// An inpaint without a mask fails closed rather than redrawing the whole scene.
result=await client.generate(env,{taskType:'INPAINT',prompt:'fix the hand',image:[1,2,3]});
assert.equal(result.ok,false);
assert.equal(result.error,'mask_required');

result=await client.generate(env,{taskType:'INPAINT',prompt:'fix the hand',image:[1,2,3],mask:[4,5,6]});
assert.equal(result.ok,true);
assert.equal(result.model,'@cf/runwayml/stable-diffusion-v1-5-inpainting');
assert.deepEqual(calls.at(-1).input.mask,[4,5,6]);

// A provider error is surfaced, never swallowed into a fake success.
const failing={AI:{async run(){throw new Error('capacity');}}};
result=await client.generate(failing,{taskType:'TEXT_TO_IMAGE',prompt:'x'});
assert.equal(result.ok,false);
assert.equal(result.error,'provider_request_failed');

// Exhausting the free allocation must fail closed, never fall through to a paid route.
const exhausted={AI:{async run(){const e=new Error('out of neurons');e.status=429;throw e;}}};
result=await client.generate(exhausted,{taskType:'TEXT_TO_IMAGE',prompt:'x'});
assert.equal(result.ok,false);
assert.equal(result.error,'free_allocation_exhausted');
assert.equal(result.paidFallback,false);
assert.equal(result.waitState,'WAITING_FOR_FREE_COMPUTE');

console.log('image render v3 workers ai client contracts: PASS');
