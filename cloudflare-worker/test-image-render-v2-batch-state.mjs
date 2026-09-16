import assert from 'node:assert/strict';
import {createImageRenderBatchClass} from './image-render/batch-state.js';
import {createImageBatch,getImageBatchStatus,cancelImageBatch,retryImageBatchScenes} from './image-render/batch-client.js';

class MemoryStorage{
  constructor(){this.map=new Map();this.alarm=null;}
  async get(k){return this.map.get(k);}
  async put(k,v){this.map.set(k,structuredClone(v));}
  async delete(k){this.map.delete(k);}
  async setAlarm(v){this.alarm=v;}
  async getAlarm(){return this.alarm;}
  async deleteAlarm(){this.alarm=null;}
}

const manifest={
  batch_id:'batch-do-1',data_class:'PUBLIC',quality_mode:'STRUCTURAL',
  scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},preferred_models:['Model A'],
  scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),status:'queued',attempts:[],compiled_prompt:`scene ${i+1}`,negative_prompt:'bad anatomy',dimensions:{width:512,height:512}})),
};

const submitted=[];
const cancelled=[];
const provider={
  id:'ai_horde',
  async listModels(){return {ok:true,models:[{name:'Model A',workerCount:8,performance:20,eta:1,queued:0}]};},
  async submit(input){
    const sceneId=String(input.sceneId);
    submitted.push(sceneId);
    return {ok:true,jobId:`job-${sceneId}-${submitted.length}`};
  },
  async check(jobId){return {ok:true,done:true,faulted:false,waitTime:0,jobId};},
  async status(jobId){
    const sceneId=jobId.split('-')[1];
    return {ok:true,done:true,generations:[{imageUrl:`https://example.invalid/${sceneId}.webp`,model:'Model A',seed:sceneId,state:'ok',censored:false}]};
  },
  async cancel(jobId){cancelled.push(jobId);return {ok:true,cancelled:true};},
};
const registryFactory=()=>({list:()=>['ai_horde'],get:id=>id==='ai_horde'?provider:null});
const qualityEvaluator=async()=>({decision:'PASS',verified:true,reasons:[]});
let nowValue=1_800_000_000_000;
const now=()=>++nowValue;
const BatchClass=createImageRenderBatchClass({registryFactory,qualityEvaluator,now});
const storage=new MemoryStorage();
let object=new BatchClass({storage},{});

let response=await object.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest})}));
assert.equal(response.status,201);
await object.alarm();
let status=await (await object.fetch(new Request('https://internal/status'))).json();
assert.equal(status.summary.activeScenes,4);
assert.equal(submitted.length,4);
await object.alarm();
status=await (await object.fetch(new Request('https://internal/status'))).json();
assert.equal(status.summary.completeScenes,4);
assert.equal(submitted.length,8);

object=new BatchClass({storage},{});
await object.alarm();
status=await (await object.fetch(new Request('https://internal/status'))).json();
assert.equal(status.summary.completeScenes,8);
assert.equal(submitted.length,12);
assert.equal(new Set(submitted).size,submitted.length,'completed scenes must not be resubmitted after Durable Object reconstruction');

response=await object.fetch(new Request('https://internal/cancel',{method:'DELETE'}));
assert.equal(response.status,200);
status=await response.json();
assert.equal(status.summary.status,'cancelled');
assert.ok(cancelled.length>0,'active provider jobs should be cancelled when supported');

const retryStorage=new MemoryStorage();
const retryManifest={...manifest,batch_id:'batch-retry',scheduler_config:{concurrency:1},scenes:[{scene_id:'1',status:'failed_quality',attempts:[{attempt:3}]},{scene_id:'2',status:'complete',attempts:[{attempt:1}]}]};
const retryObject=new BatchClass({storage:retryStorage},{});
await retryObject.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest:retryManifest})}));
response=await retryObject.fetch(new Request('https://internal/retry',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sceneIds:['1']})}));
assert.equal(response.status,200);
const retried=await response.json();
assert.equal(retried.state.scenes.find(x=>x.scene_id==='1').status,'retry_pending');
assert.equal(retried.state.scenes.find(x=>x.scene_id==='1').attempts.length,0);
assert.equal(retried.state.scenes.find(x=>x.scene_id==='2').status,'complete');

const stub={fetch:request=>object.fetch(request)};
const env={IMAGE_RENDER_BATCH:{idFromName:name=>`id:${name}`,get:id=>{assert.equal(id,'id:client-batch');return stub;}}};
const clientManifest={...manifest,batch_id:'client-batch'};
assert.equal((await createImageBatch(env,'client-batch',clientManifest)).ok,true);
assert.equal((await getImageBatchStatus(env,'client-batch')).ok,true);
assert.equal((await retryImageBatchScenes(env,'client-batch',['1'])).ok,true);
assert.equal((await cancelImageBatch(env,'client-batch')).ok,true);
await assert.rejects(()=>getImageBatchStatus({},'x'),/image_render_batch_binding_unavailable/);

console.log('IMAGE_RENDER_V2_BATCH_STATE_TEST=PASS');
