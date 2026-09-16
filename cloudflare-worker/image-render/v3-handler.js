import {compileImageIntent,IMAGE_INTENT_TASKS,validateImageIntent} from './image-intent.js';
import {createImageProviderMesh} from './provider-mesh.js';
import {loadApprovedModelVault} from './model-vault.js';
import {getProviderAdapter,listProviderAdapters} from './provider-adapter-registry.js';
import {describeProviderAdapter} from './provider-adapter.js';
import {evaluateActivation} from './activation.js';
import {BENCHMARK_SUITES} from './benchmark-suite.js';
import {visualCriticAvailability} from './critic-runtime.js';
import {workersAiHealth} from './workers-ai.js';
import {cancelImageLogicalJob,createImageLogicalJob,getImageLogicalJobStatus,retryImageLogicalJobScenes} from './logical-job-client.js';

// Tasks that can only run on a runtime allowed to receive the reference/source image.
const REFERENCE_SAFE_TASKS=new Set(['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','STYLE_TRANSFER','TARGETED_REPAIR']);

// A supported intent is not an executable capability: a task is only AVAILABLE when a
// registered FREE provider can actually run it today, and reference work that has no
// reference-safe free runtime waits rather than being reported as live.
function taskAvailability(registrations=[]){
  const availability={};
  for(const task of IMAGE_INTENT_TASKS){
    const needsReferenceSafe=REFERENCE_SAFE_TASKS.has(task);
    const eligible=registrations.some(registration=>
      Array.isArray(registration.supportedTasks)&&registration.supportedTasks.includes(task)
      &&registration.monetaryCost==='zero'
      &&registration.paidFallback===false
      &&registration.autoPurchase===false
      &&(!needsReferenceSafe||registration.referenceSafe===true));
    availability[task]=eligible?'AVAILABLE':(needsReferenceSafe?'WAITING_FOR_SAFE_FREE_RUNTIME':'WAITING_FOR_FREE_COMPUTE');
  }
  return availability;
}

function vaultSummary(entries=[]){
  const summary={CANDIDATE:0,BENCHMARKED:0,ACTIVE:0,DEGRADED:0,DISABLED:0};
  for(const entry of entries){
    // A model is only counted ACTIVE when its runtime is actually configured.
    const status=entry.approvalStatus==='ACTIVE'&&entry.runtimeConfigured!==true?'BENCHMARKED':entry.approvalStatus;
    if(summary[status]!==undefined)summary[status]+=1;
  }
  return summary;
}

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

async function createJobResponse(env,scenes,chunkSize=100){
  const jobId=`imgjob-${crypto.randomUUID()}`;
  try{
    const created=await createImageLogicalJob(env,jobId,scenes,{chunkSize});
    if(!created.ok)return json({ok:false,error:created.error||'image_logical_job_create_failed'},created.status||502);
    return json({ok:true,mode:'FREE_ONLY',paidFallback:false,jobId,sceneCount:scenes.length,statusUrl:`/brain/image/v3/jobs/status?id=${encodeURIComponent(jobId)}`,summary:created.summary||null},202);
  }catch(error){return clientError(error);}
}

export async function handleImageRenderV3Authorized(request,env={}){
  const url=new URL(request.url);
  if(!url.pathname.startsWith('/brain/image/v3/'))return null;

  if(url.pathname==='/brain/image/v3/capabilities'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const registrations=createImageProviderMesh({env}).listRegistrations();
    const availability=taskAvailability(registrations);
    const critic=await visualCriticAvailability(env);
    const inference=await workersAiHealth(env);
    const referenceSafeRuntime=Object.entries(availability).some(([task,state])=>REFERENCE_SAFE_TASKS.has(task)&&state==='AVAILABLE')?'AVAILABLE':'WAITING_FOR_SAFE_FREE_RUNTIME';
    return json({
      ok:true,
      contractVersion:'image_render_v3',
      mode:'FREE_ONLY',
      paidFallback:false,
      autoPurchase:false,
      cloudOnly:true,
      localRuntimeRequired:false,
      logicalJobs:{enabled:Boolean(env?.IMAGE_LOGICAL_JOB),physicalChunkMaxScenes:100},
      tasks:[...IMAGE_INTENT_TASKS],
      taskAvailability:availability,
      referenceSafeRuntime,
      // STRICT_VISUAL is only ever verified when a real critic runtime answered. With no
      // critic the quality layer reports complete_unverified; nothing metadata-only passes.
      visualCriticRuntime:critic.available?'AVAILABLE':'UNAVAILABLE',
      visualCriticProvider:critic.provider,
      visualCriticModel:critic.model,
      inferenceRuntime:inference.ok?'AVAILABLE':'UNAVAILABLE',
      modelVault:vaultSummary(loadApprovedModelVault()),
      privacy:{aiHordePublicOnly:true,referenceSafeRequired:true},
      quality:{strictVisualRequiresRealCritic:true,missingVisualCriticAction:'complete_unverified'},
    });
  }

  if(url.pathname==='/brain/image/v3/activation'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const adapters=listProviderAdapters();
    const summary={CANDIDATE:0,RUNTIME_DISCOVERED:0,HEALTH_VERIFIED:0,LICENSE_VERIFIED:0,PRIVACY_VERIFIED:0,BENCHMARKED:0,ACTIVE:0,DEGRADED:0,DISABLED:0};
    const blockerCounts={};
    const models=loadApprovedModelVault().map(model=>{
      const tasks=(model.supportedTasks||[]).map(taskType=>{
        // A model is evaluated against a provider that actually declares the task; with no
        // such provider it stops at the first gate rather than being assumed runnable.
        const adapter=adapters.find(item=>(model.runtimeProviders||[]).includes(item.id)&&item.supportedTasks.includes(taskType))
          ||getProviderAdapter((model.runtimeProviders||[])[0])
          ||adapters[0];
        const evaluation=evaluateActivation({model,adapter,taskType,evidence:model.activationEvidence?.[taskType]||{}});
        if(summary[evaluation.status]!==undefined)summary[evaluation.status]+=1;
        for(const blocker of evaluation.blockers)blockerCounts[blocker]=(blockerCounts[blocker]||0)+1;
        return {taskType,status:evaluation.status,stage:evaluation.stage,blockers:evaluation.blockers,evidenceTrail:evaluation.evidenceTrail};
      });
      return {modelId:model.modelId,family:model.family,version:model.version,status:model.status,runtimeProviders:[...(model.runtimeProviders||[])],referenceSupport:model.referenceSupport===true,editSupport:model.editSupport===true,criticSupport:model.criticSupport===true,tasks};
    });
    const nextBottleneck=Object.entries(blockerCounts).sort((a,b)=>b[1]-a[1])[0]?.[0]||null;
    return json({
      ok:true,
      contractVersion:'image_render_v3',
      mode:'FREE_ONLY',
      paidFallback:false,
      autoPurchase:false,
      providers:adapters.map(describeProviderAdapter),
      models,
      summary,
      nextBottleneck,
      benchmarkSuites:Object.values(BENCHMARK_SUITES).map(suite=>({taskType:suite.taskType,purpose:suite.purpose,dimensions:suite.dimensions.map(d=>d.id)})),
    });
  }

  if(url.pathname==='/brain/image/v3/models'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const mesh=createImageProviderMesh({env});
    return json({ok:true,mode:'FREE_ONLY',paidFallback:false,vault:loadApprovedModelVault(),providerRegistrations:mesh.listRegistrations()});
  }

  if(url.pathname==='/brain/image/v3/edit'){
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
    let scenes;try{scenes=normalizeScenes([{id:body?.sceneId||'edit-1',intent:{...body,taskType:body?.taskType||'IMAGE_EDIT_LOCAL'}}]);}catch(error){return json({ok:false,error:String(error?.message||error)},400);}
    return createJobResponse(env,scenes,1);
  }

  if(url.pathname==='/brain/image/v3/jobs'){
    if(request.method==='POST'){
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      let scenes;try{scenes=normalizeScenes(body?.scenes);}catch(error){return json({ok:false,error:String(error?.message||error)},400);}
      return createJobResponse(env,scenes,body?.chunkSize??100);
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
