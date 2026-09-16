function requireBinding(env){
  const binding=env?.IMAGE_LOGICAL_JOB;
  if(!binding||typeof binding.idFromName!=='function'||typeof binding.get!=='function')throw new Error('image_logical_job_binding_unavailable');
  return binding;
}

function requireJobId(jobId){
  const value=String(jobId||'').trim();
  if(!value)throw new Error('image_logical_job_id_required');
  return value;
}

async function callLogicalJob(env,jobId,path,{method='GET',body}={}){
  const binding=requireBinding(env);
  const name=requireJobId(jobId);
  const id=binding.idFromName(name);
  const stub=binding.get(id);
  const init={method,headers:{accept:'application/json'}};
  if(body!==undefined){init.headers['content-type']='application/json';init.body=JSON.stringify(body);}
  const response=await stub.fetch(new Request(`https://image-logical-job${path}`,init));
  let payload={};try{payload=await response.json();}catch{}
  return {ok:response.ok,status:response.status,...payload};
}

export function createImageLogicalJob(env,jobId,scenes,{chunkSize=100}={}){
  return callLogicalJob(env,jobId,'/create',{method:'POST',body:{jobId,scenes,chunkSize}});
}
export function getImageLogicalJobStatus(env,jobId){return callLogicalJob(env,jobId,'/status');}
export function cancelImageLogicalJob(env,jobId){return callLogicalJob(env,jobId,'/cancel',{method:'DELETE'});}
export function retryImageLogicalJobScenes(env,jobId,sceneIds=[]){return callLogicalJob(env,jobId,'/retry',{method:'POST',body:{sceneIds}});}
