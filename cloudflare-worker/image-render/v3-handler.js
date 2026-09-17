import {compileImageIntent,IMAGE_INTENT_TASKS,validateImageIntent} from './image-intent.js';
import {createImageProviderMesh} from './provider-mesh.js';
import {loadApprovedModelVault} from './model-vault.js';
import {getProviderAdapter,listProviderAdapters} from './provider-adapter-registry.js';
import {describeProviderAdapter} from './provider-adapter.js';
import {evaluateActivation} from './activation.js';
import {buildStaticActivationEvidence} from './activation-evidence.js';
import {BENCHMARK_SUITES} from './benchmark-suite.js';
import {visualCriticAvailability} from './critic-runtime.js';
import {workersAiHealth} from './workers-ai.js';
import {probeImageRuntimes} from './runtime-probe.js';
import {cancelImageLogicalJob,createImageLogicalJob,getImageLogicalJobStatus,retryImageLogicalJobScenes} from './logical-job-client.js';
import {getImageBatchAsset} from './batch-client.js';

const REFERENCE_SAFE_TASKS=new Set(['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','STYLE_TRANSFER','TARGETED_REPAIR']);

const PROBE_TASK_GROUP=Object.freeze({
  TEXT_TO_IMAGE:'TEXT_TO_IMAGE',
  MULTI_SCENE_BATCH:'TEXT_TO_IMAGE',
  REFERENCE_GENERATION:'REFERENCE_GENERATION',
  IMAGE_EDIT_GLOBAL:'REFERENCE_GENERATION',
  STYLE_TRANSFER:'REFERENCE_GENERATION',
  IMAGE_EDIT_LOCAL:'INPAINT',
  INPAINT:'INPAINT',
  BACKGROUND_REPLACE:'INPAINT',
  OBJECT_REPLACE:'INPAINT',
  TARGETED_REPAIR:'INPAINT',
});

const evidenceState=evidence=>{
  if(!evidence)return 'UNVERIFIED';
  if(evidence.ok===true)return 'AVAILABLE';
  if(evidence.waitState==='WAITING_FOR_FREE_COMPUTE')return 'WAITING_FOR_FREE_COMPUTE';
  return 'UNAVAILABLE';
};

function providerState(registration,probedByProvider,taskType=null){
  if(!probedByProvider)return 'UNVERIFIED';
  const probed=probedByProvider.get(registration.providerId);
  if(!probed)return 'UNVERIFIED';
  const probeKey=taskType?PROBE_TASK_GROUP[taskType]:null;
  if(probeKey&&probed.taskHealth&&Object.prototype.hasOwnProperty.call(probed.taskHealth,probeKey)){
    return evidenceState(probed.taskHealth[probeKey]);
  }
  return evidenceState(probed.health);
}

const requiresLocalBinding=registration=>registration.providerId==='cloudflare_workers_ai';

function taskAvailability(registrations=[],probedByProvider=null){
  const availability={};
  for(const task of IMAGE_INTENT_TASKS){
    const needsReferenceSafe=REFERENCE_SAFE_TASKS.has(task);
    const capable=registrations.filter(registration=>
      Array.isArray(registration.supportedTasks)&&registration.supportedTasks.includes(task)
      &&registration.monetaryCost==='zero'
      &&registration.paidFallback===false
      &&registration.autoPurchase===false
      &&(!needsReferenceSafe||registration.referenceSafe===true));
    const waiting=needsReferenceSafe?'WAITING_FOR_SAFE_FREE_RUNTIME':'WAITING_FOR_FREE_COMPUTE';
    if(capable.length===0){availability[task]=waiting;continue;}
    const states=capable.map(registration=>requiresLocalBinding(registration)?providerState(registration,probedByProvider,task):'AVAILABLE');
    if(states.includes('AVAILABLE'))availability[task]='AVAILABLE';
    else if(states.includes('UNVERIFIED'))availability[task]='UNVERIFIED';
    else if(states.includes('WAITING_FOR_FREE_COMPUTE'))availability[task]='WAITING_FOR_FREE_COMPUTE';
    else availability[task]=waiting;
  }
  return availability;
}

function vaultSummary(entries=[]){
  const summary={CANDIDATE:0,BENCHMARKED:0,ACTIVE:0,DEGRADED:0,DISABLED:0};
  for(const entry of entries){
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
    const capabilityProbe=url.searchParams.get('probe')==='1'?await probeImageRuntimes(env):null;
    const probedByProvider=capabilityProbe?new Map(capabilityProbe.providers.map(entry=>[entry.providerId,entry])):null;
    const availability=taskAvailability(registrations,probedByProvider);
    const critic=await visualCriticAvailability(env);
    const inference=await workersAiHealth(env);
    const workersRegistration=registrations.find(r=>r.providerId==='cloudflare_workers_ai')||null;
    const inferenceState=workersRegistration?providerState(workersRegistration,probedByProvider,'TEXT_TO_IMAGE'):'UNAVAILABLE';
    const workersProbe=probedByProvider?.get('cloudflare_workers_ai')||null;
    const criticState=capabilityProbe?evidenceState(workersProbe?.taskHealth?.VISUAL_CRITIC):'UNVERIFIED';
    const referenceStates=Object.entries(availability).filter(([task])=>REFERENCE_SAFE_TASKS.has(task)).map(([,state])=>state);
    const referenceSafeRuntime=referenceStates.includes('AVAILABLE')?'AVAILABLE'
      :referenceStates.includes('UNVERIFIED')?'UNVERIFIED'
      :referenceStates.includes('WAITING_FOR_FREE_COMPUTE')?'WAITING_FOR_FREE_COMPUTE'
      :'WAITING_FOR_SAFE_FREE_RUNTIME';
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
      visualCriticRuntime:critic.available?criticState:'UNAVAILABLE',
      visualCriticProvider:critic.provider,
      visualCriticModel:critic.model,
      inferenceRuntime:inference.ok?inferenceState:'UNAVAILABLE',
      runtimeVerifiedThisRequest:Boolean(capabilityProbe),
      modelVault:vaultSummary(loadApprovedModelVault()),
      privacy:{aiHordePublicOnly:true,referenceSafeRequired:true},
      quality:{strictVisualRequiresRealCritic:true,missingVisualCriticAction:'complete_unverified'},
    });
  }

  if(url.pathname==='/brain/image/v3/activation'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const adapters=listProviderAdapters();
    const probe=url.searchParams.get('probe')==='1'?await probeImageRuntimes(env):null;
    const probedEvidence=new Map((probe?.providers||[]).map(entry=>[entry.providerId,entry]));
    const summary={CANDIDATE:0,RUNTIME_DISCOVERED:0,HEALTH_VERIFIED:0,LICENSE_VERIFIED:0,PRIVACY_VERIFIED:0,BENCHMARKED:0,ACTIVE:0,DEGRADED:0,DISABLED:0};
    const blockerCounts={};
    const models=loadApprovedModelVault().map(model=>{
      const tasks=(model.supportedTasks||[]).map(taskType=>{
        const adapter=adapters.find(item=>(model.runtimeProviders||[]).includes(item.id)&&item.supportedTasks.includes(taskType))
          ||getProviderAdapter((model.runtimeProviders||[])[0])
          ||adapters[0];
        const staticEvidence=buildStaticActivationEvidence({model,adapter,taskType});
        const recorded=model.activationEvidence?.[taskType]||{};
        const probed=probedEvidence.get(adapter?.id);
        let health=probed?.health;
        if(probed?.taskHealth){
          const probeKey=model.criticSupport===true?'VISUAL_CRITIC':PROBE_TASK_GROUP[taskType];
          if(probeKey&&probed.taskHealth[probeKey])health=probed.taskHealth[probeKey];
        }
        const evidence={...staticEvidence,...recorded};
        if(probed){
          evidence.runtimeDiscovered=probed.runtimeDiscovered;
          evidence.health=health;
        }
        const evaluation=evaluateActivation({model,adapter,taskType,evidence});
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
      probe:probe?{at:probe.at,providers:probe.providers}:null,
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

  // Delivers the image a job produced. A synchronous free runtime returns bytes rather
  // than a hosted URL, so without this the caller would only ever see a status.
  if(url.pathname==='/brain/image/v3/assets'){
    if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
    const jobId=String(url.searchParams.get('job')||'').trim();
    const sceneId=String(url.searchParams.get('scene')||'').trim();
    if(!jobId)return json({ok:false,error:'image_logical_job_id_required'},400);
    if(!sceneId)return json({ok:false,error:'image_asset_scene_id_required'},400);
    let status;try{status=await getImageLogicalJobStatus(env,jobId);}catch(error){return clientError(error);}
    if(!status?.ok)return json({ok:false,error:status?.error||'image_logical_job_not_found'},status?.status||404);
    const asset=(status.state?.scenes||[]).find(scene=>scene.id===sceneId)?.asset;
    if(!asset)return json({ok:false,error:'image_asset_not_ready'},404);
    if(asset.url)return json({ok:true,jobId,sceneId,url:asset.url,model:asset.model||null});
    try{return await getImageBatchAsset(env,asset.batchId,asset.ref);}catch(error){return clientError(error);}
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
