import assert from 'node:assert/strict';
import {createImageLogicalJobClass} from './image-render/logical-job-state.js';

class MemoryStorage{
  constructor(){this.map=new Map();this.alarm=null;}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
  async setAlarm(value){this.alarm=value;}
  async deleteAlarm(){this.alarm=null;}
}

const publicScene=i=>({id:`scene-${i}`,intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:`scene ${i}`,negativeConstraints:[],privacyClass:'PUBLIC',qualityProfile:'STRUCTURAL',referenceAssets:[],target:{width:512,height:512}}});

function harness(){
  const submitted=[];
  const cancelled=[];
  const physical=new Map();
  const batchClient={
    async createImageBatch(_env,batchId,manifest){
      assert.ok(!physical.has(batchId),`physical batch id reused: ${batchId}`);
      submitted.push({batchId,manifest});
      physical.set(batchId,{ok:true,summary:{status:'running'},state:{scenes:manifest.scenes.map(scene=>({...scene,status:'provider_processing'}))}});
      return {ok:true,status:201,summary:{status:'queued'}};
    },
    async getImageBatchStatus(_env,batchId){return physical.get(batchId);},
    async cancelImageBatch(_env,batchId){cancelled.push(batchId);return {ok:true};},
  };
  let nowValue=1_900_000_000_000;
  const LogicalClass=createImageLogicalJobClass({batchClient,now:()=>++nowValue});
  return {submitted,cancelled,physical,object:new LogicalClass({storage:new MemoryStorage()},{})};
}

const post=(path,body)=>new Request(`https://internal${path}`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
const stateOf=async object=>(await (await object.fetch(new Request('https://internal/status'))).json()).state;

// 1. Retrying a failed scene must never orphan a physical batch that is still running
//    for its sibling scenes: the chunk keeps its physicalBatchId so cancel still reaches it.
{
  const {object,physical,cancelled}=harness();
  await object.fetch(post('/create',{jobId:'job-mixed',scenes:[publicScene(1),publicScene(2)],chunkSize:2}));
  await object.alarm();
  let state=await stateOf(object);
  const batchId=state.chunks[0].physicalBatchId;
  assert.ok(batchId,'chunk must record its physical batch id after submission');

  // scene-1 failed on the provider while scene-2 is still being generated.
  physical.set(batchId,{ok:true,summary:{status:'running'},state:{scenes:[
    {scene_id:'scene-1',status:'failed_provider'},
    {scene_id:'scene-2',status:'provider_processing'},
  ]}});
  await object.alarm();
  state=await stateOf(object);
  assert.equal(state.scenes.find(scene=>scene.id==='scene-1').status,'failed_provider');
  assert.equal(state.scenes.find(scene=>scene.id==='scene-2').status,'provider_processing');

  await object.fetch(post('/retry',{sceneIds:['scene-1']}));
  state=await stateOf(object);
  assert.equal(state.chunks[0].physicalBatchId,batchId,'retry must not drop a live physical batch id');
  assert.equal(state.chunks[0].status,'submitted','chunk with an active scene must stay submitted');

  // The in-flight chunk must not be resubmitted while its physical batch is still live.
  await object.alarm();
  state=await stateOf(object);
  assert.equal(state.chunks[0].physicalBatchId,batchId);

  await object.fetch(new Request('https://internal/cancel',{method:'DELETE'}));
  assert.ok(cancelled.includes(batchId),'cancel must reach the still-running physical batch');
}

// 2. Re-running a settled chunk must allocate a fresh physical batch id so the previous
//    physical batch state is never clobbered.
{
  const {object,physical,submitted}=harness();
  await object.fetch(post('/create',{jobId:'job-resubmit',scenes:[publicScene(1)],chunkSize:1}));
  await object.alarm();
  let state=await stateOf(object);
  const firstBatchId=state.chunks[0].physicalBatchId;

  physical.set(firstBatchId,{ok:true,summary:{status:'complete_with_failures'},state:{scenes:[{scene_id:'scene-1',status:'failed_provider'}]}});
  await object.alarm();
  state=await stateOf(object);
  assert.equal(state.chunks[0].status,'complete_with_failures');

  await object.fetch(post('/retry',{sceneIds:['scene-1']}));
  await object.alarm();
  state=await stateOf(object);
  assert.equal(submitted.length,2,'the retried scene must be resubmitted');
  assert.notEqual(submitted[1].batchId,firstBatchId,'resubmission must use a fresh physical batch id');
  assert.equal(state.chunks[0].physicalBatchId,submitted[1].batchId);
}

console.log('image render v3 logical job retry lifecycle contracts: PASS');
