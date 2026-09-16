const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

function batchStub(env,batchId){
  const binding=env?.IMAGE_RENDER_BATCH;
  if(!binding||typeof binding.idFromName!=='function'||typeof binding.get!=='function')return null;
  const name=String(batchId||'').trim();
  if(!name)return null;
  return binding.get(binding.idFromName(name));
}
function internal(path,{method='GET',body}={}){
  return new Request(`https://image-render-batch.internal${path}`,{method,headers:body===undefined?undefined:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
}
function missing(){return json({ok:false,error:'image_render_batch_binding_unavailable'},503);}

export async function createImageBatch(env,{batchId,manifest}={}){const stub=batchStub(env,batchId);return stub?stub.fetch(internal('/create',{method:'POST',body:{manifest}})):missing();}
export async function getImageBatchStatus(env,batchId){const stub=batchStub(env,batchId);return stub?stub.fetch(internal('/status')):missing();}
export async function cancelImageBatch(env,batchId){const stub=batchStub(env,batchId);return stub?stub.fetch(internal('/cancel',{method:'DELETE'})):missing();}
export async function retryImageBatchScenes(env,{batchId,sceneIds}={}){const stub=batchStub(env,batchId);return stub?stub.fetch(internal('/retry',{method:'POST',body:{sceneIds}})):missing();}
