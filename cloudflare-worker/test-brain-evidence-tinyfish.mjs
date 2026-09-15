import assert from 'node:assert/strict';
import {createBrainEvidenceHandler} from './brain-evidence-handler.js';
import {callTinyFish} from './evidence/tinyfish-client.js';
import {TinyFishCircuit} from './evidence/tinyfish-circuit.js';

let calls=[];
const fetchImpl=async(url,init={})=>{
  calls.push({url:String(url),init});
  assert.equal(init.headers['X-API-Key'],'tiny-secret');
  return new Response(JSON.stringify({results:[{title:'Safe title',url:'https://example.com/a',snippet:'Useful evidence'}]}),{status:200,headers:{'content-type':'application/json'}});
};
let result=await callTinyFish({operation:'search',query:'model health',apiKey:'tiny-secret',fetchImpl,delay:async()=>{}});
assert.equal(result.ok,true);assert.equal(calls[0].url.startsWith('https://api.search.tinyfish.ai?query='),true);
assert.equal(JSON.stringify(result).includes('tiny-secret'),false);

calls=[];
result=await callTinyFish({operation:'fetch',urls:['https://example.com/a'],apiKey:'tiny-secret',fetchImpl,delay:async()=>{}});
assert.equal(result.ok,true);assert.equal(calls[0].url,'https://api.fetch.tinyfish.ai');assert.equal(calls[0].init.method,'POST');
result=await callTinyFish({operation:'fetch',urls:['https://example.com/a'],apiKey:'tiny-secret',fetchImpl:async()=>new Response(JSON.stringify({results:[],errors:[{url:'https://example.com/a',error:'timeout with secret detail'}]}),{status:200}),delay:async()=>{}});
assert.equal(result.ok,false);assert.equal(result.category,'UNKNOWN_SANITIZED');assert.equal(JSON.stringify(result).includes('secret detail'),false);
result=await callTinyFish({operation:'fetch',urls:['https://example.com/a'],apiKey:'tiny-secret',fetchImpl:async()=>new Response(JSON.stringify({results:[{url:'https://example.com/a',final_url:'http://127.0.0.1/private',text:'bad'}],errors:[]}),{status:200}),delay:async()=>{}});
assert.equal(result.ok,false);assert.equal(result.category,'REQUEST_INVALID');

const routeSkill=({text})=>({profile:text==='quick'?'FAST':'STANDARD',primarySkill:'core_reasoning',externalRoutingCalls:0});
const handler=createBrainEvidenceHandler({routeSkill,fetchImpl});
const rows=new Map(),storage={transaction:async fn=>fn({get:async key=>rows.get(key),put:async(key,value)=>rows.set(key,value)})};
const circuit=new TinyFishCircuit({storage}),TINYFISH_CIRCUIT={getByName:()=>({fetch:(url,init)=>circuit.fetch(new Request(url,init))})};
let response=await handler(new Request('https://example.com/brain/evidence/health'),{TINY_FISH_API:'tiny-secret'});
let body=await response.json();assert.equal(body.ok,true);assert.equal(body.configured,true);assert.equal(JSON.stringify(body).includes('tiny-secret'),false);

const request=(path,body,token='token')=>new Request(`https://example.com${path}`,{method:'POST',headers:{'content-type':'application/json','x-model-mesh-token':token},body:JSON.stringify(body)});
response=await handler(request('/brain/evidence/query',{text:'quick'}),{TINY_FISH_API:'tiny-secret',MODEL_MESH_EXECUTION_TOKEN:'token'});
assert.equal(response.status,409);
response=await handler(request('/brain/evidence/query',{text:'secret research',dataClass:'SECRET'}),{TINY_FISH_API:'tiny-secret',MODEL_MESH_EXECUTION_TOKEN:'token'});
assert.equal(response.status,403);
response=await handler(request('/brain/evidence/query',{text:'typo classification',dataClass:'SECRETT'}),{TINY_FISH_API:'tiny-secret',MODEL_MESH_EXECUTION_TOKEN:'token'});
assert.equal(response.status,403);
response=await handler(request('/brain/evidence/query',{text:'research this',operation:'agent'}),{TINY_FISH_API:'tiny-secret',MODEL_MESH_EXECUTION_TOKEN:'token'});
assert.equal(response.status,400);
response=await handler(request('/brain/evidence/query',{text:'research this',operation:'search'}),{TINY_FISH_API:'tiny-secret',MODEL_MESH_EXECUTION_TOKEN:'token',TINYFISH_CIRCUIT});
assert.equal(response.status,200);body=await response.json();assert.equal(body.ok,true);assert.equal(body.routingAuthority,false);assert.equal(body.reasoningAuthority,false);assert.equal(body.provider,'tinyfish');
assert.equal(JSON.stringify(body).includes('tiny-secret'),false);

console.log('TinyFish separate evidence lane contracts ok');
