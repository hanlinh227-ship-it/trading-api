import assert from 'node:assert/strict';
import {validateImageBatchRequest,createRenderManifest} from './image-render/render-manifest.js';
import {compileScenePrompt} from './image-render/prompt-compiler.js';

const scenes=Array.from({length:20},(_,i)=>({sceneId:String(i+1),prompt:`Scene ${i+1}: Max walks through the park`}));

assert.equal(validateImageBatchRequest({scenes}).error,'data_class_required');
assert.equal(validateImageBatchRequest({dataClass:'INTERNAL',scenes}).error,'ai_horde_public_data_only');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',referenceImages:['x'],scenes}).error,'reference_images_not_enabled_for_volunteer_provider');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',scenes:Array.from({length:101},()=>({prompt:'x'}))}).error,'batch_scene_limit_exceeded');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',scenes:[{prompt:''}]}).error,'invalid_scene_prompt');

const valid=validateImageBatchRequest({
  dataClass:'PUBLIC',
  qualityMode:'STRICT',
  consistencyMode:'STRICT',
  scenes,
  globalConstraints:['16:9','one character only'],
  sharedCharacterState:{Max:['child monkey','blue shirt','same wardrobe in every scene']},
  sharedStyleState:['polished 3D children animation'],
});
assert.equal(valid.ok,true);
assert.equal(valid.request.scenes.length,20);
assert.equal(valid.request.schedulerConfig.concurrency,4);
assert.equal(valid.request.retryPolicy.maxAttempts,3);

const manifest=createRenderManifest(valid.request,{batchId:'batch-test-001',createdAt:'2026-09-16T00:00:00.000Z'});
assert.equal(manifest.batch_id,'batch-test-001');
assert.equal(manifest.scenes[0].original_prompt,scenes[0].prompt);
assert.equal(manifest.scenes[0].status,'queued');
assert.deepEqual(manifest.scenes[0].attempts,[]);

const compiled=compileScenePrompt(manifest.scenes[0],manifest);
assert.match(compiled.prompt,/Scene 1: Max walks through the park/);
assert.match(compiled.prompt,/child monkey/);
assert.match(compiled.prompt,/blue shirt/);
assert.match(compiled.prompt,/16:9/);
assert.match(compiled.prompt,/polished 3D children animation/);
assert.equal(compiled.locks.consistencyMode,'STRICT');
assert.equal(compiled.negativePrompt.includes('duplicate character'),true);

console.log('IMAGE_RENDER_V2_CONTRACTS_TEST=PASS');
