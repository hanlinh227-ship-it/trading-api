import assert from 'node:assert/strict';
import {runUniversalCanary} from './validate-universal-canary.mjs';

const expectedSha='a'.repeat(40);
const tokens={chatgpt:'cg-token',claude:'cl-token',gemini:'gm-token'};
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

const result=await runUniversalCanary({baseUrl:'https://worker.example',sourceSha:expectedSha,clients:tokens,fetchImpl});
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
for(const call of seen){
  const text=JSON.stringify(call);
  assert.equal(text.includes('chainOfThought'),false);
  assert.equal(text.includes('hidden_reasoning'),false);
}
console.log('UNIVERSAL_CANARY_TESTS=PASS');
