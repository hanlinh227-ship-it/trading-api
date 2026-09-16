import assert from 'node:assert/strict';
import {listAiHordeModels} from './image-render/ai-horde.js';
import {createImageProviderRegistry} from './image-render/provider-registry.js';

const fetchImpl=async url=>{
  assert.match(String(url),/status\/models\?type=image$/);
  return new Response(JSON.stringify([
    {name:'Model A',count:4,performance:25.5,eta:2,queued:1},
    {name:'Model B',count:1,performance:10,eta:40,queued:9},
  ]),{status:200,headers:{'content-type':'application/json'}});
};

const listed=await listAiHordeModels({fetchImpl});
assert.equal(listed.ok,true);
assert.deepEqual(listed.models[0],{name:'Model A',workerCount:4,performance:25.5,eta:2,queued:1});
const registry=createImageProviderRegistry({fetchImpl});
assert.deepEqual(registry.list(),['ai_horde']);
assert.equal(registry.get('unknown',{}),null);
const provider=registry.get('ai_horde',{});
assert.ok(provider);
assert.equal((await provider.listModels()).models.length,2);
console.log('IMAGE_RENDER_V2_PROVIDER_TEST=PASS');
