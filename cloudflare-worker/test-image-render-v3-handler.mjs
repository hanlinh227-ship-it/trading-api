import assert from 'node:assert/strict';
import {handleImageRenderV3} from './image-render-v3-entry.js';
import {createImageLogicalJobClass} from './image-render/logical-job-state.js';

class MemoryStorage{constructor(){this.map=new Map();this.alarm=null;}async get(k){return this.map.get(k);}async put(k,v){this.map.set(k,structuredClone(v));}async setAlarm(v){this.alarm=v;}async deleteAlarm(){this.alarm=null;}}
const objects=new Map();
const LogicalClass=createImageLogicalJobClass({batchClient:{
  async createImageBatch(){return {ok:false,status:503,error:'no_free_compute'};},
  async getImageBatchStatus(){return {ok:false,status:503};},
  async cancelImageBatch(){return {ok:true};},
}});
const binding={
  idFromName:name=>name,
  get:id=>{
    if(!objects.has(id))objects.set(id,new LogicalClass({storage:new MemoryStorage()},{ }));
    return {fetch:request=>objects.get(id).fetch(request)};
  },
};
const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:'secret',IMAGE_LOGICAL_JOB:binding};
const auth={'x-image-render-token':'secret'};

let response=await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities'),env);
assert.equal(response.status,401);
response=await handleImageRenderV3(new Request('https://x/brain/image/v3/capabilities',{headers:auth}),env);
assert.equal(response.status,200);
let payload=await response.json();
assert.equal(payload.mode,'FREE_ONLY');
assert.equal(payload.localRuntimeRequired,false);
assert.equal(payload.logicalJobs.physicalChunkMaxScenes,100);

const scenes=Array.from({length:101},(_,i)=>({id:`s-${i+1}`,taskType:'TEXT_TO_IMAGE',prompt:`scene ${i+1}`,dataClass:'PUBLIC',width:512,height:512,qualityProfile:'STRUCTURAL'}));
response=await handleImageRenderV3(new Request('https://x/brain/image/v3/jobs',{method:'POST',headers:{...auth,'content-type':'application/json'},body:JSON.stringify({scenes})}),env);
assert.equal(response.status,202);
payload=await response.json();
assert.equal(payload.sceneCount,101);
assert.ok(payload.jobId.startsWith('imgjob-'));
const jobId=payload.jobId;

response=await handleImageRenderV3(new Request(`https://x/brain/image/v3/jobs/status?id=${encodeURIComponent(jobId)}`,{headers:auth}),env);
assert.equal(response.status,200);
payload=await response.json();
assert.equal(payload.state.sceneCount,101);
assert.equal(payload.state.chunks.length,2);

response=await handleImageRenderV3(new Request('https://x/brain/image/v3/models',{headers:auth}),env);
assert.equal(response.status,200);
payload=await response.json();
assert.equal(payload.mode,'FREE_ONLY');
assert.ok(payload.vault.every(model=>model.approvalStatus==='CANDIDATE'));

console.log('image render v3 handler contracts: PASS');
