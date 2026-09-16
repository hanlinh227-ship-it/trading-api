import assert from 'node:assert/strict';
import {createImageRenderBatchClass} from './image-render/batch-state.js';
import {createImageBatch,getImageBatchStatus,cancelImageBatch,retryImageBatchScenes} from './image-render/batch-client.js';

class MemoryStorage{
  constructor(){this.map=new Map();this.alarm=null;}
  async get(key){return structuredClone(this.map.get(key));}
  async put(key,value){this.map.set(key,structuredClone(value));}
  async delete(key){this.map.delete(key);}
  async setAlarm(value){this.alarm=value;}
  async getAlarm(){return this.alarm;}
  async deleteAlarm(){this.alarm=null;}
}

const submitted=[];
const provider={
  id:'ai_horde',
  async listModels(){return {ok:true,models:[{name:'M',workerCount:8,performance:20,eta:0,queued:0}]};},
  async submit(input){const jobId=`job-${submitted.length+1}`;submitted.push({jobId,prompt:input.prompt});return {ok:true,jobId,request:{models:input.models||[]}};},
  async check(jobId){return {ok:true,jobId,done:true,faulted:false,waitTime:0};},
  async status(jobId){return {ok:true,jobId,done:true,faulted:false,generations:[{imageUrl:`https://example.invalid/${jobId}.webp`,model:'M',seed:jobId,state:'ok',censored:false}]};},
  async cancel(jobId){return {ok:true,jobId,cancelled:true};},
};
const registryFactory=()=>({get:id=>id==='ai_horde'?provider:null,list:()=>['ai_horde']});
const qualityEvaluator=async()=>({decision:'PASS',sceneStatus:'complete',qaLevel:'VISUAL',qaConfidence:1,reasons:[]});
let clock=1000;
const BatchClass=createImageRenderBatchClass({registryFactory,qualityEvaluator,now:()=>clock});
const storage=new MemoryStorage();
const env={};
let object=new BatchClass({storage},env);
const manifest={batch_id:'batch-1',quality_mode:'STRICT',scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),original_prompt:`scene ${i+1}`,compiled_prompt:`scene ${i+1}`,negative_prompt:'',dimensions:{width:512,height:512},model_candidates:['M'],status:'queued',attempts:[]}))};

let response=await object.fetch(new Request('https://batch.internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest})}));
assert.equal(response.status,201);
await object.alarm();
let body=await (await object.fetch(new Request('https://batch.internal/status'))).json();
assert.equal(body.summary.activeScenes,4);
assert.equal(submitted.length,4);

object=new BatchClass({storage},env);
clock+=3000;
await object.alarm();
body=await (await object.fetch(new Request('https://batch.internal/status'))).json();
assert.equal(body.summary.completeScenes,4);
assert.equal(submitted.length,8);
assert.equal(new Set(submitted.map(x=>x.prompt)).size,8,'resume must not resubmit completed scenes');

response=await object.fetch(new Request('https://batch.internal/cancel',{method:'DELETE'}));
assert.equal(response.status,200);
body=await response.json();
assert.equal(body.summary.status,'cancelled');

const failed=structuredClone(await storage.get('image-render-batch-state-v2'));
failed.status='complete_with_failures';
failed.scenes[0].status='failed_quality';
await storage.put('image-render-batch-state-v2',failed);
response=await object.fetch(new Request('https://batch.internal/retry',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sceneIds:['1']})}));
assert.equal(response.status,200);
body=await response.json();
assert.equal(body.state.scenes[0].status,'queued');

const calls=[];
const stub={fetch:async request=>{calls.push({url:request.url,method:request.method,body:request.method==='GET'?null:await request.clone().json().catch(()=>null)});return new Response(JSON.stringify({ok:true,summary:{status:'queued'}}),{status:200,headers:{'content-type':'application/json'}});}};
const namespace={idFromName:name=>`id:${name}`,get:id=>({...stub,id})};
const clientEnv={IMAGE_RENDER_BATCH:namespace};
await createImageBatch(clientEnv,'client-batch',{batch_id:'client-batch',scenes:[]});
await getImageBatchStatus(clientEnv,'client-batch');
await cancelImageBatch(clientEnv,'client-batch');
await retryImageBatchScenes(clientEnv,'client-batch',['1']);
assert.deepEqual(calls.map(x=>[new URL(x.url).pathname,x.method]),[['/create','POST'],['/status','GET'],['/cancel','DELETE'],['/retry','POST']]);
await assert.rejects(()=>createImageBatch({},'x',{}),/image_render_batch_binding_unavailable/);
console.log('IMAGE_RENDER_V2_BATCH_STATE_TEST=PASS');
