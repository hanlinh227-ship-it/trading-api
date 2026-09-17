import assert from 'node:assert/strict';
import {createWorkersAiClient} from './image-render/workers-ai.js';

const calls=[];
const env={AI:{async run(model,input){calls.push({model,input});return {image:'ZmFrZQ=='};}}};
const client=createWorkersAiClient();

// flux-1-schnell accepts only prompt and steps. Sending width/height makes the provider
// reject the request, which is what made the first production probe fail.
calls.length=0;
let result=await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'a blue square',width:512,height:512,steps:4});
assert.equal(result.ok,true);
assert.equal(calls[0].model,'@cf/black-forest-labs/flux-1-schnell');
assert.equal(calls[0].input.prompt,'a blue square');
assert.equal(calls[0].input.width,undefined,'flux-1-schnell does not accept width');
assert.equal(calls[0].input.height,undefined,'flux-1-schnell does not accept height');
assert.equal(calls[0].input.steps,4);

// steps is clamped to the documented maximum of 8 rather than passed through blindly.
calls.length=0;
await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'x',steps:40});
assert.equal(calls[0].input.steps,8);
calls.length=0;
await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'x'});
assert.ok(calls[0].input.steps>=1&&calls[0].input.steps<=8,'a default within range is sent');

// The stable-diffusion models do accept the image shaping parameters.
calls.length=0;
await client.generate(env,{taskType:'IMAGE_EDIT_GLOBAL',prompt:'make it night',image:[1,2],width:512,height:512,strength:0.6});
assert.equal(calls[0].model,'@cf/runwayml/stable-diffusion-v1-5-img2img');
assert.equal(calls[0].input.width,512);
assert.equal(calls[0].input.height,512);
assert.equal(calls[0].input.strength,0.6);
assert.deepEqual(calls[0].input.image,[1,2]);

calls.length=0;
await client.generate(env,{taskType:'INPAINT',prompt:'fix',image:[1],mask:[2],width:512,height:512});
assert.equal(calls[0].model,'@cf/runwayml/stable-diffusion-v1-5-inpainting');
assert.deepEqual(calls[0].input.mask,[2]);
assert.equal(calls[0].input.width,512);

// flux-1-schnell returns {image:<base64>}; the client surfaces that without reshaping it
// into something the caller would have to guess at.
calls.length=0;
result=await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'x'});
assert.equal(result.output.image,'ZmFrZQ==');

console.log('image render v3 model input schema contracts: PASS');
