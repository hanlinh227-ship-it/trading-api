import assert from 'node:assert/strict';
import {runUniversalCanary} from './validate-universal-canary.mjs';

const expectedSha='a'.repeat(40);
const tokens={chatgpt:'cg-token',claude:'cl-token',gemini:'gm-token'};
const seen=[];
const fetchImpl=async (url,init={})=>{
  const u=new URL(url);seen.push({path:u.pathname,headers:init.headers||{},body:init.body||null});
  const client=init.headers?.['x-brain-client'];
  const auth=init.headers?.authorization;
  assert.equal(auth,`Bearer ${tokens[client]}`);
  if(u.pathname==='/brain/universal/health')return new Response(JSON.stringify({ok:true,brainAuthority:'GITHUB_BRAIN_V4',sourceSha:expectedSha,fastZeroRtt:true,fastExternalRoutingCalls:0}),{status:200});
  if(u.pathname==='/brain/universal/capabilities')return new Response(JSON.stringify({ok:true,adapters:['chatgpt','claude','gemini','evergreen'],userAdapters:['chatgpt','claude','gemini'],paidFallback:false,permissionWidening:false}),{status:200});
  if(u.pathname==='/brain/universal/route'){
    const body=JSON.parse(init.body);
    const live=body.freshness==='live'||body.requested_action_class==='live_or_trading';
    return new Response(JSON.stringify({ok:true,clientId:client,requestId:body.request_id,profile:live?'DEEP':'FAST',onlineBrainRequired:live,safeDegradedAllowed:!live,sourceSha:expectedSha,route:{primarySkill:live?'trading_router':'core_reasoning',externalRoutingCalls:0}}),{status:200});
  }
  return new Response('{}',{status:404});
};

const result=await runUniversalCanary({baseUrl:'https://worker.example',sourceSha:expectedSha,clients:tokens,fetchImpl});
assert.equal(result.ok,true);
assert.deepEqual(result.adapters.sort(),['chatgpt','claude','gemini']);
assert.equal(result.highRiskFailClosed,true);
assert.equal(seen.filter(x=>x.path==='/brain/universal/route').length,4);
for(const call of seen){
  const text=JSON.stringify(call);
  assert.equal(text.includes('chainOfThought'),false);
  assert.equal(text.includes('hidden_reasoning'),false);
}
console.log('UNIVERSAL_CANARY_TESTS=PASS');
