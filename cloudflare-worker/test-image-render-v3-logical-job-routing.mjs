import assert from 'node:assert/strict';
import {createImageLogicalJobClass} from './image-render/logical-job-state.js';

class MemoryStorage{
  constructor(){this.map=new Map();this.alarm=null;}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
  async setAlarm(value){this.alarm=value;}
  async deleteAlarm(){this.alarm=null;}
}

function harness(){
  const submitted=[];
  const batchClient={
    async createImageBatch(_env,batchId,manifest){submitted.push({batchId,manifest});return {ok:true,status:201,summary:{status:'queued'}};},
    async getImageBatchStatus(){return {ok:true,summary:{status:'running'},state:{scenes:[]}};},
    async cancelImageBatch(){return {ok:true};},
  };
  let nowValue=1_900_000_000_000;
  const LogicalClass=createImageLogicalJobClass({batchClient,now:()=>++nowValue});
  return {submitted,object:new LogicalClass({storage:new MemoryStorage()},{})};
}

const intent=extra=>({taskType:'TEXT_TO_IMAGE',promptCompiled:'a scene',negativeConstraints:[],privacyClass:'PUBLIC',qualityProfile:'STRUCTURAL',referenceAssets:[],target:{width:512,height:512},...extra});
const create=(object,scene)=>object.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jobId:'job',scenes:[{id:'scene-1',intent:scene}],chunkSize:1})}));
const stateOf=async object=>(await (await object.fetch(new Request('https://internal/status'))).json()).state;

// Routing goes through the provider mesh's eligibility gates, not a second hardcoded list.
// A PUBLIC prompt-only scene is executable on the volunteer provider.
{
  const {object,submitted}=harness();
  await create(object,intent());
  await object.alarm();
  assert.equal(submitted.length,1);
  assert.equal(submitted[0].manifest.data_class,'PUBLIC');
}

// Every route with no reference-safe free runtime waits; the reference is never dropped
// to force a prompt-only render, and the scene is never sent to the volunteer provider.
for(const scene of [
  intent({privacyClass:'CONFIDENTIAL',taskType:'REFERENCE_GENERATION',referenceAssets:[{id:'ref'}]}),
  intent({privacyClass:'PUBLIC',taskType:'REFERENCE_GENERATION',referenceAssets:[{id:'ref'}]}),
  // A PUBLIC prompt-only task type still must not reach a non-reference-safe provider
  // once the caller attaches a reference asset.
  intent({privacyClass:'PUBLIC',taskType:'TEXT_TO_IMAGE',referenceAssets:[{id:'ref'}]}),
  intent({privacyClass:'PUBLIC',taskType:'INPAINT',referenceAssets:[{id:'src'}]}),
]){
  const {object,submitted}=harness();
  await create(object,scene);
  await object.alarm();
  assert.equal(submitted.length,0,`${scene.taskType} must not be submitted to a volunteer provider`);
  assert.equal((await stateOf(object)).status,'waiting_for_safe_free_runtime',scene.taskType);
}

// A non-public prompt-only scene fails closed too: the volunteer provider is PUBLIC-only.
{
  const {object,submitted}=harness();
  await create(object,intent({privacyClass:'INTERNAL'}));
  await object.alarm();
  assert.equal(submitted.length,0);
  assert.ok(String((await stateOf(object)).status).startsWith('waiting_for_'));
}

console.log('image render v3 logical job routing contracts: PASS');
