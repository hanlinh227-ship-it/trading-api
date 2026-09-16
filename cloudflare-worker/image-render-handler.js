import {timingSafeToken} from './model-mesh/auth.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';
import {aiHordeHealth,cancelAiHordeImage,checkAiHordeImage,resolveAiHordeKey,statusAiHordeImage,submitAiHordeImage} from './image-render/ai-horde.js';
import {validateImageBatchRequest,createRenderManifest} from './image-render/render-manifest.js';
import {createImageBatch,getImageBatchStatus,cancelImageBatch,retryImageBatchScenes} from './image-render/batch-client.js';
import {createImageProviderRegistry} from './image-render/provider-registry.js';
import {rankImageModels} from './image-render/model-router.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const enabled=env=>String(env?.IMAGE_RENDER_EXECUTION_ENABLED||'0')==='1';
const configuredToken=env=>String(env?.IMAGE_RENDER_EXECUTION_TOKEN||env?.MODEL_MESH_EXECUTION_TOKEN||'');
const suppliedToken=request=>String(request.headers.get('x-image-render-token')||request.headers.get('x-model-mesh-token')||'');

async function authorize(request,env){const expected=configuredToken(env);if(!expected)return false;return timingSafeToken(expected,suppliedToken(request));}
async function responseJson(response){try{return await response.json();}catch{return {ok:false,error:'batch_response_invalid'};}}
async function proxyBatch(response){const body=await responseJson(response);return json({...body,mode:'FREE_ONLY',paidFallback:false},response.status);}
const batchIdFrom=url=>String(url.searchParams.get('id')||'').trim();

export function createImageRenderHandler({fetchImpl=fetch}={}){
  const registry=createImageProviderRegistry({fetchImpl});
  return async function handleImageRender(request,env={}){
    const url=new URL(request.url);
    if(!url.pathname.startsWith('/brain/image/'))return null;

    if(url.pathname==='/brain/image/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const provider=await aiHordeHealth({fetchImpl});
      return json({ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,executionEnabled:enabled(env),executionTokenConfigured:Boolean(configuredToken(env)),provider:{id:'ai_horde',reachable:provider.ok,status:provider.status,anonymousAccess:true,monetaryCost:'zero',queuePriority:'lowest_when_anonymous'},privacy:{allowedDataClasses:['PUBLIC'],explicitDataClassRequired:true,nonPublicAction:'fail_closed',referenceImagesEnabled:false,anonymousRequestsMayBeSharedByProvider:true},batch:{enabled:Boolean(env?.IMAGE_RENDER_BATCH),maxScenes:100,defaultConcurrency:4,maxConcurrency:8,maxAttemptsPerScene:3},quality:{strictVisualVerificationRequired:true,metadataOnlyMayReportVerified:false},paidFallback:false,externalAvailabilityGuarantee:false});
    }

    if(!enabled(env))return json({ok:false,error:'image_render_execution_disabled'},503);
    if(!await authorize(request,env))return json({ok:false,error:'unauthorized'},401);
    const apiKey=resolveAiHordeKey(env);

    if(url.pathname==='/brain/image/batch/status'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const batchId=batchIdFrom(url);if(!batchId)return json({ok:false,error:'batch_id_required'},400);
      return proxyBatch(await getImageBatchStatus(env,batchId));
    }

    if(url.pathname==='/brain/image/batch'){
      if(request.method==='DELETE'){
        const batchId=batchIdFrom(url);if(!batchId)return json({ok:false,error:'batch_id_required'},400);
        return proxyBatch(await cancelImageBatch(env,batchId));
      }
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      const validation=validateImageBatchRequest(body);if(!validation.ok)return json({ok:false,error:validation.error},validation.status);
      if(validation.request.scenes.some(scene=>String(scene.prompt||'').length>12000||String(scene.negativePrompt||'').length>6000))return json({ok:false,error:'prompt_too_large'},413);
      const batchId=`img-${crypto.randomUUID()}`;
      const manifest=createRenderManifest(validation.request,{batchId,createdAt:new Date().toISOString()});
      const created=await createImageBatch(env,{batchId,manifest});const createdBody=await responseJson(created);
      if(!created.ok)return json({...createdBody,mode:'FREE_ONLY',paidFallback:false},created.status);
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,dataClass:'PUBLIC',batchId,sceneCount:manifest.scenes.length,status:'queued',statusUrl:`/brain/image/batch/status?id=${encodeURIComponent(batchId)}`},202);
    }

    if(url.pathname==='/brain/image/retry'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      const batchId=String(body?.batchId||'').trim();if(!batchId)return json({ok:false,error:'batch_id_required'},400);
      if(!Array.isArray(body?.sceneIds)||!body.sceneIds.length)return json({ok:false,error:'scene_ids_required'},400);
      return proxyBatch(await retryImageBatchScenes(env,{batchId,sceneIds:body.sceneIds}));
    }

    if(url.pathname==='/brain/image/models'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const provider=registry.get('ai_horde',env);if(!provider)return json({ok:false,error:'image_provider_unavailable'},503);
      const listed=await provider.listModels();if(!listed?.ok)return json({ok:false,error:listed?.error||'provider_model_list_failed',provider:'ai_horde'},502);
      const models=rankImageModels({models:listed.models,limit:8});
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,provider:'ai_horde',models});
    }

    if(url.pathname==='/brain/image/render'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      if(body?.dataClass===undefined||body?.dataClass===null||String(body.dataClass).trim()==='')return json({ok:false,error:'data_class_required'},400);
      const dataClass=sanitizeDataClass(body.dataClass);if(dataClass!=='PUBLIC')return json({ok:false,error:'ai_horde_public_data_only',dataClass},403);
      if(typeof body?.prompt!=='string'||!body.prompt.trim())return json({ok:false,error:'invalid_prompt'},400);
      if(body.prompt.length>12000||String(body?.negativePrompt||'').length>6000)return json({ok:false,error:'prompt_too_large'},413);
      if(body?.referenceImages!==undefined||body?.sourceImage!==undefined)return json({ok:false,error:'reference_images_not_enabled_for_volunteer_provider'},409);
      const result=await submitAiHordeImage({prompt:body.prompt,negativePrompt:body.negativePrompt,width:body.width,height:body.height,steps:body.steps,n:body.n,seed:body.seed,models:body.models,apiKey,fetchImpl});
      if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,dataClass,provider:'ai_horde',jobId:result.jobId,kudos:result.kudos,anonymous:result.anonymous,anonymousRequestsMayBeSharedByProvider:result.anonymous,request:result.request,statusUrl:`/brain/image/status?id=${encodeURIComponent(result.jobId)}`},202);
    }

    if(url.pathname==='/brain/image/check'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const result=await checkAiHordeImage({jobId:url.searchParams.get('id'),apiKey,fetchImpl});if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);return json({...result,mode:'FREE_ONLY',paidFallback:false});
    }

    if(url.pathname==='/brain/image/status'){
      if(request.method==='DELETE'){const result=await cancelAiHordeImage({jobId:url.searchParams.get('id'),apiKey,fetchImpl});if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);return json({...result,mode:'FREE_ONLY',paidFallback:false});}
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const result=await statusAiHordeImage({jobId:url.searchParams.get('id'),apiKey,fetchImpl});if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);return json({...result,mode:'FREE_ONLY',paidFallback:false});
    }

    return json({ok:false,error:'image_render_endpoint_not_found'},404);
  };
}

export const handleImageRender=createImageRenderHandler();
