// Cloudflare Workers AI execution client. The Worker reaches these models through its own
// AI binding, so no credential is stored and no new third party sees the data.
// Model IDs are the verified Workers AI catalogue IDs; nothing here is inferred from a name.
export const WORKERS_AI_MODELS=Object.freeze({
  textToImage:'@cf/black-forest-labs/flux-1-schnell',
  imageToImage:'@cf/runwayml/stable-diffusion-v1-5-img2img',
  inpainting:'@cf/runwayml/stable-diffusion-v1-5-inpainting',
  vision:'@cf/llava-hf/llava-1.5-7b-hf',
  visionLarge:'@cf/meta/llama-3.2-11b-vision-instruct',
});

const TASK_MODEL=Object.freeze({
  TEXT_TO_IMAGE:WORKERS_AI_MODELS.textToImage,
  MULTI_SCENE_BATCH:WORKERS_AI_MODELS.textToImage,
  REFERENCE_GENERATION:WORKERS_AI_MODELS.imageToImage,
  IMAGE_EDIT_GLOBAL:WORKERS_AI_MODELS.imageToImage,
  STYLE_TRANSFER:WORKERS_AI_MODELS.imageToImage,
  BACKGROUND_REPLACE:WORKERS_AI_MODELS.inpainting,
  OBJECT_REPLACE:WORKERS_AI_MODELS.inpainting,
  IMAGE_EDIT_LOCAL:WORKERS_AI_MODELS.inpainting,
  INPAINT:WORKERS_AI_MODELS.inpainting,
  TARGETED_REPAIR:WORKERS_AI_MODELS.inpainting,
});

const NEEDS_SOURCE_IMAGE=new Set([WORKERS_AI_MODELS.imageToImage,WORKERS_AI_MODELS.inpainting]);
const NEEDS_MASK=new Set([WORKERS_AI_MODELS.inpainting]);

const MODEL_INPUT_SCHEMA=Object.freeze({
  [WORKERS_AI_MODELS.textToImage]:{accepts:new Set(['prompt','steps']),stepsMax:8,stepsDefault:4},
  [WORKERS_AI_MODELS.imageToImage]:{accepts:new Set(['prompt','negative_prompt','width','height','image','strength','seed','num_steps'])},
  [WORKERS_AI_MODELS.inpainting]:{accepts:new Set(['prompt','negative_prompt','width','height','image','mask','strength','seed','num_steps'])},
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
    candidate.num_steps=clampInt(steps,1,50);
  }
  return Object.fromEntries(Object.entries(candidate).filter(([key])=>schema.accepts.has(key)));
}

export function selectWorkersAiModel(taskType){return TASK_MODEL[String(taskType||'')]||null;}

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
  if(message.length>240)message=`${message.slice(0,237)}...`;
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
    async generate(env,{taskType,prompt,image,mask,width,height,negativePrompt,strength,seed,steps}={}){
      const ai=binding(env);
      if(!ai)return {ok:false,provider:'cloudflare_workers_ai',error:'workers_ai_binding_unavailable'};
      const model=selectWorkersAiModel(taskType);
      if(!model)return {ok:false,provider:'cloudflare_workers_ai',error:'task_not_supported'};
      if(!String(prompt||'').trim())return {ok:false,provider:'cloudflare_workers_ai',error:'prompt_required'};
      if(NEEDS_SOURCE_IMAGE.has(model)&&!image)return {ok:false,provider:'cloudflare_workers_ai',error:'source_image_required'};
      if(NEEDS_MASK.has(model)&&!mask)return {ok:false,provider:'cloudflare_workers_ai',error:'mask_required'};

      const input=buildInput(model,{prompt,image,mask,width,height,negativePrompt,strength,seed,steps});

      try{
        const output=await ai.run(model,input);
        return {ok:true,provider:'cloudflare_workers_ai',model,mode:'FREE_ONLY',paidFallback:false,output};
      }catch(error){
        const diagnostic=sanitizeWorkersAiError(error);
        if(isAllocationExhausted(error)){
          return {ok:false,provider:'cloudflare_workers_ai',model,error:'free_allocation_exhausted',paidFallback:false,waitState:'WAITING_FOR_FREE_COMPUTE',diagnostic};
        }
        return {ok:false,provider:'cloudflare_workers_ai',model,error:'provider_request_failed',paidFallback:false,diagnostic};
      }
    },
  };
}
