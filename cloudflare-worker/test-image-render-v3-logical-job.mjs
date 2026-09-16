import assert from 'node:assert/strict';
import {applyLogicalJobEvent,cancelLogicalJob,createLogicalJob,nextLogicalJobActions,retryLogicalJobScenes} from './image-render/logical-job-engine.js';

const scenes=n=>Array.from({length:n},(_,i)=>({id:`scene-${i+1}`,prompt:`scene ${i+1}`}));
for(const [count,chunks] of [[1,1],[100,1],[101,2],[5000,50]]){
  const state=createLogicalJob({jobId:`job-${count}`,scenes:scenes(count),chunkSize:100});
  assert.equal(state.sceneCount,count);
  assert.equal(state.chunks.length,chunks);
  assert.ok(state.chunks.every(chunk=>chunk.sceneIds.length<=100));
}
assert.throws(()=>createLogicalJob({jobId:'runaway',scenes:scenes(100001)}),/operational_scene_limit_exceeded/);

let state=createLogicalJob({jobId:'job-flow',scenes:scenes(3),chunkSize:2});
assert.equal(nextLogicalJobActions(state).length,1);
state=applyLogicalJobEvent(state,{type:'SCENE_STATUS',sceneId:'scene-1',status:'complete'});
state=applyLogicalJobEvent(state,{type:'SCENE_STATUS',sceneId:'scene-2',status:'failed_provider'});
assert.equal(state.status,'partially_complete');
state=retryLogicalJobScenes(state,['scene-2']);
assert.equal(state.scenes.find(scene=>scene.id==='scene-2').status,'queued');
state=applyLogicalJobEvent(state,{type:'WAITING_FOR_FREE_COMPUTE'});
assert.equal(state.status,'waiting_for_free_compute');
state=applyLogicalJobEvent(state,{type:'RESUME'});
assert.equal(state.status,'partially_complete');
state=cancelLogicalJob(state);
assert.equal(state.status,'cancelled');
assert.ok(state.scenes.filter(scene=>scene.id!=='scene-1').every(scene=>scene.status==='cancelled'));

assert.throws(()=>createLogicalJob({jobId:'dup',scenes:[{id:'x'},{id:'x'}]}),/duplicate_scene_id/);
console.log('image render v3 logical job contracts: PASS');
