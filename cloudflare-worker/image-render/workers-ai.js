// Cloudflare Workers AI execution client. The Worker reaches these models through its own
// AI binding, so no credential is stored and no new third party sees the data.
// Model IDs are the verified Workers AI catalogue IDs; nothing here is inferred from a name.
import {fullyEditableMask} from './png.js';

export const WORKERS_AI_MODELS=Object.freeze({
  textToImage:'@cf/black-forest-labs/flux-1-schnell',
  imageToImage:'@cf/runwayml/stable-diffusion-v1-5-img2img',
  inpainting:'@cf/runwayml/stable-diffusion-v1-5-inpainting',
  sdxlBase:'@cf/stabilityai/stable-diffusion-xl-base-1.0',
  vision:'@cf/llava-hf/llava-1.5-7b-hf',
  visionLarge:'@cf/meta/llama-3.2-11b-vision-instruct',
});

// A task names an ordered list of Workers AI models, not one model. Every entry here is a
// diffusion model Cloudflare documents as accepting `image[]` (and `mask[]` where the task
// needs it), so a task is only reported unavailable when the whole free runtime is, not
// when one hosted model is withdrawn or failing. The order is preference, and the first
// entry stays the model the rest of the system already names for the task.
// Only models whose licence is audited in the vault may run, and only where the runtime
// actually accepts the inputs the task needs. Production reports 3030 ("input tensor
// `image` is not present in the model") for SDXL base, so despite what its documented
// parameter list suggests it is a text-only model here and never backs an image-conditioned
// task. The runtime is the authority on this, not the model page.
const TEXT_FALLBACKS=Object.freeze([WORKERS_AI_MODELS.sdxlBase]);
// The inpainting model given a fully-editable mask is image-to-image. That makes it the
// fallback for whole-image edits when the dedicated img2img model is unavailable.
const IMAGE_TO_IMAGE=Object.freeze([WORKERS_AI_MODELS.imageToImage,WORKERS_AI_MODELS.inpainting]);
const INPAINTING=Object.freeze([WORKERS_AI_MODELS.inpainting]);
const TASK_MODELS=Object.freeze({
  TEXT_TO_IMAGE:Object.freeze([WORKERS_AI_MODELS.textToImage,...TEXT_FALLBACKS]),
  MULTI_SCENE_BATCH:Object.freeze([WORKERS_AI_MODELS.textToImage,...TEXT_FALLBACKS]),
  REFERENCE_GENERATION:IMAGE_TO_IMAGE,
  IMAGE_EDIT_GLOBAL:IMAGE_TO_IMAGE,
  STYLE_TRANSFER:IMAGE_TO_IMAGE,
  BACKGROUND_REPLACE:INPAINTING,
  OBJECT_REPLACE:INPAINTING,
  IMAGE_EDIT_LOCAL:INPAINTING,
  INPAINT:INPAINTING,
  TARGETED_REPAIR:INPAINTING,
});

// Which inputs a task must have, rather than which a given model happens to accept: an
// img2img task run on a fallback model still has to be given the image it edits.
const SOURCE_IMAGE_TASKS=new Set(['REFERENCE_GENERATION','IMAGE_EDIT_GLOBAL','STYLE_TRANSFER','BACKGROUND_REPLACE','OBJECT_REPLACE','IMAGE_EDIT_LOCAL','INPAINT','TARGETED_REPAIR']);
const MASK_TASKS=new Set(['BACKGROUND_REPLACE','OBJECT_REPLACE','IMAGE_EDIT_LOCAL','INPAINT','TARGETED_REPAIR']);

// Parameter names and bounds are Cloudflare's published schema for these models.
const DIFFUSION_INPUTS={accepts:new Set(['prompt','negative_prompt','width','height','image','mask','strength','seed','num_steps','guidance']),stepsCeiling:20};
const MODEL_INPUT_SCHEMA=Object.freeze({
  [WORKERS_AI_MODELS.textToImage]:{accepts:new Set(['prompt','steps']),stepsMax:8,stepsDefault:4},
  [WORKERS_AI_MODELS.imageToImage]:DIFFUSION_INPUTS,
  [WORKERS_AI_MODELS.inpainting]:DIFFUSION_INPUTS,
  [WORKERS_AI_MODELS.sdxlBase]:DIFFUSION_INPUTS,
});

const clampInt=(value,min,max)=>Math.min(max,Math.max(min,Math.round(Number(value))));

function buildInput(model,{prompt,image,mask,width,height,negativePrompt,strength,seed,steps}){
  const schema=MODEL_INPUT_SCHEMA[model]||{accepts:new Set(['prompt'])};
  const candidate={prompt:String(prompt)};
  if(negativePrompt)candidate.negative_prompt=String(negativePrompt);
  if(Number.isInteger(width)&&width>0)candidate.width=width;
  if(Number.isInteger(height)&&height>0)candidate.height=height;
  if(image)candidate.image=image;
  if(mask)candidate.mask=mask;
  if(Number.isFinite(strength))candidate.strength=strength;
  if(Number.isInteger(seed))candidate.seed=seed;
  if(schema.stepsMax!==undefined){
    candidate.steps=clampInt(Number.isFinite(Number(steps))?steps:schema.stepsDefault,1,schema.stepsMax);
  }else if(schema.accepts.has('num_steps')&&Number.isFinite(Number(steps))){
    candidate.num_steps=clampInt(steps,1,schema.stepsCeiling||20);
  }
  return Object.fromEntries(Object.entries(candidate).filter(([key])=>schema.accepts.has(key)));
}

export function workersAiModelChain(taskType){return [...(TASK_MODELS[String(taskType||'')]||[])];}
export function selectWorkersAiModel(taskType){return workersAiModelChain(taskType)[0]||null;}

// Workers AI returns image bytes two ways depending on the model: a base64 string on the
// JSON-shaped responses and a byte stream on the diffusion models. Normalizing here keeps
// the rest of the system from having to know which model it asked for.
export async function readWorkersAiImageBytes(output){
  if(!output)return null;
  if(output instanceof Uint8Array)return output;
  if(output instanceof ArrayBuffer)return new Uint8Array(output);
  if(typeof output.getReader==='function'){
    const reader=output.getReader();
    const chunks=[];let total=0;
    for(;;){
      const {done,value}=await reader.read();
      if(done)break;
      const bytes=value instanceof Uint8Array?value:new Uint8Array(value);
      chunks.push(bytes);total+=bytes.length;
    }
    const merged=new Uint8Array(total);let offset=0;
    for(const chunk of chunks){merged.set(chunk,offset);offset+=chunk.length;}
    return merged;
  }
  const b64=typeof output==='string'?output:typeof output.image==='string'?output.image:null;
  if(!b64)return null;
  try{return Uint8Array.from(atob(b64),char=>char.charCodeAt(0));}catch{return null;}
}

function binding(env){
  const ai=env?.AI;
  return ai&&typeof ai.run==='function'?ai:null;
}

function isAllocationExhausted(error){
  const status=Number(error?.status||error?.code||0);
  const message=String(error?.message||'').toLowerCase();
  return status===429||message.includes('neuron')||message.includes('quota')||message.includes('rate limit');
}

// Preserve only bounded diagnostic fields needed to identify a hosted-model schema/runtime
// failure. Credential-shaped content is removed before this object can reach logs/API output.
export function sanitizeWorkersAiError(error){
  const status=Number(error?.status||0);
  const code=error?.code===undefined||error?.code===null?'':String(error.code).slice(0,64);
  let message=String(error?.message||error||'').replace(/[\r\n\t]+/g,' ').trim();
  message=message
    .replace(/(authorization\s*:\s*bearer\s+)[^\s,;]+/gi,'$1[REDACTED]')
    .replace(/(bearer\s+)[A-Za-z0-9._~+\/-]+/gi,'$1[REDACTED]')
    .replace(/((?:api[-_ ]?key|token|secret|password)\s*[:=]\s*)[^\s,;]+/gi,'$1[REDACTED]');
  // Long enough to keep the part that names the cause. Truncating at 240 cut every hosted
  // pipeline error off exactly where it was about to say what was wrong.
  if(message.length>1000)message=`${message.slice(0,997)}...`;
  return {
    ...(Number.isFinite(status)&&status>0?{status}:{}),
    ...(code?{code}:{}),
    ...(message?{message}:{}),
  };
}

export async function workersAiHealth(env={}){
  const ai=binding(env);
  if(!ai)return {ok:false,provider:'cloudflare_workers_ai',error:'workers_ai_binding_unavailable'};
  return {ok:true,provider:'cloudflare_workers_ai',mode:'FREE_ONLY',paidFallback:false,autoPurchase:false};
}

export function createWorkersAiClient(){
  return {
    async generate(env,{taskType,prompt,image,mask,width,height,negativePrompt,strength,seed,steps,models}={}){
      const ai=binding(env);
      if(!ai)return {ok:false,provider:'cloudflare_workers_ai',error:'workers_ai_binding_unavailable'};
      const task=String(taskType||'');
      const chain=(Array.isArray(models)&&models.length?models.map(String):workersAiModelChain(task)).filter(model=>MODEL_INPUT_SCHEMA[model]);
      if(!chain.length)return {ok:false,provider:'cloudflare_workers_ai',error:'task_not_supported'};
      if(!String(prompt||'').trim())return {ok:false,provider:'cloudflare_workers_ai',error:'prompt_required'};
      if(SOURCE_IMAGE_TASKS.has(task)&&!image)return {ok:false,provider:'cloudflare_workers_ai',error:'source_image_required'};
      if(MASK_TASKS.has(task)&&!mask)return {ok:false,provider:'cloudflare_workers_ai',error:'mask_required'};

      // Each candidate is tried in turn and every rejection is kept. A model withdrawn or
      // failing on this account must not read as "the free runtime is gone", and an
      // exhausted free allocation stops the walk immediately: the next model would only
      // spend an allocation that is already gone.
      const attempted=[];
      for(const model of chain){
        // The inpainting model always needs a mask. A whole-image edit has none to give,
        // so one that leaves the whole frame editable is generated: that is precisely what
        // makes inpainting stand in for image-to-image.
        const effectiveMask=model===WORKERS_AI_MODELS.inpainting&&!mask
          ?Array.from(fullyEditableMask(width||512,height||512))
          :mask;
        const input=buildInput(model,{prompt,image,mask:effectiveMask,width,height,negativePrompt,strength,seed,steps});
        try{
          const output=await ai.run(model,input);
          return {ok:true,provider:'cloudflare_workers_ai',model,mode:'FREE_ONLY',paidFallback:false,output,attempted};
        }catch(error){
          const diagnostic=sanitizeWorkersAiError(error);
          attempted.push({model,error:isAllocationExhausted(error)?'free_allocation_exhausted':'provider_request_failed',diagnostic});
          if(isAllocationExhausted(error)){
            return {ok:false,provider:'cloudflare_workers_ai',model,error:'free_allocation_exhausted',paidFallback:false,waitState:'WAITING_FOR_FREE_COMPUTE',diagnostic,attempted};
          }
        }
      }
      const last=attempted[attempted.length-1]||{};
      return {ok:false,provider:'cloudflare_workers_ai',model:chain[0],error:'provider_request_failed',paidFallback:false,diagnostic:last.diagnostic,attempted};
    },
  };
}
