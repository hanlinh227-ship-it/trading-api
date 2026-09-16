import assert from 'node:assert/strict';
import {
  createBatchState,nextSubmissionSceneIds,markSceneSubmitted,markSceneProviderResult,
  applySceneQualityDecision,cancelBatchState,resetFailedScenesForRetry,summarizeBatch,
} from './image-render/batch-engine.js';

const manifest={
  batch_id:'b1',scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},
  scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),status:'queued',attempts:[]})),
};
let state=createBatchState(manifest);
assert.equal(nextSubmissionSceneIds(state).length,4);
for(const id of nextSubmissionSceneIds(state))state=markSceneSubmitted(state,{sceneId:id,provider:'ai_horde',model:'M',jobId:`job-${id}`,seed:id,submittedAt:'t1'});
assert.equal(nextSubmissionSceneIds(state).length,0);
state=markSceneProviderResult(state,{sceneId:'1',generation:{imageUrl:'https://example.invalid/1.webp',model:'M',seed:'1',state:'ok',censored:false},completedAt:'t2'});
assert.equal(state.scenes.find(x=>x.scene_id==='1').status,'qa_pending');
state=applySceneQualityDecision(state,{sceneId:'1',quality:{decision:'RETRY_PROMPT',reasons:['duplicate_subject']},completedAt:'t2'});
assert.equal(state.scenes.find(x=>x.scene_id==='1').status,'retry_pending');
assert.equal(nextSubmissionSceneIds(state).length,1);
assert.equal(summarizeBatch(state).activeScenes,3);

for(let attempt=2;attempt<=3;attempt++){
  state=markSceneSubmitted(state,{sceneId:'1',provider:'ai_horde',model:`M${attempt}`,jobId:`job-1-${attempt}`,seed:String(attempt),submittedAt:`t${attempt}`});
  state=markSceneProviderResult(state,{sceneId:'1',generation:{imageUrl:`https://example.invalid/1-${attempt}.webp`,model:`M${attempt}`,seed:String(attempt),state:'ok',censored:false},completedAt:`t${attempt}x`});
  state=applySceneQualityDecision(state,{sceneId:'1',quality:{decision:'RETRY_MODEL',reasons:['severe_anatomy']},completedAt:`t${attempt}x`});
}
assert.equal(state.scenes.find(x=>x.scene_id==='1').status,'failed_quality');
state=markSceneProviderResult(state,{sceneId:'2',generation:{imageUrl:'https://example.invalid/2.webp',model:'M',seed:'2',state:'ok',censored:false},completedAt:'t4'});
state=applySceneQualityDecision(state,{sceneId:'2',quality:{decision:'PASS',reasons:[]},completedAt:'t4'});
assert.equal(state.scenes.find(x=>x.scene_id==='2').status,'complete');
assert.notEqual(summarizeBatch(state).status,'failed');

let retryState=resetFailedScenesForRetry(state,['1']);
assert.equal(retryState.scenes.find(x=>x.scene_id==='1').status,'queued');
assert.deepEqual(retryState.scenes.find(x=>x.scene_id==='1').attempts,[]);
retryState=cancelBatchState(retryState);
assert.equal(retryState.status,'cancelled');
assert.equal(nextSubmissionSceneIds(retryState).length,0);
console.log('IMAGE_RENDER_V2_BATCH_ENGINE_TEST=PASS');
