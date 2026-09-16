function requireBinding(env){
  const binding=env?.IMAGE_RENDER_BATCH;
  if(!binding||typeof binding.idFromName!=='function'||typeof binding.get!=='function')throw new Error('image_render_batch_binding_unavailable');
  return binding;
}

function requireBatchId(batchId){
  const value=String(batchId||'').trim();
  if(!value)throw new Error('image_render_batch_id_required');
  return value;
}

async function callBatch(env,batchId,path,{method='GET',body}={}){
  const binding=requireBinding(env);
  const name=requireBatchId(batchId);
  const id=binding.idFromName(name);
  const stub=binding.get(id);
  const init={method,headers:{accept:'application/json'}};
  if(body!==undefined){init.headers['content-type']='application/json';init.body=JSON.stringify(body);}
  const response=await stub.fetch(new Request(`https://image-render-batch${path}`,init));
  let payload=null;try{payload=await response.json();}catch{payload={};}
  return {ok:response.ok,status:response.status,...payload};
}

export function createImageBatch(env,batchId,manifest){
  return callBatch(env,batchId,'/create',{method:'POST',body:{manifest}});
}

export function getImageBatchStatus(env,batchId){
  return callBatch(env,batchId,'/status');
}

export function cancelImageBatch(env,batchId){
  return callBatch(env,batchId,'/cancel',{method:'DELETE'});
}

export function retryImageBatchScenes(env,batchId,sceneIds=[]){
  return callBatch(env,batchId,'/retry',{method:'POST',body:{sceneIds}});
}
