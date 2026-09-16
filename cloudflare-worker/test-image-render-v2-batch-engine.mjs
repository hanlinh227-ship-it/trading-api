import assert from 'node:assert/strict';
import {createBatchState,nextSubmissionSceneIds,markSceneSubmitted,markSceneProviderResult,applySceneQualityDecision,cancelBatchState,resetFailedScenesForRetry,summarizeBatch} from './image-render/batch-engine.js';

const manifest={batch_id:'b1',scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),status:'queued',attempts:[]}))};
let state=createBatchState(manifest);
assert.equal(nextSubmissionSceneIds(state).length,4);
for(const id of nextSubmissionSceneIds(state))state=markSceneSubmitted(state,{sceneId:id,provider:'ai_horde',model:'M',jobId:`job-${id}`,seed:id,submittedAt:'t1'});
assert.equal(nextSubmissionSceneIds(state).length,0);
state=applySceneQualityDecision(state,{sceneId:'1',quality:{decision:'RETRY_PROMPT',reasons:['duplicate_subject']},completedAt:'t2'});
assert.equal(state.scenes.find(x=>x.scene_id==='1').status,'retry_pending');
assert.equal(nextSubmissionSceneIds(state).length,1);
assert.equal(summarizeBatch(state).activeScenes,3);

let bounded=createBatchState({batch_id:'b2',scheduler_config:{concurrency:2},retry_policy:{maxAttempts:3},scenes:[{scene_id:'1',status:'queued',attempts:[]},{scene_id:'2',status:'queued',attempts:[]}]});
bounded=markSceneSubmitted(bounded,{sceneId:'1',provider:'ai_horde',model:'M',jobId:'job-1a',seed:'1',submittedAt:'t1'});
bounded=markSceneSubmitted(bounded,{sceneId:'2',provider:'ai_horde',model:'M',jobId:'job-2',seed:'2',submittedAt:'t1'});
bounded=applySceneQualityDecision(bounded,{sceneId:'2',quality:{decision:'PASS',reasons:[]},completedAt:'t2'});
for(let attempt=1;attempt<=3;attempt+=1){
  bounded=applySceneQualityDecision(bounded,{sceneId:'1',quality:{decision:'RETRY_PROMPT',reasons:['duplicate_subject']},completedAt:`t${attempt+1}`});
  if(attempt<3){
    assert.equal(bounded.scenes.find(x=>x.scene_id==='1').status,'retry_pending');
    bounded=markSceneSubmitted(bounded,{sceneId:'1',provider:'ai_horde',model:'M',jobId:`job-1${attempt+1}`,seed:String(attempt+1),submittedAt:`s${attempt+1}`});
  }
}
assert.equal(bounded.scenes.find(x=>x.scene_id==='1').status,'failed_quality');
assert.equal(bounded.scenes.find(x=>x.scene_id==='2').status,'complete');
assert.equal(summarizeBatch(bounded).status,'complete_with_failures');

let providerState=createBatchState({batch_id:'b3',scheduler_config:{concurrency:1},retry_policy:{maxAttempts:2},scenes:[{scene_id:'1',status:'queued',attempts:[]}]});
providerState=markSceneSubmitted(providerState,{sceneId:'1',provider:'ai_horde',model:'M',jobId:'job-p',seed:'1',submittedAt:'t1'});
providerState=markSceneProviderResult(providerState,{sceneId:'1',ok:true,generation:{imageUrl:'https://example.invalid/a.webp'},completedAt:'t2'});
assert.equal(providerState.scenes[0].status,'qa_pending');
providerState=applySceneQualityDecision(providerState,{sceneId:'1',quality:{decision:'FAIL_TERMINAL',reasons:['fatal']},completedAt:'t3'});
assert.equal(providerState.scenes[0].status,'failed_quality');
providerState=resetFailedScenesForRetry(providerState,['1']);
assert.equal(providerState.scenes[0].status,'retry_pending');
assert.equal(providerState.scenes[0].attempts.length,1);
const cancelled=cancelBatchState(createBatchState({batch_id:'b4',scheduler_config:{concurrency:1},retry_policy:{maxAttempts:1},scenes:[{scene_id:'1',status:'queued',attempts:[]}]}));
assert.equal(cancelled.scenes[0].status,'cancelled');
assert.equal(summarizeBatch(cancelled).status,'cancelled');
console.log('IMAGE_RENDER_V2_BATCH_ENGINE_TEST=PASS');
