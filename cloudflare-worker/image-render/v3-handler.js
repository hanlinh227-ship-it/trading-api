import {compileImageIntent,validateImageIntent} from './image-intent.js';
import {createImageProviderMesh} from './provider-mesh.js';
import {loadApprovedModelVault} from './model-vault.js';
import {cancelImageLogicalJob,createImageLogicalJob,getImageLogicalJobStatus,retryImageLogicalJobScenes} from './logical-job-client.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

function clientError(error){
  const message=String(error?.message||error||'image_logical_job_error');
  if(message==='image_logical_job_binding_unavailable')return json({ok:false,error:message},503);
  if(message==='image_logical_job_id_required')return json({ok:false,error:message},400);
  return json({ok:false,error:'image_logical_job_error'},502);
}

function normalizeScenes(rawScenes=[]){
  if(!Array.isArray(rawScenes)||rawScenes.length===0)throw new Error('logical_job_scenes_required');
  return rawScenes.map((scene,index)=>{
    const rawIntent=scene?.intent||scene;
    const intent=compileImageIntent(rawIntent);
    const validation=validateImageIntent(intent);
    if(!validation.ok)throw new Error(validation.errors[0]||'invalid_image_intent');
    return {id:String(scene?.id||`scene-${index+1}`),intent};
  });
}

export async function handleImageRenderV3Authorized(request,env={}){
  const url=new URL(request.url);
  if(!url.pathname.startsWith('/brain/image/v3/'))return null;

  if(url.pathname==='/brain/image/v3/capabilities'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    return json({ok:true,contractVersion:'image_render_v3',mode:'FREE_ONLY',paidFallback:false,autoPurchase:false,cloudOnly:true,localRuntimeRequired:false,logicalJobs:{enabled:Boolean(env?.IMAGE_LOGICAL_JOB),physicalChunkMaxScenes:100},tasks:['TEXT_TO_IMAGE','REFERENCE_GENERATION','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','STYLE_TRANSFER','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','MULTI_SCENE_BATCH','TARGETED_REPAIR'],privacy:{aiHordePublicOnly:true,referenceSafeRequired:true},quality:{strictVisualRequiresRealCritic:true}});
  }

  if(url.pathname==='/brain/image/v3/models'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const mesh=createImageProviderMesh();
    return json({ok:true,mode:'FREE_ONLY',paidFallback:false,vault:loadApprovedModelVault(),providerRegistrations:mesh.listRegistrations()});
  }

  if(url.pathname==='/brain/image/v3/jobs'){
    if(request.method==='POST'){
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      let scenes;try{scenes=normalizeScenes(body?.scenes);}catch(error){return json({ok:false,error:String(error?.message||error)},400);}
      const jobId=`imgjob-${crypto.randomUUID()}`;
      try{
        const created=await createImageLogicalJob(env,jobId,scenes,{chunkSize:body?.chunkSize??100});
        if(!created.ok)return json({ok:false,error:created.error||'image_logical_job_create_failed'},created.status||502);
        return json({ok:true,mode:'FREE_ONLY',paidFallback:false,jobId,sceneCount:scenes.length,statusUrl:`/brain/image/v3/jobs/status?id=${encodeURIComponent(jobId)}`,summary:created.summary||null},202);
      }catch(error){return clientError(error);}
    }
    if(request.method==='DELETE'){
      const jobId=String(url.searchParams.get('id')||'').trim();
      if(!jobId)return json({ok:false,error:'image_logical_job_id_required'},400);
      try{return json(await cancelImageLogicalJob(env,jobId));}catch(error){return clientError(error);}
    }
    return json({ok:false,error:'method_not_allowed'},405);
  }

  if(url.pathname==='/brain/image/v3/jobs/status'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const jobId=String(url.searchParams.get('id')||'').trim();
    if(!jobId)return json({ok:false,error:'image_logical_job_id_required'},400);
    try{
      const result=await getImageLogicalJobStatus(env,jobId);
      return json(result,result.status&&result.status>=400?result.status:200);
    }catch(error){return clientError(error);}
  }

  if(url.pathname==='/brain/image/v3/jobs/retry'){
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
    const jobId=String(body?.jobId||'').trim();
    const sceneIds=Array.isArray(body?.sceneIds)?body.sceneIds.map(String).filter(Boolean):[];
    if(!jobId)return json({ok:false,error:'image_logical_job_id_required'},400);
    if(sceneIds.length===0)return json({ok:false,error:'image_logical_retry_scene_ids_required'},400);
    try{
      const result=await retryImageLogicalJobScenes(env,jobId,sceneIds);
      return json(result,result.status&&result.status>=400?result.status:200);
    }catch(error){return clientError(error);}
  }

  return json({ok:false,error:'image_render_v3_endpoint_not_found'},404);
}
