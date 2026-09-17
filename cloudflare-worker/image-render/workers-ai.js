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

// Tasks are routed to the model that actually accepts the inputs the task carries: a
// masked local edit needs the inpainting model, a whole-image edit needs img2img.
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

const NEEDS_SOURCE_IMAGE=new Set([
  WORKERS_AI_MODELS.imageToImage,
  WORKERS_AI_MODELS.inpainting,
]);
const NEEDS_MASK=new Set([WORKERS_AI_MODELS.inpainting]);

export function selectWorkersAiModel(taskType){
  return TASK_MODEL[String(taskType||'')]||null;
}

function binding(env){
  const ai=env?.AI;
  return ai&&typeof ai.run==='function'?ai:null;
}

// A 429 or an explicit quota error means the free daily allocation is spent. That is a
// wait state, never a reason to reach for a paid route.
function isAllocationExhausted(error){
  const status=Number(error?.status||error?.code||0);
  const message=String(error?.message||'').toLowerCase();
  return status===429||message.includes('neuron')||message.includes('quota')||message.includes('rate limit');
}

export async function workersAiHealth(env={}){
  const ai=binding(env);
  if(!ai)return {ok:false,provider:'cloudflare_workers_ai',error:'workers_ai_binding_unavailable'};
  return {ok:true,provider:'cloudflare_workers_ai',mode:'FREE_ONLY',paidFallback:false,autoPurchase:false};
}

export function createWorkersAiClient(){
  return {
    async generate(env,{taskType,prompt,image,mask,width,height,negativePrompt,strength,seed}={}){
      const ai=binding(env);
      if(!ai)return {ok:false,provider:'cloudflare_workers_ai',error:'workers_ai_binding_unavailable'};
      const model=selectWorkersAiModel(taskType);
      if(!model)return {ok:false,provider:'cloudflare_workers_ai',error:'task_not_supported'};
      if(!String(prompt||'').trim())return {ok:false,provider:'cloudflare_workers_ai',error:'prompt_required'};
      // Fail closed rather than quietly turning an edit into a prompt-only render.
      if(NEEDS_SOURCE_IMAGE.has(model)&&!image)return {ok:false,provider:'cloudflare_workers_ai',error:'source_image_required'};
      if(NEEDS_MASK.has(model)&&!mask)return {ok:false,provider:'cloudflare_workers_ai',error:'mask_required'};

      const input={prompt:String(prompt)};
      if(negativePrompt)input.negative_prompt=String(negativePrompt);
      if(Number.isInteger(width)&&width>0)input.width=width;
      if(Number.isInteger(height)&&height>0)input.height=height;
      if(image)input.image=image;
      if(mask)input.mask=mask;
      if(Number.isFinite(strength))input.strength=strength;
      if(Number.isInteger(seed))input.seed=seed;

      try{
        const output=await ai.run(model,input);
        return {ok:true,provider:'cloudflare_workers_ai',model,mode:'FREE_ONLY',paidFallback:false,output};
      }catch(error){
        if(isAllocationExhausted(error)){
          return {ok:false,provider:'cloudflare_workers_ai',model,error:'free_allocation_exhausted',paidFallback:false,waitState:'WAITING_FOR_FREE_COMPUTE'};
        }
        return {ok:false,provider:'cloudflare_workers_ai',model,error:'provider_request_failed',paidFallback:false};
      }
    },
  };
}
