import assert from 'node:assert/strict';
import {validateImageBatchRequest,createRenderManifest} from './image-render/render-manifest.js';
import {compileScenePrompt} from './image-render/prompt-compiler.js';

const scenes=Array.from({length:20},(_,i)=>({sceneId:String(i+1),prompt:`Max scene ${i+1}`}));
assert.equal(validateImageBatchRequest({scenes}).error,'data_class_required');
assert.equal(validateImageBatchRequest({dataClass:'INTERNAL',scenes}).error,'ai_horde_public_data_only');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',referenceImages:['x'],scenes}).error,'reference_images_not_enabled_for_volunteer_provider');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',scenes:Array.from({length:101},()=>({prompt:'x'}))}).error,'batch_scene_limit_exceeded');
const valid=validateImageBatchRequest({
  dataClass:'PUBLIC',
  qualityMode:'STRICT',
  consistencyMode:'STRICT',
  scenes,
  globalConstraints:['16:9'],
  sharedCharacterState:{Max:['red-orange fur','blue shirt','yellow overalls']},
});
assert.equal(valid.ok,true);
assert.equal(valid.request.schedulerConfig.concurrency,4);
assert.equal(valid.request.retryPolicy.maxAttempts,3);
const manifest=createRenderManifest(valid.request,{batchId:'batch-test-001',createdAt:'2026-09-16T00:00:00.000Z'});
assert.equal(manifest.scenes.length,20);
assert.equal(manifest.scenes[0].status,'queued');
assert.deepEqual(manifest.scenes[0].attempts,[]);
const compiled=compileScenePrompt(manifest.scenes[0],manifest);
assert.match(compiled.prompt,/Max scene 1/);
assert.match(compiled.prompt,/red-orange fur/);
assert.match(compiled.prompt,/blue shirt/);
assert.equal(compiled.locks.consistencyMode,'STRICT');
console.log('IMAGE_RENDER_V2_CONTRACTS_TEST=PASS');
