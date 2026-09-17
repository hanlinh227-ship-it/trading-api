import assert from 'node:assert/strict';
import {createBrainProjectStateClass} from './brain-project-state.js';
import {createProjectContinuityHandler} from './project-continuity-handler.js';

class MemoryStorage{
  constructor(){this.map=new Map();}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
}

const ProjectState=createBrainProjectStateClass({now:()=>Date.parse('2026-09-17T05:00:00.000Z')});
function createNamespace(){
  const objects=new Map();
  const ids=[];
  return {
    ids,
    idFromName(name){ids.push(name);return `project:${name}`;},
    get(id){
      if(!objects.has(id)){
        const object=new ProjectState({storage:new MemoryStorage()},{});
        objects.set(id,{fetch:request=>object.fetch(request)});
      }
      return objects.get(id);
    },
  };
}

const namespace=createNamespace();
const snapshot={schema_version:1,source_sha:'a'.repeat(40),release_id:'4.15.0'};
const handler=createProjectContinuityHandler({snapshot});
const tokens={chatgpt:'chatgpt-token',claude:'claude-token',gemini:'gemini-token'};
const env={
  BRAIN_CLIENT_CHATGPT_TOKEN:tokens.chatgpt,
  BRAIN_CLIENT_CLAUDE_TOKEN:tokens.claude,
  BRAIN_CLIENT_GEMINI_TOKEN:tokens.gemini,
  BRAIN_EVERGREEN_TOKEN:'evergreen-token',
  BRAIN_PROJECT_STATE:namespace,
  RUNTIME_REVISION:'b'.repeat(40),
};
function request(client,path,{method='GET',body,token=tokens[client]}={}){
  const headers={'x-brain-client':client,authorization:`Bearer ${token}`};
  const init={method,headers};
  if(body!==undefined){headers['content-type']='application/json';init.body=JSON.stringify(body);}
  return new Request(`https://worker.example${path}`,init);
}
const imageState={
  project_id:'image-agent',expected_version:0,active_phase:'production-operation',status:'active',
  latest_handoff:{summary:'Image V3 is canonical',blockers:[],next_actions:['render scene 1'],refs:['spec:scene-1']},
  job_refs:[{subsystem:'image-v3',job_id:'logical-1',state:'running'}],
};

let response=await handler(request('chatgpt','/brain/project/state',{method:'PUT',body:imageState}),env,{});
assert.equal(response.status,200);
let payload=await response.json();
assert.equal(payload.ok,true);
assert.equal(payload.state.version,1);
assert.equal(payload.state.project_id,'image-agent');
assert.equal(payload.state.updated_by,'chatgpt');
assert.equal(payload.state.runtime_revision,'b'.repeat(40));
assert.equal(namespace.ids.at(-1),'image-agent');

// Independent Claude session has no transcript state; bootstrap must reconstruct from Brain state.
response=await handler(request('claude','/brain/bootstrap?project_id=Image-Agent'),env,{});
assert.equal(response.status,200);
payload=await response.json();
assert.equal(payload.ok,true);
assert.equal(payload.clientId,'claude');
assert.equal(payload.brainAuthority,'GITHUB_BRAIN_V4');
assert.equal(payload.sourceSha,'a'.repeat(40));
assert.equal(payload.releaseId,'4.15.0');
assert.equal(payload.runtimeRevision,'b'.repeat(40));
assert.equal(payload.project.initialized,true);
assert.equal(payload.project.state.version,1);
assert.equal(payload.project.state.latest_handoff.summary,'Image V3 is canonical');
assert.deepEqual(payload.jobRefs,[{subsystem:'image-v3',job_id:'logical-1',state:'running'}]);
assert.equal(payload.nextAction,'render scene 1');
assert.equal(payload.capabilities.projectContinuity.versioned,true);
assert.equal(payload.capabilities.projectContinuity.conflictSafe,true);
assert.equal(payload.capabilities.imageV3.canonical,true);
assert.equal(payload.capabilities.imageV3.runtimeAvailability,'unknown_until_called');
assert.equal(payload.routes.universalRoute,'/brain/universal/route');
assert.equal(payload.routes.imageJobs,'/brain/image/v3/jobs');
assert.equal(payload.routes.imageStatus,'/brain/image/v3/jobs/status');
assert.equal(payload.routes.imageRetry,'/brain/image/v3/jobs/retry');
assert.equal(payload.routes.imageAssets,'/brain/image/v3/jobs/assets');
for(const token of Object.values(tokens))assert.equal(JSON.stringify(payload).includes(token),false);

// Another project must remain isolated.
response=await handler(request('claude','/brain/bootstrap?project_id=design-project'),env,{});
assert.equal(response.status,200);
payload=await response.json();
assert.equal(payload.project.initialized,false);
assert.equal(payload.project.state,null);
assert.deepEqual(payload.jobRefs,[]);
assert.equal(payload.nextAction,null);
assert.equal(namespace.ids.at(-1),'design-project');

const designState={
  project_id:'design-project',expected_version:0,active_phase:'drafting',status:'active',
  latest_handoff:{summary:'Design project only',blockers:[],next_actions:['continue design'],refs:[]},job_refs:[],
};
response=await handler(request('gemini','/brain/project/state',{method:'PUT',body:designState}),env,{});
assert.equal(response.status,200);
assert.equal((await response.json()).state.version,1);

response=await handler(request('chatgpt','/brain/project/state?project_id=image-agent'),env,{});
assert.equal(response.status,200);
payload=await response.json();
assert.equal(payload.state.latest_handoff.summary,'Image V3 is canonical');
assert.equal(payload.state.version,1);

// Stale client cannot overwrite version 1.
response=await handler(request('claude','/brain/project/state',{method:'PUT',body:{...imageState,active_phase:'stale'}}),env,{});
assert.equal(response.status,409);
payload=await response.json();
assert.equal(payload.error,'project_state_conflict');
assert.equal(payload.currentVersion,1);

response=await handler(request('chatgpt','/brain/project/state?project_id=missing-project'),env,{});
assert.equal(response.status,404);
payload=await response.json();
assert.equal(payload.error,'project_not_initialized');

response=await handler(request('chatgpt','/brain/bootstrap?project_id=image-agent',{token:'wrong-token'}),env,{});
assert.equal(response.status,401);
payload=await response.json();
assert.equal(JSON.stringify(payload).includes('wrong-token'),false);

const noBindingEnv={...env};delete noBindingEnv.BRAIN_PROJECT_STATE;
response=await handler(request('chatgpt','/brain/bootstrap?project_id=image-agent'),noBindingEnv,{});
assert.equal(response.status,503);
payload=await response.json();
assert.equal(payload.error,'project_state_unavailable');

response=await handler(new Request('https://worker.example/not-continuity'),env,{});
assert.equal(response,null);

console.log('PROJECT_CONTINUITY_HANDLER_TESTS=PASS');
