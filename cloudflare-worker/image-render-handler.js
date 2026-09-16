import {timingSafeToken} from './model-mesh/auth.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';
import {aiHordeHealth,cancelAiHordeImage,checkAiHordeImage,listAiHordeModels,resolveAiHordeKey,statusAiHordeImage,submitAiHordeImage} from './image-render/ai-horde.js';
import {validateImageBatchRequest,createRenderManifest,IMAGE_BATCH_MAX_SCENES,IMAGE_BATCH_DEFAULT_CONCURRENCY,IMAGE_BATCH_MAX_CONCURRENCY,IMAGE_BATCH_MAX_ATTEMPTS} from './image-render/render-manifest.js';
import {compileScenePrompt} from './image-render/prompt-compiler.js';
import {rankImageModels} from './image-render/model-router.js';
import {createImageBatch,getImageBatchStatus,cancelImageBatch,retryImageBatchScenes} from './image-render/batch-client.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const enabled=env=>String(env?.IMAGE_RENDER_EXECUTION_ENABLED||'0')==='1';
const configuredToken=env=>String(env?.IMAGE_RENDER_EXECUTION_TOKEN||env?.MODEL_MESH_EXECUTION_TOKEN||'');
const suppliedToken=request=>String(request.headers.get('x-image-render-token')||request.headers.get('x-model-mesh-token')||'');

async function authorize(request,env){
  const expected=configuredToken(env);
  if(!expected)return false;
  return timingSafeToken(expected,suppliedToken(request));
}

function batchClientFailure(error){
  const message=String(error?.message||'image_render_batch_request_failed');
  const status=Number(error?.status||0);
  if(message==='image_render_batch_binding_unavailable')return json({ok:false,error:message},503);
  return json({ok:false,error:message},status>=400&&status<600?status:502);
}

function compileManifestScenes(manifest){
  manifest.scenes=manifest.scenes.map(scene=>{
    const compiled=compileScenePrompt(scene,manifest);
    return {...scene,compiled_prompt:compiled.prompt,negative_prompt:compiled.negativePrompt,continuity_locks:compiled.locks};
  });
  return manifest;
}

export function createImageRenderHandler({fetchImpl=fetch}={}){
  return async function handleImageRender(request,env={}){
    const url=new URL(request.url);
    if(!url.pathname.startsWith('/brain/image/'))return null;

    if(url.pathname==='/brain/image/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const provider=await aiHordeHealth({fetchImpl});
      return json({
        ok:true,
        mode:'FREE_ONLY',
        routingAuthority:false,
        reasoningAuthority:false,
        executionEnabled:enabled(env),
        executionTokenConfigured:Boolean(configuredToken(env)),
        provider:{id:'ai_horde',reachable:provider.ok,status:provider.status,anonymousAccess:true,monetaryCost:'zero',queuePriority:'lowest_when_anonymous'},
        privacy:{allowedDataClasses:['PUBLIC'],explicitDataClassRequired:true,nonPublicAction:'fail_closed',referenceImagesEnabled:false,anonymousRequestsMayBeSharedByProvider:true},
        batch:{enabled:Boolean(env?.IMAGE_RENDER_BATCH),maxScenes:IMAGE_BATCH_MAX_SCENES,defaultConcurrency:IMAGE_BATCH_DEFAULT_CONCURRENCY,maxConcurrency:IMAGE_BATCH_MAX_CONCURRENCY,maxAttemptsPerScene:IMAGE_BATCH_MAX_ATTEMPTS},
        quality:{strictVisualVerificationRequired:true,metadataOnlyMayReportVerified:false},
        paidFallback:false,
        externalAvailabilityGuarantee:false,
      });
    }

    if(!enabled(env))return json({ok:false,error:'image_render_execution_disabled'},503);
    if(!await authorize(request,env))return json({ok:false,error:'unauthorized'},401);
    const apiKey=resolveAiHordeKey(env);

    if(url.pathname==='/brain/image/batch'){
      if(request.method==='DELETE'){
        const batchId=String(url.searchParams.get('id')||'').trim();
        if(!batchId)return json({ok:false,error:'batch_id_required'},400);
        try{
          const result=await cancelImageBatch(env,batchId);
          return json({...result,mode:'FREE_ONLY',paidFallback:false});
        }catch(error){return batchClientFailure(error);}
      }
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      const validated=validateImageBatchRequest(body);
      if(!validated.ok)return json({ok:false,error:validated.error},validated.status);
      const batchId=`img-${crypto.randomUUID()}`;
      let manifest=createRenderManifest(validated.request,{batchId,createdAt:new Date().toISOString()});
      manifest=compileManifestScenes(manifest);
      try{
        await createImageBatch(env,batchId,manifest);
      }catch(error){return batchClientFailure(error);}
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,batchId,sceneCount:manifest.scenes.length,statusUrl:`/brain/image/batch/status?id=${encodeURIComponent(batchId)}`},202);
    }

    if(url.pathname==='/brain/image/batch/status'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const batchId=String(url.searchParams.get('id')||'').trim();
      if(!batchId)return json({ok:false,error:'batch_id_required'},400);
      try{
        const result=await getImageBatchStatus(env,batchId);
        return json({...result,mode:'FREE_ONLY',paidFallback:false});
      }catch(error){return batchClientFailure(error);}
    }

    if(url.pathname==='/brain/image/retry'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      const batchId=String(body?.batchId||'').trim();
      if(!batchId)return json({ok:false,error:'batch_id_required'},400);
      if(!Array.isArray(body?.sceneIds)||!body.sceneIds.length)return json({ok:false,error:'scene_ids_required'},400);
      try{
        const result=await retryImageBatchScenes(env,batchId,body.sceneIds);
        return json({...result,mode:'FREE_ONLY',paidFallback:false});
      }catch(error){return batchClientFailure(error);}
    }

    if(url.pathname==='/brain/image/models'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const listed=await listAiHordeModels({fetchImpl});
      if(!listed.ok)return json({ok:false,error:listed.error||'provider_rejected',provider:'ai_horde',providerStatus:listed.status},listed.status>=400&&listed.status<600?listed.status:502);
      const preferred=url.searchParams.getAll('preferred');
      const models=rankImageModels({models:listed.models,preferredModels:preferred,limit:Math.min(8,listed.models.length||1)});
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,provider:'ai_horde',models});
    }

    if(url.pathname==='/brain/image/render'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      if(body?.dataClass===undefined||body?.dataClass===null||String(body.dataClass).trim()==='')return json({ok:false,error:'data_class_required'},400);
      const dataClass=sanitizeDataClass(body.dataClass);
      if(dataClass!=='PUBLIC')return json({ok:false,error:'ai_horde_public_data_only',dataClass},403);
      if(typeof body?.prompt!=='string'||!body.prompt.trim())return json({ok:false,error:'invalid_prompt'},400);
      if(body.prompt.length>12000||String(body?.negativePrompt||'').length>6000)return json({ok:false,error:'prompt_too_large'},413);
      if(body?.referenceImages!==undefined||body?.sourceImage!==undefined)return json({ok:false,error:'reference_images_not_enabled_for_volunteer_provider'},409);
      const result=await submitAiHordeImage({
        prompt:body.prompt,
        negativePrompt:body.negativePrompt,
        width:body.width,
        height:body.height,
        steps:body.steps,
        n:body.n,
        seed:body.seed,
        models:body.models,
        apiKey,
        fetchImpl,
      });
      if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,dataClass,provider:'ai_horde',jobId:result.jobId,kudos:result.kudos,anonymous:result.anonymous,anonymousRequestsMayBeSharedByProvider:result.anonymous,request:result.request,statusUrl:`/brain/image/status?id=${encodeURIComponent(result.jobId)}`},202);
    }

    if(url.pathname==='/brain/image/check'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const result=await checkAiHordeImage({jobId:url.searchParams.get('id'),apiKey,fetchImpl});
      if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);
      return json({...result,mode:'FREE_ONLY',paidFallback:false});
    }

    if(url.pathname==='/brain/image/status'){
      if(request.method==='DELETE'){
        const result=await cancelAiHordeImage({jobId:url.searchParams.get('id'),apiKey,fetchImpl});
        if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);
        return json({...result,mode:'FREE_ONLY',paidFallback:false});
      }
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const result=await statusAiHordeImage({jobId:url.searchParams.get('id'),apiKey,fetchImpl});
      if(!result.ok)return json({ok:false,error:result.error,provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);
      return json({...result,mode:'FREE_ONLY',paidFallback:false});
    }

    return json({ok:false,error:'image_render_endpoint_not_found'},404);
  };
}

export const handleImageRender=createImageRenderHandler();
