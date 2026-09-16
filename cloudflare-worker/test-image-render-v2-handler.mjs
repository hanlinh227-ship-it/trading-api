import assert from 'node:assert/strict';
import {createImageRenderHandler} from './image-render-handler.js';

const token='test-image-token';
const calls=[];
const stub={
  async fetch(request){
    calls.push({url:request.url,method:request.method,body:request.method==='GET'||request.method==='DELETE'?null:await request.clone().json()});
    const path=new URL(request.url).pathname;
    if(path==='/create'){
      const {manifest}=await request.json();
      return new Response(JSON.stringify({ok:true,state:{batch_id:manifest.batch_id},summary:{status:'queued',totalScenes:manifest.scenes.length}}),{status:201,headers:{'content-type':'application/json'}});
    }
    if(path==='/status')return new Response(JSON.stringify({ok:true,state:{batch_id:'img-test'},summary:{status:'running'}}),{status:200,headers:{'content-type':'application/json'}});
    if(path==='/retry')return new Response(JSON.stringify({ok:true,state:{batch_id:'img-test'},summary:{status:'running'}}),{status:200,headers:{'content-type':'application/json'}});
    if(path==='/cancel')return new Response(JSON.stringify({ok:true,state:{batch_id:'img-test'},summary:{status:'cancelled'}}),{status:200,headers:{'content-type':'application/json'}});
    return new Response('{}',{status:404});
  },
};
const env={
  IMAGE_RENDER_EXECUTION_ENABLED:'1',
  IMAGE_RENDER_EXECUTION_TOKEN:token,
  IMAGE_RENDER_BATCH:{idFromName:name=>`id:${name}`,get:()=>stub},
};
const fetchImpl=async url=>{
  if(String(url).includes('/status/heartbeat'))return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
  if(String(url).includes('/status/models'))return new Response(JSON.stringify([
    {name:'Model A',count:5,performance:20,eta:2,queued:0},
    {name:'Model B',count:2,performance:12,eta:8,queued:4},
  ]),{status:200,headers:{'content-type':'application/json'}});
  throw new Error(`unexpected fetch ${url}`);
};
const handler=createImageRenderHandler({fetchImpl});
const scenes=n=>Array.from({length:n},(_,i)=>({sceneId:String(i+1),prompt:`scene ${i+1}`}));
const request=(path,{method='GET',body,auth=true}={})=>new Request(`https://worker.example${path}`,{method,headers:{...(auth?{'x-image-render-token':token}:{}),...(body!==undefined?{'content-type':'application/json'}:{})},body:body===undefined?undefined:JSON.stringify(body)});

let response=await handler(request('/brain/image/batch',{method:'POST',auth:false,body:{dataClass:'PUBLIC',scenes:scenes(20)}}),env);
assert.equal(response.status,401);
response=await handler(request('/brain/image/batch',{method:'POST',body:{scenes:scenes(20)}}),env);
assert.equal(response.status,400);assert.equal((await response.json()).error,'data_class_required');
response=await handler(request('/brain/image/batch',{method:'POST',body:{dataClass:'INTERNAL',scenes:scenes(20)}}),env);
assert.equal(response.status,403);
response=await handler(request('/brain/image/batch',{method:'POST',body:{dataClass:'PUBLIC',referenceImages:['x'],scenes:scenes(20)}}),env);
assert.equal(response.status,409);
response=await handler(request('/brain/image/batch',{method:'POST',body:{dataClass:'PUBLIC',scenes:scenes(101)}}),env);
assert.equal(response.status,413);

response=await handler(request('/brain/image/batch',{method:'POST',body:{dataClass:'PUBLIC',qualityMode:'STRICT',consistencyMode:'STRICT',scenes:scenes(20)}}),env);
assert.equal(response.status,202);
const accepted=await response.json();
assert.equal(accepted.ok,true);assert.equal(accepted.mode,'FREE_ONLY');assert.equal(accepted.paidFallback,false);assert.equal(accepted.sceneCount,20);
assert.match(accepted.batchId,/^img-[0-9a-f-]+$/i);assert.equal(accepted.statusUrl,`/brain/image/batch/status?id=${encodeURIComponent(accepted.batchId)}`);
assert.equal(calls.find(x=>x.method==='POST'&&new URL(x.url).pathname==='/create').body.manifest.batch_id,accepted.batchId);

response=await handler(request('/brain/image/models'),env);
assert.equal(response.status,200);
const models=await response.json();
assert.equal(models.mode,'FREE_ONLY');assert.equal(models.paidFallback,false);assert.equal(models.provider,'ai_horde');assert.equal(models.models[0].name,'Model A');

response=await handler(request(`/brain/image/batch/status?id=${accepted.batchId}`),env);
assert.equal(response.status,200);
response=await handler(request('/brain/image/retry',{method:'POST',body:{batchId:accepted.batchId,sceneIds:['1']}}),env);
assert.equal(response.status,200);
response=await handler(request(`/brain/image/batch?id=${accepted.batchId}`,{method:'DELETE'}),env);
assert.equal(response.status,200);

response=await handler(request('/brain/image/health',{auth:false}),env);
assert.equal(response.status,200);
const health=await response.json();
assert.equal(health.mode,'FREE_ONLY');assert.equal(health.provider.id,'ai_horde');
assert.equal(health.batch.maxScenes,100);assert.equal(health.batch.defaultConcurrency,4);assert.equal(health.batch.maxConcurrency,8);assert.equal(health.batch.maxAttemptsPerScene,3);
assert.equal(health.quality.strictVisualVerificationRequired,true);assert.equal(health.quality.metadataOnlyMayReportVerified,false);

console.log('IMAGE_RENDER_V2_HANDLER_TEST=PASS');
