const ACTIVE_STATES=new Set(['submitting','provider_wait','provider_processing','qa_pending']);
const RUNNABLE_STATES=new Set(['queued','retry_pending']);
const TERMINAL_SCENE_STATES=new Set(['complete','complete_unverified','failed_quality','failed_provider','cancelled']);

const copy=value=>structuredClone(value);
const sceneIndex=(state,sceneId)=>state.scenes.findIndex(scene=>scene.scene_id===String(sceneId));

function deriveBatchStatus(state){
  if(state.status==='cancelled')return 'cancelled';
  const scenes=state.scenes||[];
  if(!scenes.length)return 'failed';
  const terminal=scenes.filter(scene=>TERMINAL_SCENE_STATES.has(scene.status)).length;
  const failed=scenes.filter(scene=>scene.status==='failed_quality'||scene.status==='failed_provider').length;
  const completed=scenes.filter(scene=>scene.status==='complete'||scene.status==='complete_unverified').length;
  if(terminal===scenes.length){
    if(completed>0&&failed>0)return 'complete_with_failures';
    if(completed===scenes.length)return 'complete';
    if(failed===scenes.length)return 'failed';
    return 'cancelled';
  }
  if(completed>0||failed>0)return 'partially_complete';
  if(scenes.some(scene=>ACTIVE_STATES.has(scene.status)))return 'running';
  return 'queued';
}

function withStatus(state){
  state.status=deriveBatchStatus(state);
  return state;
}

export function createBatchState(manifest={}){
  const state=copy(manifest);
  state.scheduler={concurrency:Math.max(1,Math.min(8,Number(manifest?.scheduler_config?.concurrency)||4))};
  state.retry={maxAttempts:Math.max(1,Math.min(3,Number(manifest?.retry_policy?.maxAttempts)||3))};
  state.scenes=(manifest?.scenes||[]).map(scene=>({...copy(scene),status:scene.status||'queued',attempts:Array.isArray(scene.attempts)?copy(scene.attempts):[]}));
  state.status='queued';
  state.cancelled_at=null;
  return withStatus(state);
}

export function nextSubmissionSceneIds(state={}){
  if(state.status==='cancelled')return [];
  const active=(state.scenes||[]).filter(scene=>ACTIVE_STATES.has(scene.status)).length;
  const free=Math.max(0,Math.min(8,Number(state?.scheduler?.concurrency)||4)-active);
  if(!free)return [];
  return (state.scenes||[]).filter(scene=>RUNNABLE_STATES.has(scene.status)&&(scene.attempts?.length||0)<(Number(state?.retry?.maxAttempts)||3)).slice(0,free).map(scene=>scene.scene_id);
}

export function markSceneSubmitted(state,input={}){
  const next=copy(state);const index=sceneIndex(next,input.sceneId);
  if(index<0)return next;
  const scene=next.scenes[index];
  if(!RUNNABLE_STATES.has(scene.status))return next;
  if((scene.attempts?.length||0)>=next.retry.maxAttempts){scene.status='failed_provider';return withStatus(next);}
  scene.attempts=Array.isArray(scene.attempts)?scene.attempts:[];
  scene.attempts.push({
    attempt_number:scene.attempts.length+1,
    provider:String(input.provider||''),model:String(input.model||''),seed:input.seed??null,
    provider_job_id:String(input.jobId||''),submit_time:input.submittedAt||null,complete_time:null,
    generation:null,qa_result:null,qa_reasons:[],
  });
  scene.status='provider_wait';
  return withStatus(next);
}

export function markSceneProviderResult(state,input={}){
  const next=copy(state);const index=sceneIndex(next,input.sceneId);
  if(index<0)return next;
  const scene=next.scenes[index];const attempt=scene.attempts?.[scene.attempts.length-1];
  if(!attempt)return next;
  attempt.complete_time=input.completedAt||null;
  if(input.error){
    attempt.provider_error=String(input.error);
    scene.status=(scene.attempts.length>=next.retry.maxAttempts)?'failed_provider':'retry_pending';
    return withStatus(next);
  }
  attempt.generation=copy(input.generation||{});
  scene.status='qa_pending';
  return withStatus(next);
}

export function applySceneQualityDecision(state,input={}){
  const next=copy(state);const index=sceneIndex(next,input.sceneId);
  if(index<0)return next;
  const scene=next.scenes[index];const attempt=scene.attempts?.[scene.attempts.length-1];
  if(!attempt)return next;
  const quality=input.quality||{};
  attempt.complete_time=input.completedAt||attempt.complete_time||null;
  attempt.qa_result=String(quality.decision||'');
  attempt.qa_reasons=Array.isArray(quality.reasons)?quality.reasons.map(String):[];
  attempt.qa_level=quality.qaLevel||null;
  attempt.qa_confidence=quality.qaConfidence??null;
  if(quality.decision==='PASS')scene.status='complete';
  else if(quality.decision==='PASS_UNVERIFIED')scene.status='complete_unverified';
  else if(quality.decision==='FAIL_TERMINAL')scene.status='failed_quality';
  else if(['RETRY_PROMPT','RETRY_MODEL','RETRY_SEED'].includes(quality.decision))scene.status=scene.attempts.length>=next.retry.maxAttempts?'failed_quality':'retry_pending';
  else scene.status=scene.attempts.length>=next.retry.maxAttempts?'failed_quality':'retry_pending';
  scene.last_quality={decision:quality.decision||null,reasons:attempt.qa_reasons};
  return withStatus(next);
}

export function cancelBatchState(state,{cancelledAt=null}={}){
  const next=copy(state);next.status='cancelled';next.cancelled_at=cancelledAt;
  next.scenes=next.scenes.map(scene=>TERMINAL_SCENE_STATES.has(scene.status)?scene:{...scene,status:'cancelled'});
  return next;
}

export function resetFailedScenesForRetry(state,sceneIds=[]){
  const next=copy(state);const wanted=new Set((sceneIds||[]).map(String));
  next.scenes=next.scenes.map(scene=>wanted.has(scene.scene_id)&&['failed_quality','failed_provider','complete_unverified'].includes(scene.status)?{...scene,status:'queued',attempts:[],last_quality:null}:scene);
  if(next.status==='cancelled')return next;
  return withStatus(next);
}

export function summarizeBatch(state={}){
  const scenes=state.scenes||[];
  const count=status=>scenes.filter(scene=>scene.status===status).length;
  const activeScenes=scenes.filter(scene=>ACTIVE_STATES.has(scene.status)).length;
  return {
    batchId:state.batch_id||null,
    status:deriveBatchStatus(state),
    totalScenes:scenes.length,
    activeScenes,
    queuedScenes:scenes.filter(scene=>RUNNABLE_STATES.has(scene.status)).length,
    completeScenes:count('complete'),
    unverifiedScenes:count('complete_unverified'),
    failedScenes:count('failed_quality')+count('failed_provider'),
    cancelledScenes:count('cancelled'),
  };
}
