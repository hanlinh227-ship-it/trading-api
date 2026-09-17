import assert from 'node:assert/strict';
import {createBatchState,markSceneProviderResult,markSceneSubmitted} from './image-render/batch-engine.js';
import {modelHistoryFromState} from './image-render/batch-engine.js';

const manifest={
  batch_id:'b1',data_class:'PUBLIC',quality_mode:'STRUCTURAL',
  scheduler_config:{concurrency:1},retry_policy:{maxAttempts:3},preferred_models:[],
  scenes:[{scene_id:'s1',status:'queued',attempts:[],compiled_prompt:'a cat',negative_prompt:'',dimensions:{width:512,height:512}}],
};

// The model we asked for and the model the provider actually used are separate facts.
let state=createBatchState(manifest);
state=markSceneSubmitted(state,{sceneId:'s1',provider:'ai_horde',model:'Deliberate 3.0',jobId:'j1',seed:'1',submittedAt:'2026-09-17T00:00:00Z'});
let attempt=state.scenes[0].attempts[0];
assert.equal(attempt.requested_model,'Deliberate 3.0');
assert.equal(attempt.observed_model,null,'nothing is observed until the provider reports it');
// The legacy field stays for backward compatibility with existing consumers.
assert.equal(attempt.model,'Deliberate 3.0');

// A provider that served a different model must not overwrite what we requested.
state=markSceneProviderResult(state,{
  sceneId:'s1',
  generation:{imageUrl:'https://example.invalid/a.webp',seed:'1',model:'majicMIX realistic',state:'ok'},
  completedAt:'2026-09-17T00:01:00Z',
});
attempt=state.scenes[0].attempts[0];
assert.equal(attempt.requested_model,'Deliberate 3.0','the request is never rewritten');
assert.equal(attempt.observed_model,'majicMIX realistic','what actually ran is recorded');
assert.equal(attempt.model_substituted,true);

// Benchmarks and history must attribute the image to what actually generated it.
const history=modelHistoryFromState(state);
assert.ok(history['majicMIX realistic'],'history is keyed by the model that actually ran');
assert.equal(history['Deliberate 3.0'],undefined,'a model that did not run earns no history');

// When the provider honours the request, both agree and nothing is flagged.
let honoured=createBatchState(manifest);
honoured=markSceneSubmitted(honoured,{sceneId:'s1',provider:'ai_horde',model:'Deliberate 3.0',jobId:'j2',seed:'2',submittedAt:'2026-09-17T00:00:00Z'});
honoured=markSceneProviderResult(honoured,{sceneId:'s1',generation:{imageUrl:'https://example.invalid/b.webp',seed:'2',model:'Deliberate 3.0',state:'ok'},completedAt:'2026-09-17T00:01:00Z'});
attempt=honoured.scenes[0].attempts[0];
assert.equal(attempt.observed_model,'Deliberate 3.0');
assert.equal(attempt.model_substituted,false);

// A provider that reports no model leaves observed_model unknown rather than assuming
// the requested one ran: an unverified attribution is not evidence.
let silent=createBatchState(manifest);
silent=markSceneSubmitted(silent,{sceneId:'s1',provider:'ai_horde',model:'Deliberate 3.0',jobId:'j3',seed:'3',submittedAt:'2026-09-17T00:00:00Z'});
silent=markSceneProviderResult(silent,{sceneId:'s1',generation:{imageUrl:'https://example.invalid/c.webp',seed:'3',model:null,state:'ok'},completedAt:'2026-09-17T00:01:00Z'});
attempt=silent.scenes[0].attempts[0];
assert.equal(attempt.observed_model,null);
assert.equal(attempt.model_substituted,false);
assert.deepEqual(modelHistoryFromState(silent),{},'an unattributable image earns no model history');

console.log('IMAGE_RENDER_MODEL_PROVENANCE_TEST=PASS');
