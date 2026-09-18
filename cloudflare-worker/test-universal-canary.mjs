import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runUniversalCanary,buildLiveProductionEvidence,cacheBypassFromObservations} from './validate-universal-canary.mjs';

const expectedSha='a'.repeat(40);
const tokens={chatgpt:'cg-token',claude:'cl-token',gemini:'gm-token'};
const fixedNonce='canary-fixed-nonce-0001';
const seen=[];
let projectState=null;
const fetchImpl=async (url,init={})=>{
  const u=new URL(url);seen.push({path:u.pathname,search:u.search,method:init.method||'GET',headers:init.headers||{},body:init.body||null});
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
  if(u.pathname==='/brain/project/state'&&init.method==='GET'){
    const requestedProject=String(u.searchParams.get('project_id')||'');
    if(!projectState||projectState.project_id!==requestedProject)return new Response(JSON.stringify({ok:false,error:'project_not_initialized'}),{status:404});
    return new Response(JSON.stringify({ok:true,state:projectState}),{status:200});
  }
  if(u.pathname==='/brain/project/state'&&init.method==='PUT'){
    const body=JSON.parse(init.body);
    const currentVersion=projectState?.project_id===body.project_id?(projectState?.version||0):0;
    if(body.expected_version!==currentVersion){
      return new Response(JSON.stringify({ok:false,error:'project_state_conflict',currentVersion}),{status:409});
    }
    projectState={
      project_id:body.project_id,schema_version:1,version:currentVersion+1,active_phase:body.active_phase,status:body.status,
      latest_handoff:body.latest_handoff,job_refs:body.job_refs,runtime_revision:expectedSha,updated_at:'2026-09-17T05:30:00.000Z',updated_by:client,
    };
    return new Response(JSON.stringify({ok:true,state:projectState}),{status:200});
  }
  if(u.pathname==='/brain/bootstrap'){
    const requestedProject=String(u.searchParams.get('project_id')||'');
    if(!projectState||projectState.project_id!==requestedProject)return new Response(JSON.stringify({ok:true,clientId:client,sourceSha:expectedSha,project:{initialized:false,state:null},jobRefs:[],nextAction:null}),{status:200});
    return new Response(JSON.stringify({
      ok:true,brainAuthority:'GITHUB_BRAIN_V4',clientId:client,sourceSha:expectedSha,runtimeRevision:expectedSha,
      project:{initialized:true,state:projectState},jobRefs:projectState.job_refs,nextAction:projectState.latest_handoff.next_actions[0]||null,
      capabilities:{projectContinuity:{versioned:true,conflictSafe:true},imageV3:{canonical:true,runtimeAvailability:'unknown_until_called'}},
    }),{status:200});
  }
  return new Response('{}',{status:404});
};

const result=await runUniversalCanary({baseUrl:'https://worker.example',sourceSha:expectedSha,clients:tokens,fetchImpl,canaryNonce:fixedNonce});
assert.equal(result.ok,true);
assert.deepEqual(result.adapters.sort(),['chatgpt','claude','gemini']);
assert.equal(result.highRiskFailClosed,true);
assert.equal(result.projectContinuity,true);
assert.equal(result.staleWriteBlocked,true);
assert.equal(result.projectIsolation,true);
assert.equal(result.frontDoor.backendReady,true);
assert.equal(result.frontDoor.clientAdapterReady,true);
assert.equal(result.frontDoor.newSessionResumePass,true);
assert.equal(result.frontDoor.versionConflict409Pass,true);
assert.equal(result.frontDoor.liveCanaryPass,false);
assert.equal(result.frontDoor.cacheBypassProven,false);
assert.equal(result.frontDoor.accountIntegrationProven,false);
assert.equal(result.frontDoor.ready,false);
assert.equal(result.projectId,`canary-${expectedSha.slice(0,12)}`);
assert.equal(projectState.version,1);
assert.equal(projectState.updated_by,'chatgpt');
assert.equal(projectState.latest_handoff.summary,`continuity-canary:${expectedSha.slice(0,12)}`);
assert.deepEqual(projectState.job_refs,[{subsystem:'image-v3',job_id:`canary-image-${expectedSha.slice(0,12)}`,state:'canary-pointer'}]);
assert.equal(seen.filter(x=>x.path==='/brain/universal/route').length,4);
assert.equal(seen.filter(x=>x.path==='/brain/project/state'&&x.method==='GET').length,2);
assert.equal(seen.filter(x=>x.path==='/brain/project/state'&&x.method==='PUT').length,2);
assert.equal(seen.filter(x=>x.path==='/brain/bootstrap'&&x.headers['x-brain-client']==='claude').length,1);
assert.equal(seen.filter(x=>x.path==='/brain/project/state'&&x.method==='GET'&&x.search.includes(`isolation-${expectedSha.slice(0,12)}`)).length,1);

assert.ok(seen.length>0);
for(const call of seen){
  const params=new URLSearchParams(call.search);
  assert.equal(params.get('__canary_nonce'),fixedNonce);
  assert.equal(call.headers['cache-control'],'no-store');
  assert.equal(call.headers.pragma,'no-cache');
  assert.equal(call.headers['x-canary-nonce'],fixedNonce);
}
assert.equal(seen.filter(x=>x.path==='/brain/project/state'&&x.method==='GET'&&new URLSearchParams(x.search).get('project_id')===`canary-${expectedSha.slice(0,12)}`).length,1);
assert.equal(seen.filter(x=>x.path==='/brain/bootstrap'&&new URLSearchParams(x.search).get('project_id')===`canary-${expectedSha.slice(0,12)}`).length,1);

assert.equal(Object.prototype.hasOwnProperty.call(result,'frontDoorEvidence'),false);
const genericText=JSON.stringify(result);
assert.equal(genericText.includes('live_canary_pass'),false);
assert.equal(genericText.includes('cache_bypass_proven'),false);
assert.equal(genericText.includes('live production'),false);
assert.equal(genericText.includes('deployed worker'),false);
assert.equal(genericText.includes('LIVE_PRODUCTION_CANARY'),false);
for(const token of Object.values(tokens))assert.equal(genericText.includes(token),false);

for(const call of seen){
  const text=JSON.stringify(call);
  assert.equal(text.includes('chainOfThought'),false);
  assert.equal(text.includes('hidden_reasoning'),false);
}

let fetchCalled=false;
const rejectingFetch=async ()=>{fetchCalled=true;return new Response('{}',{status:200});};
for(const badNonce of ['', '   ', 'bad nonce with spaces', 'x'.repeat(65), 'semi;colon', 'new\nline', 'quote"mark', 'slash/mark', 'hash#mark', 'amp&mark', 'question?mark', 'percent%mark', 'plus+mark', 'equals=mark', 'at@mark', 'dollar$mark', 'star*mark', 'paren(mark', 'bracket[mark', 'brace{mark', 'pipe|mark', 'back\\slash', 'tilde~mark', 'caret^mark', 'backtick`mark', 'less<mark', 'greater>mark', 'comma,mark', 'bang!mark', 'unicode-\u00e9']){
  fetchCalled=false;
  await assert.rejects(
    ()=>runUniversalCanary({baseUrl:'https://worker.example',sourceSha:expectedSha,clients:tokens,fetchImpl:rejectingFetch,canaryNonce:badNonce}),
    /UNIVERSAL_CANARY_NONCE_INVALID|UNIVERSAL_CANARY_NONCE_REQUIRED/,
  );
  assert.equal(fetchCalled,false);
}


// --- an injected fetch cannot manufacture live production evidence ----------
// `fetchImpl=fetch` resolved globalThis.fetch at call time, so `node --import`
// preloading a fake fetch made main() write evidence with zero network
// traffic - and buildLiveProductionEvidence hard-coded live_canary_pass and
// cache_bypass_proven to true, contradicting the very result it was built
// beside, which said false for both. The real fetch is captured at module
// scope and both booleans are now derived from what actually ran.
assert.equal(result.usedDefaultFetch,false);
const injectedEvidence=buildLiveProductionEvidence(result);
assert.equal(injectedEvidence.live_canary_pass,false);
assert.equal(injectedEvidence.cache_bypass_proven,false);
assert.equal(injectedEvidence.ready,false);
assert.equal(injectedEvidence.source_sha,expectedSha);
assert.ok(injectedEvidence.proofs.length>0);
for(const proof of injectedEvidence.proofs){
  assert.equal(proof.includes('live production'),false);
  assert.equal(proof.includes('cache-busted'),false);
}

// The evidence never contradicts its own result object.
assert.equal(injectedEvidence.live_canary_pass,result.frontDoor.liveCanaryPass);
assert.equal(injectedEvidence.cache_bypass_proven,result.frontDoor.cacheBypassProven);

// --- cache_bypass_proven is a response-side observation, not a request one --
// It used to be asserted purely from the request side - a nonce and a
// no-store header - and no response was ever inspected.
assert.equal(cacheBypassFromObservations([]),false);
assert.equal(cacheBypassFromObservations([{cacheStatus:null,age:null}]),false);
assert.equal(cacheBypassFromObservations([{cacheStatus:'HIT',age:'0'}]),false);
assert.equal(cacheBypassFromObservations([{cacheStatus:'MISS',age:'120'}]),false);
assert.equal(cacheBypassFromObservations([{cacheStatus:'MISS',age:'0'},{cacheStatus:'DYNAMIC',age:null}]),true);
assert.equal(cacheBypassFromObservations([{cacheStatus:'MISS',age:'0'},{cacheStatus:'HIT',age:'0'}]),false);
assert.ok(Array.isArray(result.cacheObservations));
assert.equal(result.cacheObservations.length,seen.length);
assert.equal(result.cacheBypassObserved,false);

// --- a caller-supplied nonce is not cache-busting on the main() path -------
await assert.rejects(
  ()=>runUniversalCanary({baseUrl:'https://worker.example',sourceSha:expectedSha,clients:tokens,fetchImpl:rejectingFetch,canaryNonce:fixedNonce,requireGeneratedNonce:true}),
  /UNIVERSAL_CANARY_NONCE_NOT_ACCEPTED/,
);

// --- the nonce fallback is not a coin toss --------------------------------
const source=readFileSync(new URL('./validate-universal-canary.mjs',import.meta.url),'utf8');
assert.equal(source.includes('Math.random'),false);
assert.ok(source.includes('const REAL_FETCH='));

console.log('UNIVERSAL_CANARY_TESTS=PASS');
