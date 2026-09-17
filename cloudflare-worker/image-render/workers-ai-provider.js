// Executable Cloudflare Workers AI provider.
//
// The mesh has always been able to *describe* Workers AI as the reference-safe free
// runtime; without this adapter nothing could actually run there, so every reference,
// edit and inpaint route had no execution path at all. This is that path.
//
// It is synchronous: the Worker's own AI binding returns the image on the same call, so
// there is no provider-side job to poll. Submissions report `synchronous:true` and carry
// the generation with them.
import {createWorkersAiClient,readWorkersAiImageBytes,workersAiModelChain,WORKERS_AI_MODELS} from './workers-ai.js';

const PROVIDER_ID='cloudflare_workers_ai';

// Reference and source assets may arrive as base64 or as raw byte arrays. Anything else
// is not an image this runtime can be given, and is reported as missing rather than
// silently dropped -- dropping it is what turns an edit into a prompt-only render.
export function assetBytes(asset){
  if(!asset||typeof asset!=='object')return null;
  if(Array.isArray(asset.bytes)&&asset.bytes.length)return asset.bytes.map(Number);
  if(asset.bytes instanceof Uint8Array&&asset.bytes.length)return Array.from(asset.bytes);
  const b64=typeof asset.imageB64==='string'?asset.imageB64:typeof asset.b64==='string'?asset.b64:null;
  if(!b64)return null;
  try{return Array.from(Uint8Array.from(atob(b64),char=>char.charCodeAt(0)));}catch{return null;}
}

// The image the provider edits from. A caller that named a source image gets that one;
// otherwise the first reference asset is the source, which is what the compiled intent
// already records.
export function sourceBytesFor(scene){
  return assetBytes(scene?.source_image)??assetBytes((scene?.reference_assets||[])[0]);
}

export function maskBytesFor(scene){return assetBytes(scene?.mask);}

const PNG=[0x89,0x50,0x4e,0x47];
function contentTypeOf(bytes){
  if(!bytes||bytes.length<4)return 'image/png';
  if(PNG.every((byte,index)=>bytes[index]===byte))return 'image/png';
  if(bytes[0]===0xff&&bytes[1]===0xd8)return 'image/jpeg';
  return 'image/png';
}

export function createWorkersAiProvider({env={},client=createWorkersAiClient()}={}){
  return {
    id:PROVIDER_ID,
    mode:'FREE_ONLY',
    monetaryCost:'zero',
    paidFallback:false,
    autoPurchase:false,
    // Same vendor as the Worker itself, which is what makes it reference-safe where the
    // volunteer provider is not.
    privacyClasses:['PUBLIC','INTERNAL','CONFIDENTIAL'],
    referenceSafe:true,
    synchronous:true,

    async listModels(){
      return {ok:true,provider:PROVIDER_ID,models:Object.values(WORKERS_AI_MODELS).map(name=>({name,workerCount:1,performance:0,eta:0,queued:0}))};
    },

    async submit(input={}){
      const scene=input.scene||{};
      const taskType=String(input.taskType||scene.task_type||'TEXT_TO_IMAGE');
      const image=sourceBytesFor(scene);
      const mask=maskBytesFor(scene);
      const taskChain=workersAiModelChain(taskType);
      // A routed model is a preference, never an override of what the task needs: a model
      // that cannot do this task is dropped rather than run. Routing names the provider;
      // only the provider knows which of its models can edit an image.
      const requested=(Array.isArray(input.models)?input.models.filter(Boolean).map(String):[]).filter(model=>taskChain.includes(model));
      // Whatever survives, the rest of the task's chain still backs it up, so one withdrawn
      // hosted model cannot take the capability down.
      const chain=[...new Set([...requested,...taskChain])];
      const result=await client.generate(env,{
        taskType,
        prompt:input.prompt,
        negativePrompt:input.negativePrompt,
        width:Number(input.width)||undefined,
        height:Number(input.height)||undefined,
        steps:input.steps,
        strength:Number.isFinite(Number(input.strength))?Number(input.strength):undefined,
        seed:Number.isFinite(Number(input.seed))?Number(input.seed):undefined,
        image,
        mask,
        models:chain,
      });
      if(!result?.ok){
        return {ok:false,provider:PROVIDER_ID,error:result?.error||'provider_request_failed',waitState:result?.waitState??null,diagnostic:result?.diagnostic??null,attempted:result?.attempted||[],paidFallback:false};
      }
      const bytes=await readWorkersAiImageBytes(result.output);
      if(!bytes||bytes.length===0){
        return {ok:false,provider:PROVIDER_ID,model:result.model,error:'provider_generation_missing',paidFallback:false};
      }
      return {
        ok:true,
        provider:PROVIDER_ID,
        // Synchronous runtimes have no provider-side job to poll, so the id only has to
        // identify this attempt in our own records.
        jobId:`wai-${String(input.sceneId||'scene')}-${Number(input.attempt||1)}`,
        synchronous:true,
        model:result.model,
        generation:{
          imageUrl:null,
          model:result.model,
          state:'ok',
          seed:input.seed??null,
          censored:false,
          bytes:Array.from(bytes),
          contentType:contentTypeOf(bytes),
        },
      };
    },

    // Nothing runs on the provider between calls, so there is nothing to check or cancel.
    async check(){return {ok:true,provider:PROVIDER_ID,done:true,waitTime:0};},
    async status(){return {ok:false,provider:PROVIDER_ID,error:'workers_ai_results_are_returned_on_submit',generations:[]};},
    async cancel(){return {ok:true,provider:PROVIDER_ID,cancelled:true};},
  };
}
