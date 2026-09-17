// Acceptance: Scene 1 + MAX REF + MOMMY REF + BG01.
//
// The whole point of the V3 control plane is that the routing decision it makes survives
// every later layer. This test follows one reference scene from the intent the caller
// submits, through the logical job, into the physical batch manifest, down to the provider
// call that actually runs, and asserts that nothing the decision depended on is dropped on
// the way and that the volunteer provider is never reached.
import assert from 'node:assert/strict';
import {createImageLogicalJobClass} from './image-render/logical-job-state.js';
import {createImageRenderBatchClass} from './image-render/batch-state.js';
import {compileImageIntent} from './image-render/image-intent.js';

class MemoryStorage{
  constructor(){this.map=new Map();this.alarm=null;}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
  async delete(key){this.map.delete(key);}
  async setAlarm(value){this.alarm=value;}
  async deleteAlarm(){this.alarm=null;}
}

const PIXEL_B64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

// Scene 1 of the storyboard: two locked character references plus the locked background.
const SCENE_1=compileImageIntent({
  taskType:'REFERENCE_GENERATION',
  prompt:'Scene 1: MAX and MOMMY standing together in the BG01 kitchen at morning light',
  dataClass:'CONFIDENTIAL',
  qualityProfile:'STRICT',
  width:512,
  height:512,
  subjectCount:2,
  referenceAssets:[
    {id:'MAX_REF',role:'character',imageB64:PIXEL_B64},
    {id:'MOMMY_REF',role:'character',imageB64:PIXEL_B64},
  ],
  backgroundImage:{id:'BG01',role:'background',imageB64:PIXEL_B64},
  explicit:{backgroundConstraints:['BG01 kitchen layout must not change']},
  negativeConstraints:['extra limbs'],
});

// A stub Workers AI binding: this is what makes the reference-safe runtime present. The
// stub records every model it is asked to run so the test can prove which path executed.
function aiBinding(){
  const calls=[];
  return {
    calls,
    AI:{
      async run(model,input){
        calls.push({model,input});
        if(String(model).includes('vision')||String(model).includes('llava')){
          return {response:JSON.stringify({overallScore:93,confidence:0.9,dimensions:{},problems:[]})};
        }
        return {image:PIXEL_B64};
      },
    },
  };
}

function harness({env}){
  const batches=new Map();
  const BatchClass=createImageRenderBatchClass({now:()=>1_900_000_000_000});
  const batchClient={
    async createImageBatch(batchEnv,batchId,manifest){
      const object=new BatchClass({storage:new MemoryStorage()},batchEnv);
      batches.set(batchId,object);
      const response=await object.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest})}));
      return {ok:response.ok,status:response.status,...(await response.json())};
    },
    async getImageBatchStatus(_env,batchId){
      const object=batches.get(batchId);
      if(!object)return {ok:false};
      const response=await object.fetch(new Request('https://internal/status'));
      return {ok:response.ok,status:response.status,...(await response.json())};
    },
    async cancelImageBatch(){return {ok:true};},
  };
  const LogicalClass=createImageLogicalJobClass({batchClient,now:()=>1_900_000_000_000});
  return {batches,object:new LogicalClass({storage:new MemoryStorage()},env)};
}

const create=(object,intent)=>object.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jobId:'scene1-job',scenes:[{id:'scene-1',intent}],chunkSize:1})}));
const stateOf=async object=>(await (await object.fetch(new Request('https://internal/status'))).json()).state;

// 1. Reference-safe runtime present: the scene renders, and every routing input the V3
//    decision was made from is still on the physical manifest that runs it.
{
  const binding=aiBinding();
  // A fetch that would reach the volunteer provider fails the test outright.
  const env={AI:binding.AI,fetch:()=>{throw new Error('ai_horde_must_not_be_contacted');}};
  const {object,batches}=harness({env});
  await create(object,SCENE_1);
  await object.alarm();
  // Drive the physical batch's own alarm, which the Durable Object runtime fires for us
  // in production.
  for(const batch of batches.values())await batch.alarm();
  await object.alarm();

  const state=await stateOf(object);
  assert.equal(state.chunks.length,1);
  const batch=batches.get(state.chunks[0].physicalBatchId);
  assert.ok(batch,'the chunk must have reached a physical batch');
  const physical=(await (await batch.fetch(new Request('https://internal/status'))).json()).state;

  // Privacy is carried, never downgraded to PUBLIC to make a route fit.
  assert.equal(physical.data_class,'CONFIDENTIAL');
  const scene=physical.scenes[0];
  assert.equal(scene.task_type,'REFERENCE_GENERATION');
  assert.equal(scene.privacy_class,'CONFIDENTIAL');
  assert.equal(scene.provider_id,'cloudflare_workers_ai');
  assert.deepEqual(scene.reference_assets.map(ref=>ref.id),['MAX_REF','MOMMY_REF','BG01']);
  assert.ok(scene.background_constraints.includes('BG01 kitchen layout must not change'));
  assert.ok(scene.source_image,'the reference the provider renders from must survive');
  assert.equal(scene.negative_prompt,'extra limbs');

  // The provider that ran is the reference-safe one V3 selected.
  const attempt=scene.attempts.at(-1);
  assert.equal(attempt.provider,'cloudflare_workers_ai');
  assert.ok(binding.calls.some(call=>call.model.includes('img2img')),`expected an img2img call, saw ${binding.calls.map(c=>c.model).join(',')}`);
  // The reference bytes actually reached the model.
  const render=binding.calls.find(call=>call.model.includes('img2img'));
  assert.ok(Array.isArray(render.input.image)&&render.input.image.length>0,'reference image bytes must reach the provider');

  // A real asset came back and the scene finished.
  assert.ok(['complete','complete_unverified'].includes(scene.status),`scene status was ${scene.status}`);
  assert.ok(attempt.generation?.assetRef||attempt.generation?.imageUrl,'a real asset must be recorded');
}

// 2. No reference-safe runtime: the scene waits. The reference is never dropped and the
//    volunteer provider is never used as a substitute.
{
  const {object,batches}=harness({env:{}});
  await create(object,SCENE_1);
  await object.alarm();
  assert.equal(batches.size,0);
  assert.equal((await stateOf(object)).status,'waiting_for_safe_free_runtime');
}

// 3. The finished asset is reachable from the logical job, so a caller gets the image
//    back rather than only a status.
{
  const binding=aiBinding();
  const {object,batches}=harness({env:{AI:binding.AI}});
  await create(object,SCENE_1);
  await object.alarm();
  for(const batch of batches.values())await batch.alarm();
  await object.alarm();

  const scene=(await stateOf(object)).scenes[0];
  assert.ok(scene.asset,'the logical job must surface the produced asset');
  assert.equal(scene.asset.batchId,(await stateOf(object)).chunks[0].physicalBatchId);
  const served=await batches.get(scene.asset.batchId).fetch(new Request(`https://internal/asset?ref=${encodeURIComponent(scene.asset.ref)}`));
  assert.equal(served.status,200);
  assert.equal(served.headers.get('content-type'),scene.asset.contentType);
  assert.ok((await served.arrayBuffer()).byteLength>0,'the served asset must have bytes');
}

// 4. A spent free allocation is a wait, not a failure, and never a reason to pay.
{
  const exhausted=Object.assign(new Error('Neuron allocation exceeded'),{status:429});
  const env={AI:{async run(){throw exhausted;}}};
  const {object,batches}=harness({env});
  await create(object,SCENE_1);
  await object.alarm();
  for(const batch of batches.values())await batch.alarm();
  await object.alarm();
  assert.equal((await stateOf(object)).status,'waiting_for_free_compute');
}

// 5. A reference-safe runtime that rejects every model it has is reported as a missing
//    runtime, not as a failed scene: the reference is kept and the work waits.
{
  const env={AI:{async run(){throw Object.assign(new Error('no such model'),{status:404});}}};
  const {object,batches}=harness({env});
  await create(object,SCENE_1);
  await object.alarm();
  for(const batch of batches.values())await batch.alarm();
  await object.alarm();
  assert.equal((await stateOf(object)).status,'waiting_for_safe_free_runtime');
}

console.log('IMAGE_V4_REFERENCE_CONTINUITY=PASS');
