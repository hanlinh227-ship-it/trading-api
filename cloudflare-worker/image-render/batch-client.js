function binding(env){
  const namespace=env?.IMAGE_RENDER_BATCH;
  if(!namespace||typeof namespace.idFromName!=='function'||typeof namespace.get!=='function')throw new Error('image_render_batch_binding_unavailable');
  return namespace;
}
function stubFor(env,batchId){
  const namespace=binding(env);const id=namespace.idFromName(String(batchId));return namespace.get(id);
}
async function read(response){let body=null;try{body=await response.json();}catch{}if(!response.ok){const error=new Error(body?.error||`image_render_batch_request_failed:${response.status}`);error.status=response.status;throw error;}return body;}
function req(path,method='GET',body){return new Request(`https://image-render-batch.internal${path}`,{method,headers:body===undefined?undefined:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});}

export async function createImageBatch(env,batchId,manifest){return read(await stubFor(env,batchId).fetch(req('/create','POST',{manifest})));}
export async function getImageBatchStatus(env,batchId){return read(await stubFor(env,batchId).fetch(req('/status')));}
export async function cancelImageBatch(env,batchId){return read(await stubFor(env,batchId).fetch(req('/cancel','DELETE')));}
export async function retryImageBatchScenes(env,batchId,sceneIds){return read(await stubFor(env,batchId).fetch(req('/retry','POST',{sceneIds:Array.isArray(sceneIds)?sceneIds:[]})));}
