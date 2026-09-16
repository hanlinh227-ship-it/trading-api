const TERMINAL=new Set(['complete','complete_unverified','failed_quality','failed_provider','cancelled']);
const clone=value=>structuredClone(value);

function recompute(state){
  if(state.status==='cancelled'||String(state.status).startsWith('waiting_for_'))return state;
  const statuses=state.scenes.map(scene=>scene.status);
  const complete=statuses.filter(status=>status==='complete'||status==='complete_unverified').length;
  const failed=statuses.filter(status=>status==='failed_quality'||status==='failed_provider').length;
  if(statuses.length&&statuses.every(status=>TERMINAL.has(status)))state.status=failed?'complete_with_failures':'complete';
  else if(complete||failed)state.status='partially_complete';
  else if(statuses.some(status=>status!=='queued'))state.status='running';
  else state.status='queued';
  return state;
}

export function createLogicalJob({jobId,scenes,chunkSize=100,operationalSceneLimit=100000}={}){
  if(!Array.isArray(scenes)||scenes.length===0)throw new Error('logical_job_scenes_required');
  if(scenes.length>operationalSceneLimit)throw new Error('operational_scene_limit_exceeded');
  chunkSize=Number(chunkSize);
  if(!Number.isInteger(chunkSize)||chunkSize<1||chunkSize>100)throw new Error('invalid_chunk_size');
  const ids=scenes.map((scene,index)=>String(scene.id||`scene-${index+1}`));
  if(new Set(ids).size!==ids.length)throw new Error('duplicate_scene_id');
  const normalized=scenes.map((scene,index)=>({...scene,id:ids[index],status:'queued',attempts:Number(scene.attempts||0)}));
  const chunks=[];
  for(let index=0;index<normalized.length;index+=chunkSize){
    chunks.push({id:`chunk-${String(chunks.length+1).padStart(4,'0')}`,sceneIds:normalized.slice(index,index+chunkSize).map(scene=>scene.id),status:'queued'});
  }
  return {version:'image_logical_job_v3',jobId:String(jobId||`logical-${Date.now()}`),status:'queued',sceneCount:normalized.length,chunkSize,scenes:normalized,chunks};
}

export function nextLogicalJobActions(state,{maxChunks=1}={}){
  if(['cancelled','complete','complete_with_failures'].includes(state.status)||String(state.status).startsWith('waiting_for_'))return [];
  return state.chunks
    .filter(chunk=>chunk.sceneIds.some(id=>state.scenes.find(scene=>scene.id===id)?.status==='queued'))
    .slice(0,maxChunks)
    .map(chunk=>({type:'SUBMIT_CHUNK',chunkId:chunk.id,sceneIds:chunk.sceneIds.filter(id=>state.scenes.find(scene=>scene.id===id)?.status==='queued')}));
}

export function applyLogicalJobEvent(state,event={}){
  const next=clone(state);
  if(event.type==='WAITING_FOR_FREE_COMPUTE'){
    next.status='waiting_for_free_compute';
    return next;
  }
  if(event.type==='WAITING_FOR_SAFE_FREE_RUNTIME'){
    next.status='waiting_for_safe_free_runtime';
    return next;
  }
  if(event.type==='RESUME'){
    next.status='queued';
    return recompute(next);
  }
  if(event.type==='SCENE_STATUS'){
    const scene=next.scenes.find(item=>item.id===event.sceneId);
    if(!scene)throw new Error('scene_not_found');
    scene.status=String(event.status);
    if(event.attempts!==undefined)scene.attempts=Number(event.attempts);
    return recompute(next);
  }
  throw new Error('unsupported_logical_job_event');
}

export function retryLogicalJobScenes(state,sceneIds=[]){
  const next=clone(state);
  const selected=new Set(sceneIds.map(String));
  for(const scene of next.scenes){
    if(selected.has(scene.id)&&['failed_quality','failed_provider','cancelled'].includes(scene.status))scene.status='queued';
  }
  next.status='queued';
  return recompute(next);
}

export function cancelLogicalJob(state){
  const next=clone(state);
  for(const scene of next.scenes){
    if(!['complete','complete_unverified'].includes(scene.status))scene.status='cancelled';
  }
  for(const chunk of next.chunks){
    if(chunk.status!=='complete')chunk.status='cancelled';
  }
  next.status='cancelled';
  return next;
}
