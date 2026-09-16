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
}

const submitted=[];const cancelled=[];
const provider={
  async listModels(){return {ok:true,models:[{name:'Free Model',workerCount:4,performance:20,eta:0,queued:0}]};},
  async submit(input){const jobId=`job-${input.sceneId}-${submitted.length+1}`;submitted.push({jobId,sceneId:input.sceneId});return {ok:true,jobId};},
  async check(jobId){return {ok:true,done:true,waitTime:0,jobId};},
  async status(jobId){return {ok:true,done:true,generations:[{imageUrl:`https://example.invalid/${jobId}.webp`,censored:false,model:'Free Model',state:'ok',seed:'1'}]};},
  async cancel(jobId){cancelled.push(jobId);return {ok:true,cancelled:true};},
};
const registryFactory=()=>({get:id=>id==='ai_horde'?provider:null});
const qualityEvaluator=async()=>({decision:'PASS',reasons:[],qaLevel:'VISUAL',qaConfidence:1});
let clock=1000;const BatchClass=createImageRenderBatchClass({registryFactory,qualityEvaluator,now:()=>clock});
const storage=new MemoryStorage();
const first=new BatchClass({storage},{});
const manifest={batch_id:'b20',quality_mode:'STRICT',scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),original_prompt:`scene ${i+1}`,negative_prompt:'',model_candidates:['Free Model'],status:'queued',attempts:[],dimensions:{width:512,height:512}}))};
let response=await first.fetch(new Request('https://batch.internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest})}));
assert.equal(response.status,201);
await first.alarm();
assert.equal(submitted.length,4);
const firstSubmitted=submitted.map(x=>x.sceneId);
clock+=3000;
const resumed=new BatchClass({storage},{});
await resumed.alarm();
assert.equal(new Set(submitted.filter(x=>firstSubmitted.includes(x.sceneId)).map(x=>x.sceneId)).size,4);
assert.equal(submitted.filter(x=>firstSubmitted.includes(x.sceneId)).length,4,'completed scenes must not resubmit after reconstruction');
response=await resumed.fetch(new Request('https://batch.internal/status'));
const progress=await response.json();
assert.equal(progress.summary.completeScenes,4);
assert.equal(progress.summary.activeScenes,4);

const retryStorage=new MemoryStorage();let failOnce=true;
const retryProvider={...provider,async submit(input){const jobId=`retry-job-${input.sceneId}-${submitted.length+1}`;submitted.push({jobId,sceneId:input.sceneId});return {ok:true,jobId};}};
const RetryClass=createImageRenderBatchClass({registryFactory:()=>({get:()=>retryProvider}),qualityEvaluator:async()=>failOnce?(failOnce=false,{decision:'FAIL_TERMINAL',reasons:['fatal']}):({decision:'PASS',reasons:[]}),now:()=>clock});
const retryObj=new RetryClass({storage:retryStorage},{});
const one={...manifest,batch_id:'retry-b',scheduler_config:{concurrency:1},scenes:[{scene_id:'1',original_prompt:'one',negative_prompt:'',model_candidates:['Free Model'],status:'queued',attempts:[],dimensions:{width:512,height:512}}]};
await retryObj.fetch(new Request('https://batch.internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest:one})}));
await retryObj.alarm();await retryObj.alarm();
let status=await (await retryObj.fetch(new Request('https://batch.internal/status'))).json();
assert.equal(status.scenes[0].status,'failed_quality');
response=await retryObj.fetch(new Request('https://batch.internal/retry',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sceneIds:['1']})}));
assert.equal(response.status,200);
status=await response.json();assert.equal(status.scenes[0].status,'retry_pending');
await retryObj.alarm();
status=await (await retryObj.fetch(new Request('https://batch.internal/status'))).json();
assert.equal(status.scenes[0].attempts.length,2);
response=await retryObj.fetch(new Request('https://batch.internal/cancel',{method:'DELETE'}));
assert.equal(response.status,200);
assert.equal((await response.json()).summary.status,'cancelled');

const bindingStorage=new MemoryStorage();const bindingObject=new BatchClass({storage:bindingStorage},{});
const env={IMAGE_RENDER_BATCH:{idFromName:name=>({name}),get:()=>({fetch:req=>bindingObject.fetch(req)})}};
response=await createImageBatch(env,{batchId:'client-b',manifest:{...one,batch_id:'client-b'}});assert.equal(response.status,201);
response=await getImageBatchStatus(env,'client-b');assert.equal(response.status,200);
response=await retryImageBatchScenes(env,{batchId:'client-b',sceneIds:['1']});assert.equal(response.status,200);
response=await cancelImageBatch(env,'client-b');assert.equal(response.status,200);
response=await createImageBatch({}, {batchId:'missing',manifest:one});assert.equal(response.status,503);assert.equal((await response.json()).error,'image_render_batch_binding_unavailable');
console.log('IMAGE_RENDER_V2_BATCH_STATE_TEST=PASS');
