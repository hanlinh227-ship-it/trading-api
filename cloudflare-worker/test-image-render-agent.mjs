import assert from 'node:assert/strict';
import {createImageRenderHandler} from './image-render-handler.js';

const JOB_ID='123e4567-e89b-12d3-a456-426614174000';
const TOKEN='test-image-render-token';
const calls=[];
const fetchImpl=async(url,init={})=>{
  calls.push({url:String(url),init});
  if(String(url).endsWith('/status/heartbeat'))return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
  if(String(url).endsWith('/generate/async')){
    const body=JSON.parse(String(init.body||'{}'));
    assert.equal(init.method,'POST');
    assert.equal(init.headers.apikey,'0000000000');
    assert.equal(body.nsfw,false);
    assert.equal(body.censor_nsfw,true);
    assert.equal(body.shared,false);
    assert.equal(body.params.n,2);
    assert.equal(body.params.width,512);
    assert.equal(body.params.height,512);
    assert.match(body.prompt,/cat/);
    return new Response(JSON.stringify({id:JOB_ID,kudos:0}),{status:202,headers:{'content-type':'application/json'}});
  }
  if(String(url).includes(`/generate/check/${JOB_ID}`))return new Response(JSON.stringify({done:false,faulted:false,wait_time:3,queue_position:2,finished:0,processing:0,waiting:1,is_possible:true}),{status:200,headers:{'content-type':'application/json'}});
  if(String(url).includes(`/generate/status/${JOB_ID}`)&&init.method==='DELETE')return new Response(JSON.stringify({message:'cancelled'}),{status:200,headers:{'content-type':'application/json'}});
  if(String(url).includes(`/generate/status/${JOB_ID}`))return new Response(JSON.stringify({done:true,faulted:false,wait_time:0,queue_position:0,generations:[{img:'https://example.invalid/render.webp',seed:'7',model:'test-model',state:'ok',censored:false}]}),{status:200,headers:{'content-type':'application/json'}});
  return new Response(JSON.stringify({message:'not found'}),{status:404,headers:{'content-type':'application/json'}});
};
const handler=createImageRenderHandler({fetchImpl});
const enabledEnv={IMAGE_RENDER_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_TOKEN:TOKEN};
const authHeaders={'x-image-render-token':TOKEN,'content-type':'application/json'};

{
  const response=await handler(new Request('https://brain.test/brain/image/health'),enabledEnv);
  assert.equal(response.status,200);
  const body=await response.json();
  assert.equal(body.mode,'FREE_ONLY');
  assert.equal(body.paidFallback,false);
  assert.equal(body.provider.id,'ai_horde');
  assert.deepEqual(body.privacy.allowedDataClasses,['PUBLIC']);
  assert.equal(body.privacy.explicitDataClassRequired,true);
  assert.equal(body.privacy.referenceImagesEnabled,false);
  assert.equal(body.privacy.anonymousRequestsMayBeSharedByProvider,true);
}

{
  const response=await handler(new Request('https://brain.test/brain/image/render',{method:'POST',headers:authHeaders,body:JSON.stringify({prompt:'cat',dataClass:'PUBLIC'})}),{});
  assert.equal(response.status,503);
}

{
  const response=await handler(new Request('https://brain.test/brain/image/render',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({prompt:'cat',dataClass:'PUBLIC'})}),enabledEnv);
  assert.equal(response.status,401);
}

{
  const response=await handler(new Request('https://brain.test/brain/image/render',{method:'POST',headers:authHeaders,body:JSON.stringify({prompt:'unclassified cat'})}),enabledEnv);
  assert.equal(response.status,400);
  assert.equal((await response.json()).error,'data_class_required');
}

{
  const response=await handler(new Request('https://brain.test/brain/image/render',{method:'POST',headers:authHeaders,body:JSON.stringify({prompt:'private cat',dataClass:'INTERNAL'})}),enabledEnv);
  assert.equal(response.status,403);
  assert.equal((await response.json()).error,'ai_horde_public_data_only');
}

{
  const response=await handler(new Request('https://brain.test/brain/image/render',{method:'POST',headers:authHeaders,body:JSON.stringify({prompt:'cat',dataClass:'PUBLIC',referenceImages:['data:image/png;base64,AAAA']})}),enabledEnv);
  assert.equal(response.status,409);
  assert.equal((await response.json()).error,'reference_images_not_enabled_for_volunteer_provider');
}

{
  const response=await handler(new Request('https://brain.test/brain/image/render',{method:'POST',headers:authHeaders,body:JSON.stringify({prompt:'a friendly cartoon cat',negativePrompt:'text, watermark',dataClass:'PUBLIC',width:500,height:500,n:2})}),enabledEnv);
  assert.equal(response.status,202);
  const body=await response.json();
  assert.equal(body.jobId,JOB_ID);
  assert.equal(body.anonymous,true);
  assert.equal(body.anonymousRequestsMayBeSharedByProvider,true);
  assert.equal(body.paidFallback,false);
}

{
  const response=await handler(new Request(`https://brain.test/brain/image/check?id=${JOB_ID}`,{headers:{'x-image-render-token':TOKEN}}),enabledEnv);
  assert.equal(response.status,200);
  assert.equal((await response.json()).queuePosition,2);
}

{
  const response=await handler(new Request(`https://brain.test/brain/image/status?id=${JOB_ID}`,{headers:{'x-image-render-token':TOKEN}}),enabledEnv);
  assert.equal(response.status,200);
  const body=await response.json();
  assert.equal(body.done,true);
  assert.equal(body.generations.length,1);
  assert.equal(body.generations[0].imageUrl,'https://example.invalid/render.webp');
}

{
  const response=await handler(new Request(`https://brain.test/brain/image/status?id=${JOB_ID}`,{method:'DELETE',headers:{'x-image-render-token':TOKEN}}),enabledEnv);
  assert.equal(response.status,200);
  assert.equal((await response.json()).cancelled,true);
}

assert.ok(calls.some(call=>call.url.endsWith('/generate/async')));
console.log('IMAGE_RENDER_AGENT_TEST=PASS');
