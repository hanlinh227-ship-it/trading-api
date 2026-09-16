import assert from 'node:assert/strict';
import {createImageLogicalJobClass} from './image-render/logical-job-state.js';
import {cancelImageLogicalJob,createImageLogicalJob,getImageLogicalJobStatus,retryImageLogicalJobScenes} from './image-render/logical-job-client.js';

class MemoryStorage{
  constructor(){this.map=new Map();this.alarm=null;}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
  async setAlarm(value){this.alarm=value;}
  async deleteAlarm(){this.alarm=null;}
}
const submitted=[];
const cancelled=[];
const physical=new Map();
const batchClient={
  async createImageBatch(_env,batchId,manifest){submitted.push({batchId,manifest});physical.set(batchId,{ok:true,summary:{status:'running'},state:{scenes:manifest.scenes.map(scene=>({...scene,status:'queued'}))}});return {ok:true,status:201,summary:{status:'queued'}};},
  async getImageBatchStatus(_env,batchId){return physical.get(batchId);},
  async cancelImageBatch(_env,batchId){cancelled.push(batchId);return {ok:true};},
};
let nowValue=1_900_000_000_000;
const LogicalClass=createImageLogicalJobClass({batchClient,now:()=>++nowValue});
const storage=new MemoryStorage();
const object=new LogicalClass({storage},{});
const publicScene=i=>({id:`scene-${i}`,intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:`scene ${i}`,negativeConstraints:[],privacyClass:'PUBLIC',qualityProfile:'STRUCTURAL',referenceAssets:[],target:{width:512,height:512}}});

let response=await object.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jobId:'logical-205',scenes:Array.from({length:205},(_,i)=>publicScene(i+1)),chunkSize:100})}));
assert.equal(response.status,201);
let payload=await response.json();
assert.equal(payload.state.chunks.length,3);
await object.alarm();
assert.equal(submitted.length,1);
assert.equal(submitted[0].manifest.scenes.length,100);
assert.equal(submitted[0].manifest.data_class,'PUBLIC');

const privateStorage=new MemoryStorage();
const privateObject=new LogicalClass({storage:privateStorage},{});
await privateObject.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jobId:'private-ref',scenes:[{id:'scene-1',intent:{taskType:'REFERENCE_GENERATION',promptCompiled:'same Max',negativeConstraints:[],privacyClass:'CONFIDENTIAL',qualityProfile:'STRICT_VISUAL',referenceAssets:[{id:'ref'}],target:{width:512,height:512}}}]})}));
await privateObject.alarm();
payload=await (await privateObject.fetch(new Request('https://internal/status'))).json();
assert.equal(payload.state.status,'waiting_for_safe_free_runtime');

const stub={fetch:request=>object.fetch(request)};
const env={IMAGE_LOGICAL_JOB:{idFromName:name=>`id:${name}`,get:id=>{assert.equal(id,'id:logical-205');return stub;}}};
assert.equal((await getImageLogicalJobStatus(env,'logical-205')).ok,true);
assert.equal((await retryImageLogicalJobScenes(env,'logical-205',['scene-1'])).ok,true);
assert.equal((await cancelImageLogicalJob(env,'logical-205')).ok,true);
assert.ok(cancelled.length>=1);
await assert.rejects(()=>createImageLogicalJob({},'x',[publicScene(1)]),/image_logical_job_binding_unavailable/);

console.log('image render v3 logical durable state contracts: PASS');
