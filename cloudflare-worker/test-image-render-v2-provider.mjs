import assert from 'node:assert/strict';
import {listAiHordeModels} from './image-render/ai-horde.js';
import {createImageProviderRegistry} from './image-render/provider-registry.js';

const requests=[];
const fetchImpl=async(url,init={})=>{
  requests.push({url:String(url),init});
  if(String(url).endsWith('/status/models?type=image')){
    return new Response(JSON.stringify([
      {name:'Model A',count:4,performance:25.5,eta:2,queued:1},
      {name:'Model B',count:0,performance:10,eta:40,queued:9},
    ]),{status:200,headers:{'content-type':'application/json'}});
  }
  if(String(url).endsWith('/status/heartbeat'))return new Response(JSON.stringify({ok:true}),{status:200,headers:{'content-type':'application/json'}});
  return new Response(JSON.stringify({message:'not found'}),{status:404,headers:{'content-type':'application/json'}});
};

const listed=await listAiHordeModels({fetchImpl});
assert.equal(listed.ok,true);
assert.equal(listed.provider,'ai_horde');
assert.deepEqual(listed.models[0],{name:'Model A',workerCount:4,performance:25.5,eta:2,queued:1});
assert.deepEqual(listed.models[1],{name:'Model B',workerCount:0,performance:10,eta:40,queued:9});
assert.ok(requests.some(row=>row.url.endsWith('/status/models?type=image')));

const registry=createImageProviderRegistry({fetchImpl});
assert.deepEqual(registry.list(),['ai_horde']);
assert.equal(registry.get('unknown',{}),null);
const provider=registry.get('ai_horde',{});
assert.equal(provider.id,'ai_horde');
assert.equal(provider.mode,'FREE_ONLY');
assert.equal(provider.monetaryCost,'zero');
assert.equal(provider.paidFallback,false);
const registryModels=await provider.listModels();
assert.equal(registryModels.models.length,2);
assert.equal((await provider.health()).ok,true);

console.log('IMAGE_RENDER_V2_PROVIDER_TEST=PASS');
