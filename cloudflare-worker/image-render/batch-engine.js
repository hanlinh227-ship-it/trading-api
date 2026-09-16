const ACTIVE_STATES=new Set(['submitting','provider_wait','provider_processing','qa_pending']);
const COMPLETE_STATES=new Set(['complete','complete_unverified']);
const FAILED_STATES=new Set(['failed_quality','failed_provider']);
const TERMINAL_STATES=new Set([...COMPLETE_STATES,...FAILED_STATES,'cancelled']);
const RETRY_DECISIONS=new Set(['RETRY_PROMPT','RETRY_MODEL','RETRY_SEED']);
const clone=value=>structuredClone(value);
const clampInt=(value,min,max,fallback)=>{const n=Number(value);return Number.isFinite(n)?Math.min(max,Math.max(min,Math.floor(n))):fallback;};
const findScene=(state,sceneId)=>state.scenes.find(scene=>scene.scene_id===String(sceneId));
const attemptsInWindow=scene=>Math.max(0,(scene.attempts?.length||0)-Number(scene.attempt_window_start||0));

export function createBatchState(manifest={}){
  return {
    batch_id:String(manifest.batch_id||''),
    created_at:manifest.created_at||null,
    cancelled:false,
    scheduler:{concurrency:clampInt(manifest?.scheduler_config?.concurrency,1,8,4)},
    retry:{maxAttempts:clampInt(manifest?.retry_policy?.maxAttempts,1,3,3)},
    manifest:clone(manifest),
    scenes:(Array.isArray(manifest.scenes)?manifest.scenes:[]).map(scene=>({
      ...clone(scene),
      scene_id:String(scene.scene_id),
      status:String(scene.status||'queued'),
      attempts:Array.isArray(scene.attempts)?clone(scene.attempts):[],
      attempt_window_start:Number(scene.attempt_window_start||0),
    })),
  };
}

export function nextSubmissionSceneIds(state){
  const activeCount=state.scenes.filter(scene=>ACTIVE_STATES.has(scene.status)).length;
  const free=Math.max(0,Math.min(8,state.scheduler.concurrency)-activeCount);
  if(free<=0||state.cancelled)return [];
  return state.scenes.filter(scene=>['queued','retry_pending'].includes(scene.status)&&attemptsInWindow(scene)<state.retry.maxAttempts).slice(0,free).map(scene=>scene.scene_id);
}

export function markSceneSubmitted(state,{sceneId,provider,model,jobId,seed,submittedAt}={}){
  const next=clone(state);const scene=findScene(next,sceneId);if(!scene||next.cancelled)return next;
  if(!['queued','retry_pending','submitting'].includes(scene.status))return next;
  if(attemptsInWindow(scene)>=next.retry.maxAttempts){scene.status='failed_provider';return next;}
  const attemptNumber=(scene.attempts?.length||0)+1;
  scene.attempts.push({attempt_number:attemptNumber,provider:String(provider||''),model:String(model||''),seed:seed??null,provider_job_id:String(jobId||''),submit_time:submittedAt??null,complete_time:null,generation:null,QA_result:null,QA_reasons:[]});
  scene.status='provider_wait';
  return next;
}

export function markSceneProviderResult(state,{sceneId,ok=true,generation=null,completedAt=null,error=null,processing=false}={}){
  const next=clone(state);const scene=findScene(next,sceneId);if(!scene||TERMINAL_STATES.has(scene.status))return next;
  const attempt=scene.attempts?.[scene.attempts.length-1];
  if(attempt){attempt.complete_time=completedAt??attempt.complete_time;attempt.generation=generation??attempt.generation;if(error)attempt.provider_error=String(error);}
  if(processing===true){scene.status='provider_processing';return next;}
  if(ok&&generation){scene.status='qa_pending';return next;}
  scene.status=attemptsInWindow(scene)>=next.retry.maxAttempts?'failed_provider':'retry_pending';
  return next;
}

export function applySceneQualityDecision(state,{sceneId,quality={},completedAt=null}={}){
  const next=clone(state);const scene=findScene(next,sceneId);if(!scene||scene.status==='cancelled')return next;
  const decision=String(quality?.decision||'');const reasons=Array.isArray(quality?.reasons)?quality.reasons.map(String):[];
  const attempt=scene.attempts?.[scene.attempts.length-1];
  if(attempt){attempt.complete_time=completedAt??attempt.complete_time;attempt.QA_result=decision;attempt.QA_reasons=reasons;attempt.QA_level=quality?.qaLevel??null;attempt.QA_confidence=quality?.qaConfidence??null;}
  if(decision==='PASS'){scene.status='complete';return next;}
  if(decision==='PASS_UNVERIFIED'){scene.status='complete_unverified';return next;}
  if(decision==='FAIL_TERMINAL'){scene.status='failed_quality';return next;}
  if(RETRY_DECISIONS.has(decision)){scene.status=attemptsInWindow(scene)>=next.retry.maxAttempts?'failed_quality':'retry_pending';return next;}
  scene.status='failed_quality';
  return next;
}

export function cancelBatchState(state){
  const next=clone(state);next.cancelled=true;
  for(const scene of next.scenes)if(!TERMINAL_STATES.has(scene.status))scene.status='cancelled';
  return next;
}

export function resetFailedScenesForRetry(state,sceneIds=[]){
  const next=clone(state);const wanted=new Set((Array.isArray(sceneIds)?sceneIds:[]).map(String));
  for(const scene of next.scenes){
    if(wanted.has(scene.scene_id)&&FAILED_STATES.has(scene.status)){
      scene.status='retry_pending';
      scene.attempt_window_start=scene.attempts.length;
    }
  }
  if(wanted.size)next.cancelled=false;
  return next;
}

export function summarizeBatch(state){
  const totalScenes=state.scenes.length;
  const activeScenes=state.scenes.filter(scene=>ACTIVE_STATES.has(scene.status)).length;
  const completeScenes=state.scenes.filter(scene=>COMPLETE_STATES.has(scene.status)).length;
  const failedScenes=state.scenes.filter(scene=>FAILED_STATES.has(scene.status)).length;
  const cancelledScenes=state.scenes.filter(scene=>scene.status==='cancelled').length;
  const queuedScenes=state.scenes.filter(scene=>['queued','retry_pending'].includes(scene.status)).length;
  let status='queued';
  if(state.cancelled&&cancelledScenes+completeScenes+failedScenes===totalScenes)status='cancelled';
  else if(totalScenes>0&&state.scenes.every(scene=>TERMINAL_STATES.has(scene.status))){
    if(failedScenes>0&&completeScenes===0)status='failed';
    else if(failedScenes>0)status='complete_with_failures';
    else status='complete';
  }else if(completeScenes>0||failedScenes>0)status='partially_complete';
  else if(activeScenes>0)status='running';
  return {batchId:state.batch_id,status,totalScenes,activeScenes,completeScenes,failedScenes,cancelledScenes,queuedScenes};
}

export {ACTIVE_STATES,COMPLETE_STATES,FAILED_STATES,TERMINAL_STATES};
