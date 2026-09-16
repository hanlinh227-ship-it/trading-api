const ACTIVE_SCENE_STATES=new Set(['submitting','provider_wait','provider_processing','qa_pending']);
const COMPLETE_SCENE_STATES=new Set(['complete','complete_unverified']);
const FAILED_SCENE_STATES=new Set(['failed_quality','failed_provider']);
const RUNNABLE_SCENE_STATES=new Set(['queued','retry_pending']);

const clone=value=>structuredClone(value);
const bounded=(value,min,max,fallback)=>{
  const n=Number(value);
  return Number.isFinite(n)?Math.min(max,Math.max(min,Math.trunc(n))):fallback;
};

function sceneById(state,sceneId){
  const id=String(sceneId);
  const scene=state.scenes.find(item=>String(item.scene_id)===id);
  if(!scene) throw new Error(`image_render_scene_not_found:${id}`);
  return scene;
}

function latestAttempt(scene){
  return scene.attempts?.[scene.attempts.length-1]||null;
}

function deriveBatchStatus(state){
  if(state.cancelled) return 'cancelled';
  const scenes=state.scenes||[];
  const complete=scenes.filter(scene=>COMPLETE_SCENE_STATES.has(scene.status)).length;
  const failed=scenes.filter(scene=>FAILED_SCENE_STATES.has(scene.status)).length;
  const active=scenes.filter(scene=>ACTIVE_SCENE_STATES.has(scene.status)).length;
  const runnable=scenes.filter(scene=>RUNNABLE_SCENE_STATES.has(scene.status)).length;
  const cancelled=scenes.filter(scene=>scene.status==='cancelled').length;
  if(!active&&!runnable){
    if(failed||cancelled) return complete?'complete_with_failures':'failed';
    return complete===scenes.length?'complete':'queued';
  }
  if(complete||failed||cancelled) return 'partially_complete';
  return active?'running':'queued';
}

function refresh(state){
  state.status=deriveBatchStatus(state);
  return state;
}

export function createBatchState(manifest={}){
  const schedulerConcurrency=bounded(manifest?.scheduler_config?.concurrency,1,8,4);
  const maxAttempts=bounded(manifest?.retry_policy?.maxAttempts,1,3,3);
  const state={
    ...clone(manifest),
    scheduler:{concurrency:schedulerConcurrency,maxConcurrency:8},
    retry:{maxAttempts},
    scenes:(manifest.scenes||[]).map(scene=>({
      ...clone(scene),
      scene_id:String(scene.scene_id),
      status:scene.status||'queued',
      attempts:Array.isArray(scene.attempts)?clone(scene.attempts):[],
    })),
    cancelled:false,
  };
  return refresh(state);
}

export function nextSubmissionSceneIds(state){
  const concurrency=bounded(state?.scheduler?.concurrency,1,8,4);
  const active=(state.scenes||[]).filter(scene=>ACTIVE_SCENE_STATES.has(scene.status)).length;
  const free=Math.max(0,concurrency-active);
  if(!free||state.cancelled) return [];
  return state.scenes.filter(scene=>RUNNABLE_SCENE_STATES.has(scene.status)).slice(0,free).map(scene=>String(scene.scene_id));
}

export function markSceneSubmitted(state,input={}){
  const next=clone(state);
  const scene=sceneById(next,input.sceneId);
  if(next.cancelled||scene.status==='cancelled'||COMPLETE_SCENE_STATES.has(scene.status)) return refresh(next);
  if(!RUNNABLE_SCENE_STATES.has(scene.status)) throw new Error(`image_render_scene_not_runnable:${scene.scene_id}:${scene.status}`);
  const attemptNumber=(scene.attempts?.length||0)+1;
  if(attemptNumber>next.retry.maxAttempts){
    scene.status='failed_provider';
    return refresh(next);
  }
  scene.status='provider_wait';
  scene.attempts.push({
    attempt:attemptNumber,
    provider:String(input.provider||''),
    model:String(input.model||''),
    provider_job_id:String(input.jobId||''),
    seed:input.seed??null,
    submitted_at:input.submittedAt||null,
    completed_at:null,
    generation_state:'submitted',
    qa_level:null,
    qa_result:null,
    qa_reasons:[],
  });
  return refresh(next);
}

export function markSceneProviderResult(state,input={}){
  const next=clone(state);
  const scene=sceneById(next,input.sceneId);
  const attempt=latestAttempt(scene);
  if(!attempt) throw new Error(`image_render_attempt_missing:${scene.scene_id}`);
  const generation=input.generation||null;
  attempt.completed_at=input.completedAt||attempt.completed_at||null;
  attempt.generation=generation;
  attempt.generation_state=String(generation?.state||input.state||'unknown');
  const usable=Boolean(generation&&typeof generation.imageUrl==='string'&&generation.imageUrl);
  if(usable){
    scene.status='qa_pending';
    return refresh(next);
  }
  const exhausted=scene.attempts.length>=next.retry.maxAttempts;
  scene.status=exhausted?'failed_provider':'retry_pending';
  attempt.qa_result='provider_failure';
  attempt.qa_reasons=[String(input.error||'provider_result_unusable')];
  return refresh(next);
}

export function applySceneQualityDecision(state,input={}){
  const next=clone(state);
  const scene=sceneById(next,input.sceneId);
  const quality=input.quality||{};
  const attempt=latestAttempt(scene);
  if(attempt){
    attempt.completed_at=input.completedAt||attempt.completed_at||null;
    attempt.qa_level=quality.level||null;
    attempt.qa_result=quality.decision||'FAIL_TERMINAL';
    attempt.qa_reasons=Array.isArray(quality.reasons)?clone(quality.reasons):[];
    attempt.qa_confidence=Number.isFinite(Number(quality.confidence))?Number(quality.confidence):null;
  }
  switch(quality.decision){
    case 'PASS':
      scene.status='complete';
      break;
    case 'PASS_UNVERIFIED':
      scene.status='complete_unverified';
      break;
    case 'RETRY_PROMPT':
    case 'RETRY_MODEL':
    case 'RETRY_SEED':
      scene.status=(scene.attempts?.length||0)>=next.retry.maxAttempts?'failed_quality':'retry_pending';
      break;
    case 'FAIL_TERMINAL':
    default:
      scene.status='failed_quality';
      break;
  }
  scene.quality={...clone(quality),completed_at:input.completedAt||null};
  return refresh(next);
}

export function cancelBatchState(state){
  const next=clone(state);
  next.cancelled=true;
  for(const scene of next.scenes){
    if(!COMPLETE_SCENE_STATES.has(scene.status)) scene.status='cancelled';
  }
  return refresh(next);
}

export function resetFailedScenesForRetry(state,sceneIds=[]){
  const next=clone(state);
  const selected=new Set(sceneIds.map(String));
  next.cancelled=false;
  for(const scene of next.scenes){
    if(!selected.has(String(scene.scene_id))) continue;
    if(!FAILED_SCENE_STATES.has(scene.status)&&scene.status!=='cancelled') continue;
    scene.status='retry_pending';
    scene.attempts=[];
    delete scene.quality;
  }
  return refresh(next);
}

export function summarizeBatch(state){
  const scenes=state.scenes||[];
  const counts={};
  for(const scene of scenes) counts[scene.status]=(counts[scene.status]||0)+1;
  const activeScenes=scenes.filter(scene=>ACTIVE_SCENE_STATES.has(scene.status)).length;
  const completeScenes=scenes.filter(scene=>COMPLETE_SCENE_STATES.has(scene.status)).length;
  const failedScenes=scenes.filter(scene=>FAILED_SCENE_STATES.has(scene.status)).length;
  const runnableScenes=scenes.filter(scene=>RUNNABLE_SCENE_STATES.has(scene.status)).length;
  return {
    batchId:state.batch_id||null,
    status:deriveBatchStatus(state),
    totalScenes:scenes.length,
    completeScenes,
    failedScenes,
    activeScenes,
    runnableScenes,
    counts,
    cancelled:Boolean(state.cancelled),
  };
}

export const IMAGE_RENDER_ACTIVE_SCENE_STATES=Object.freeze([...ACTIVE_SCENE_STATES]);
