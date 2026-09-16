import assert from 'node:assert/strict';
import {createImageRenderHandler} from './image-render-handler.js';

const TOKEN='v2-token';
const stubCalls=[];
const stub={fetch:async request=>{
  const url=new URL(request.url);let payload=null;
  if(request.method!=='GET')payload=await request.clone().json().catch(()=>null);
  stubCalls.push({path:url.pathname,method:request.method,payload});
  if(url.pathname==='/create')return new Response(JSON.stringify({ok:true,summary:{status:'queued'}}),{status:201,headers:{'content-type':'application/json'}});
  if(url.pathname==='/status')return new Response(JSON.stringify({ok:true,summary:{status:'running',totalScenes:20}}),{status:200,headers:{'content-type':'application/json'}});
  if(url.pathname==='/cancel')return new Response(JSON.stringify({ok:true,summary:{status:'cancelled'}}),{status:200,headers:{'content-type':'application/json'}});
  if(url.pathname==='/retry')return new Response(JSON.stringify({ok:true,summary:{status:'queued'}}),{status:200,headers:{'content-type':'application/json'}});
  return new Response('{}',{status:404});
}};
const namespace={idFromName:name=>`id:${name}`,get:()=>stub};
const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:TOKEN,IMAGE_RENDER_BATCH:namespace};
const auth={'x-image-render-token':TOKEN,'content-type':'application/json'};
const fetchImpl=async url=>{
  if(String(url).endsWith('/status/heartbeat'))return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
  if(String(url).endsWith('/status/models?type=image'))return new Response(JSON.stringify([{name:'Model A',count:4,performance:20,eta:1,queued:0}]),{status:200,headers:{'content-type':'application/json'}});
  return new Response('{}',{status:404,headers:{'content-type':'application/json'}});
};
const handler=createImageRenderHandler({fetchImpl});
const scenes=Array.from({length:20},(_,i)=>({sceneId:String(i+1),prompt:`scene ${i+1}`}));

let response=await handler(new Request('https://brain.test/brain/image/health'),env);
let body=await response.json();
assert.equal(body.batch.enabled,true);
assert.equal(body.batch.maxScenes,100);
assert.equal(body.quality.metadataOnlyMayReportVerified,false);

response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({dataClass:'PUBLIC',scenes})}),env);
assert.equal(response.status,401);

response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({scenes})}),env);
assert.equal(response.status,400);assert.equal((await response.json()).error,'data_class_required');
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'INTERNAL',scenes})}),env);
assert.equal(response.status,403);
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'PUBLIC',referenceImages:['x'],scenes})}),env);
assert.equal(response.status,409);
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'PUBLIC',scenes:Array.from({length:101},()=>({prompt:'x'}))})}),env);
assert.equal(response.status,413);

response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'PUBLIC',qualityMode:'STRICT',consistencyMode:'STRICT',scenes})}),env);
assert.equal(response.status,202);body=await response.json();
assert.equal(body.mode,'FREE_ONLY');assert.equal(body.paidFallback,false);assert.equal(body.sceneCount,20);assert.match(body.batchId,/^img-/);assert.match(body.statusUrl,/\/brain\/image\/batch\/status\?id=/);
assert.equal(stubCalls.find(x=>x.path==='/create').payload.manifest.scenes.length,20);
assert.ok(stubCalls.find(x=>x.path==='/create').payload.manifest.scenes[0].compiled_prompt.includes('scene 1'));

response=await handler(new Request('https://brain.test/brain/image/models',{headers:{'x-image-render-token':TOKEN}}),env);
assert.equal(response.status,200);body=await response.json();assert.equal(body.models[0].name,'Model A');assert.equal(body.mode,'FREE_ONLY');
response=await handler(new Request(`https://brain.test/brain/image/batch/status?id=${encodeURIComponent(body.batchId||'img-status')}`,{headers:{'x-image-render-token':TOKEN}}),env);
assert.equal(response.status,200);
response=await handler(new Request('https://brain.test/brain/image/retry',{method:'POST',headers:auth,body:JSON.stringify({batchId:'img-retry',sceneIds:['1']})}),env);
assert.equal(response.status,200);
response=await handler(new Request('https://brain.test/brain/image/batch?id=img-cancel',{method:'DELETE',headers:{'x-image-render-token':TOKEN}}),env);
assert.equal(response.status,200);
console.log('IMAGE_RENDER_V2_HANDLER_TEST=PASS');
