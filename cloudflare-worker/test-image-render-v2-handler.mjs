import assert from 'node:assert/strict';
import {createImageRenderHandler} from './image-render-handler.js';

const TOKEN='v2-token';const batchCalls=[];const providerCalls=[];
const stub={fetch:async request=>{const u=new URL(request.url);batchCalls.push({path:u.pathname,method:request.method});if(u.pathname==='/create')return new Response(JSON.stringify({ok:true,summary:{status:'queued'}}),{status:201,headers:{'content-type':'application/json'}});if(u.pathname==='/status')return new Response(JSON.stringify({ok:true,summary:{status:'running'},scenes:[]}),{status:200,headers:{'content-type':'application/json'}});if(u.pathname==='/retry')return new Response(JSON.stringify({ok:true,summary:{status:'queued'},scenes:[]}),{status:200,headers:{'content-type':'application/json'}});if(u.pathname==='/cancel')return new Response(JSON.stringify({ok:true,summary:{status:'cancelled'},scenes:[]}),{status:200,headers:{'content-type':'application/json'}});return new Response('{}',{status:404});}};
const env={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:TOKEN,IMAGE_RENDER_BATCH:{idFromName:name=>({name}),get:()=>stub}};
const fetchImpl=async(url)=>{providerCalls.push(String(url));if(String(url).endsWith('/status/models?type=image'))return new Response(JSON.stringify([{name:'Model A',count:3,performance:20,eta:2,queued:0}]),{status:200,headers:{'content-type':'application/json'}});if(String(url).endsWith('/status/heartbeat'))return new Response('{}',{status:200});return new Response('{}',{status:404});};
const handler=createImageRenderHandler({fetchImpl});
const auth={'x-image-render-token':TOKEN,'content-type':'application/json'};
const scenes=Array.from({length:20},(_,i)=>({sceneId:String(i+1),prompt:`scene ${i+1}`}));

let response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({dataClass:'PUBLIC',scenes})}),env);assert.equal(response.status,401);
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({scenes})}),env);assert.equal(response.status,400);assert.equal((await response.json()).error,'data_class_required');
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'INTERNAL',scenes})}),env);assert.equal(response.status,403);
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'PUBLIC',referenceImages:['x'],scenes})}),env);assert.equal(response.status,409);
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'PUBLIC',scenes:Array.from({length:101},()=>({prompt:'x'}))})}),env);assert.equal(response.status,413);
response=await handler(new Request('https://brain.test/brain/image/batch',{method:'POST',headers:auth,body:JSON.stringify({dataClass:'PUBLIC',scenes})}),env);assert.equal(response.status,202);const created=await response.json();assert.equal(created.mode,'FREE_ONLY');assert.equal(created.paidFallback,false);assert.equal(created.sceneCount,20);assert.match(created.batchId,/^img-[0-9a-f-]+$/i);const batchId=created.batchId;
response=await handler(new Request(`https://brain.test/brain/image/batch/status?id=${batchId}`,{headers:{'x-image-render-token':TOKEN}}),env);assert.equal(response.status,200);
response=await handler(new Request('https://brain.test/brain/image/retry',{method:'POST',headers:auth,body:JSON.stringify({batchId,sceneIds:['1']})}),env);assert.equal(response.status,200);
response=await handler(new Request(`https://brain.test/brain/image/batch?id=${batchId}`,{method:'DELETE',headers:{'x-image-render-token':TOKEN}}),env);assert.equal(response.status,200);
response=await handler(new Request('https://brain.test/brain/image/models',{headers:{'x-image-render-token':TOKEN}}),env);assert.equal(response.status,200);const models=await response.json();assert.equal(models.mode,'FREE_ONLY');assert.equal(models.models[0].name,'Model A');assert.equal(providerCalls.some(x=>x.includes('/generate/async')),false);
response=await handler(new Request('https://brain.test/brain/image/health'),env);const health=await response.json();assert.equal(health.batch.enabled,true);assert.equal(health.batch.maxScenes,100);assert.equal(health.quality.metadataOnlyMayReportVerified,false);
assert.ok(batchCalls.some(x=>x.path==='/create'));
console.log('IMAGE_RENDER_V2_HANDLER_TEST=PASS');
