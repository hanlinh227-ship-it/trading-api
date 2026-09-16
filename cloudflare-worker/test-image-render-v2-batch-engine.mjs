import assert from 'node:assert/strict';
import {
  createBatchState,nextSubmissionSceneIds,markSceneSubmitted,markSceneProviderResult,
  applySceneQualityDecision,cancelBatchState,resetFailedScenesForRetry,summarizeBatch,
} from './image-render/batch-engine.js';

const manifest={
  batch_id:'b1',quality_mode:'STRICT',scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},
  scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),status:'queued',attempts:[],compiled_prompt:`scene ${i+1}`})),
};
let state=createBatchState(manifest);
assert.deepEqual(nextSubmissionSceneIds(state),['1','2','3','4']);
for(const id of nextSubmissionSceneIds(state)){
  state=markSceneSubmitted(state,{sceneId:id,provider:'ai_horde',model:'M',jobId:`job-${id}`,seed:id,submittedAt:'t1'});
}
assert.equal(nextSubmissionSceneIds(state).length,0);
state=applySceneQualityDecision(state,{sceneId:'1',quality:{decision:'RETRY_PROMPT',reasons:['duplicate_subject']},completedAt:'t2'});
assert.equal(state.scenes.find(x=>x.scene_id==='1').status,'retry_pending');
assert.deepEqual(nextSubmissionSceneIds(state),['1']);
assert.equal(summarizeBatch(state).activeScenes,3);

state=markSceneProviderResult(state,{sceneId:'2',generation:{imageUrl:'https://x/2.webp',model:'M',state:'ok'},completedAt:'t2'});
assert.equal(state.scenes.find(x=>x.scene_id==='2').status,'qa_pending');
state=applySceneQualityDecision(state,{sceneId:'2',quality:{decision:'PASS',verified:true,reasons:[]},completedAt:'t3'});
assert.equal(state.scenes.find(x=>x.scene_id==='2').status,'complete');

let retryState=createBatchState({batch_id:'b2',scheduler_config:{concurrency:1},retry_policy:{maxAttempts:3},scenes:[{scene_id:'A',status:'queued',attempts:[]},{scene_id:'B',status:'queued',attempts:[]}]});
for(let attempt=1;attempt<=3;attempt+=1){
  retryState=markSceneSubmitted(retryState,{sceneId:'A',provider:'ai_horde',model:`M${attempt}`,jobId:`job-A-${attempt}`,seed:String(attempt),submittedAt:`t${attempt}`});
  retryState=applySceneQualityDecision(retryState,{sceneId:'A',quality:{decision:'RETRY_MODEL',reasons:['severe_anatomy']},completedAt:`q${attempt}`});
}
assert.equal(retryState.scenes.find(x=>x.scene_id==='A').status,'failed_quality');
assert.deepEqual(nextSubmissionSceneIds(retryState),['B']);
retryState=markSceneSubmitted(retryState,{sceneId:'B',provider:'ai_horde',model:'M',jobId:'job-B',seed:'1',submittedAt:'t4'});
retryState=applySceneQualityDecision(retryState,{sceneId:'B',quality:{decision:'PASS_UNVERIFIED',verified:false,reasons:['visual_critic_unavailable']},completedAt:'q4'});
assert.equal(retryState.scenes.find(x=>x.scene_id==='B').status,'complete_unverified');
assert.equal(summarizeBatch(retryState).status,'complete_with_failures');

const reset=resetFailedScenesForRetry(retryState,['A']);
assert.equal(reset.scenes.find(x=>x.scene_id==='A').status,'retry_pending');
assert.equal(reset.scenes.find(x=>x.scene_id==='A').attempts.length,0);
const cancelled=cancelBatchState(reset);
assert.equal(cancelled.status,'cancelled');
assert.ok(cancelled.scenes.filter(x=>!['complete','complete_unverified'].includes(x.status)).every(x=>x.status==='cancelled'));

console.log('IMAGE_RENDER_V2_BATCH_ENGINE_TEST=PASS');
