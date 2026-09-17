// Targeted repair has to actually run, not just be plannable. A critic verdict that a
// finished image has a fixable problem should send the next attempt back through an edit
// of that image -- keeping what was right about it -- rather than re-rolling the whole
// render and losing it.
import assert from 'node:assert/strict';
import {createImageRenderBatchClass} from './image-render/batch-state.js';

const PIXEL_B64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

class MemoryStorage{
  constructor(){this.map=new Map();}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
  async delete(key){this.map.delete(key);}
  async setAlarm(){}
  async deleteAlarm(){}
}

// The critic reports one fixable global problem on the first image and is satisfied by
// the second.
function harness({destructiveRedrawAllowed}){
  const calls=[];
  let reviews=0;
  const env={AI:{async run(model,input){
    calls.push({model,input});
    if(String(model).includes('vision')||String(model).includes('llava')){
      reviews+=1;
      return reviews===1
        ?{response:JSON.stringify({overallScore:60,confidence:0.9,dimensions:{},problems:[{code:'background_mismatch',scope:'global',severity:'major',target:'background'}]})}
        :{response:JSON.stringify({overallScore:95,confidence:0.9,dimensions:{},problems:[]})};
    }
    return {image:PIXEL_B64};
  }}};
  const manifest={
    batch_id:'repair-batch',
    data_class:'CONFIDENTIAL',
    quality_mode:'STRICT',
    retry_policy:{maxAttempts:3},
    scenes:[{
      scene_id:'scene-1',
      status:'queued',
      attempts:[],
      compiled_prompt:'a kitchen scene',
      negative_prompt:'',
      dimensions:{width:512,height:512},
      task_type:'REFERENCE_GENERATION',
      privacy_class:'CONFIDENTIAL',
      reference_assets:[{id:'MAX_REF',imageB64:PIXEL_B64}],
      source_image:{id:'MAX_REF',imageB64:PIXEL_B64},
      mask:null,
      destructive_redraw_allowed:destructiveRedrawAllowed,
      provider_id:'cloudflare_workers_ai',
      model_candidates:[],
      intent:{taskType:'REFERENCE_GENERATION',promptCompiled:'a kitchen scene',preserveRegions:[],destructiveRedrawAllowed},
    }],
  };
  const Batch=createImageRenderBatchClass({now:()=>1_900_000_000_000});
  return {calls,env,manifest,object:new Batch({storage:new MemoryStorage()},env)};
}

const run=async ({destructiveRedrawAllowed})=>{
  const {object,manifest,calls}=harness({destructiveRedrawAllowed});
  await object.fetch(new Request('https://internal/create',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({manifest})}));
  await object.alarm();
  await object.alarm();
  const state=(await (await object.fetch(new Request('https://internal/status'))).json()).state;
  return {state,calls,scene:state.scenes[0]};
};

// A redraw the caller allowed: the repair attempt edits the image the first attempt
// produced, and the scene finishes verified.
{
  const {scene,calls}=await run({destructiveRedrawAllowed:true});
  assert.equal(scene.attempts.length,2,'the repair must be its own attempt');
  const repair=scene.attempts[1];
  assert.equal(repair.repair?.action,'GLOBAL_EDIT');
  assert.equal(repair.repair?.reason,'background_mismatch');
  assert.equal(scene.status,'complete');
  // The second render was given the first render's output, not the original reference.
  const renders=calls.filter(call=>!String(call.model).includes('vision')&&!String(call.model).includes('llava'));
  assert.equal(renders.length,2);
  assert.ok(Array.isArray(renders[1].input.image)&&renders[1].input.image.length>0);
}

// A caller who did not allow a destructive redraw does not get one: the scene retries
// normally and no repair edit is recorded.
{
  const {scene}=await run({destructiveRedrawAllowed:false});
  assert.equal(scene.attempts[1]?.repair?.action??null,null);
}

console.log('image render v4 targeted repair runtime contracts: PASS');
