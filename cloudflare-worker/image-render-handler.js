import {timingSafeToken} from './model-mesh/auth.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';
import {aiHordeHealth,cancelAiHordeImage,checkAiHordeImage,resolveAiHordeKey,statusAiHordeImage,submitAiHordeImage} from './image-render/ai-horde.js';
import {
  IMAGE_BATCH_DEFAULT_CONCURRENCY,
  IMAGE_BATCH_MAX_ATTEMPTS,
  IMAGE_BATCH_MAX_CONCURRENCY,
  IMAGE_BATCH_MAX_SCENES,
  createRenderManifest,
  validateImageBatchRequest,
} from './image-render/render-manifest.js';
import {compileScenePrompt} from './image-render/prompt-compiler.js';
import {createImageProviderRegistry} from './image-render/provider-registry.js';
import {rankImageModels} from './image-render/model-router.js';
import {cancelImageBatch,createImageBatch,getImageBatchStatus,retryImageBatchScenes} from './image-render/batch-client.js';
import {buildExportManifest,buildRenderReport} from './image-render/export-contract.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const enabled=env=>String(env?.IMAGE_RENDER_EXECUTION_ENABLED||'0')==='1';
const configuredToken=env=>String(env?.IMAGE_RENDER_EXECUTION_TOKEN||env?.MODEL_MESH_EXECUTION_TOKEN||'');
const suppliedToken=request=>String(request.headers.get('x-image-render-token')||request.headers.get('x-model-mesh-token')||'');

async function authorize(request,env){
  const expected=configuredToken(env);
  if(!expected)return false;
  return timingSafeToken(expected,suppliedToken(request));
}

function batchErrorResponse(error){
  const message=String(error?.message||error||'image_render_batch_error');
  if(message==='image_render_batch_binding_unavailable')return json({ok:false,error:message},503);
  if(message==='image_render_batch_id_required')return json({ok:false,error:message},400);
  return json({ok:false,error:'image_render_batch_error'},502);
}

function compileManifest(manifest){
  manifest.scenes=manifest.scenes.map(scene=>{
    const compiled=compileScenePrompt(scene,manifest);
    return {...scene,compiled_prompt:compiled.prompt,negative_prompt:compiled.negativePrompt,prompt_locks:compiled.locks};
  });
  return manifest;
}

function withExportMetadata(result){
  if(!result?.ok||!result?.state||!Array.isArray(result.state.scenes))return result;
  const exportManifest=buildExportManifest(result.state);
  const renderReport=buildRenderReport(result.state);
  return exportManifest.assets.length?{...result,renderReport,exportManifest}:{...result,renderReport};
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

    if(url.pathname==='/brain/image/models'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const registry=createImageProviderRegistry({fetchImpl});
      const provider=registry.get('ai_horde',env);
      const result=await provider.listModels();
      if(!result.ok)return json({ok:false,error:result.error||'provider_rejected',provider:'ai_horde',providerStatus:result.status},result.status>=400&&result.status<600?result.status:502);
      const preferred=url.searchParams.getAll('preferred').map(value=>String(value).trim()).filter(Boolean);
      const models=rankImageModels({models:result.models||[],preferredModels:preferred,limit:8});
      return json({ok:true,mode:'FREE_ONLY',paidFallback:false,provider:'ai_horde',models});
    }

    if(url.pathname==='/brain/image/batch'){
      if(request.method==='POST'){
        let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        const checked=validateImageBatchRequest(body);
        if(!checked.ok)return json({ok:false,error:checked.error},checked.status);
        const batchId=`img-${crypto.randomUUID()}`;
        let manifest=compileManifest(createRenderManifest(checked.request,{batchId}));
        manifest.preferred_models=Array.isArray(checked.request.preferredModels)?checked.request.preferredModels.map(String).filter(Boolean):[];
        try{
          const created=await createImageBatch(env,batchId,manifest);
          if(!created.ok)return json({ok:false,error:created.error||'image_render_batch_create_failed'},created.status||502);
          return json({
            ok:true,
            mode:'FREE_ONLY',
            paidFallback:false,
            dataClass:'PUBLIC',
            provider:'ai_horde',
            batchId,
            sceneCount:manifest.scenes.length,
            statusUrl:`/brain/image/batch/status?id=${encodeURIComponent(batchId)}`,
            summary:created.summary||null,
          },202);
        }catch(error){return batchErrorResponse(error);}
      }
      if(request.method==='DELETE'){
        const batchId=String(url.searchParams.get('id')||'').trim();
        if(!batchId)return json({ok:false,error:'image_render_batch_id_required'},400);
        try{return json(await cancelImageBatch(env,batchId));}catch(error){return batchErrorResponse(error);}
      }
      return json({ok:false,error:'method_not_allowed'},405);
    }

    if(url.pathname==='/brain/image/batch/status'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const batchId=String(url.searchParams.get('id')||'').trim();
      if(!batchId)return json({ok:false,error:'image_render_batch_id_required'},400);
      try{
        const result=withExportMetadata(await getImageBatchStatus(env,batchId));
        return json(result,result.status&&result.status>=400?result.status:200);
      }catch(error){return batchErrorResponse(error);}
    }

    if(url.pathname==='/brain/image/retry'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      const batchId=String(body?.batchId||'').trim();
      if(!batchId)return json({ok:false,error:'image_render_batch_id_required'},400);
      const sceneIds=Array.isArray(body?.sceneIds)?body.sceneIds.map(String).filter(Boolean):[];
      if(!sceneIds.length)return json({ok:false,error:'image_render_retry_scene_ids_required'},400);
      try{
        const result=await retryImageBatchScenes(env,batchId,sceneIds);
        return json(result,result.status&&result.status>=400?result.status:200);
      }catch(error){return batchErrorResponse(error);}
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
