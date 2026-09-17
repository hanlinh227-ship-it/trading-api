import {authenticateAdapter,requiredScopeForPath} from './universal-auth.js';
import {normalizeProjectId} from './brain-project-state.js';

const MAX_BODY_BYTES=64_000;
const encoder=new TextEncoder();
const PUBLIC_UPDATE_FIELDS=new Set(['project_id','expected_version','active_phase','status','latest_handoff','job_refs']);
const SUPPORTED_PATHS=new Set(['/brain/bootstrap','/brain/project/state']);
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

async function parsePublicUpdate(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('invalid_project_state');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('invalid_project_state');
  let value;
  try{value=JSON.parse(text);}catch{throw new Error('invalid_project_state');}
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!PUBLIC_UPDATE_FIELDS.has(key)))throw new Error('invalid_project_state');
  for(const field of PUBLIC_UPDATE_FIELDS)if(!Object.hasOwn(value,field))throw new Error('invalid_project_state');
  return value;
}

function binding(env){
  const namespace=env?.BRAIN_PROJECT_STATE;
  if(!namespace||typeof namespace.idFromName!=='function'||typeof namespace.get!=='function')return null;
  return namespace;
}

function runtimeRevision(env,snapshot){
  const value=String(env?.RUNTIME_REVISION||snapshot?.source_sha||'').trim();
  return value.slice(0,160);
}

async function projectStub(env,projectId){
  const namespace=binding(env);
  if(!namespace)return null;
  const id=namespace.idFromName(projectId);
  return namespace.get(id);
}

async function readProject(stub){
  try{
    const response=await stub.fetch(new Request('https://brain-project.internal/state',{method:'GET'}));
    const text=await response.text();
    let body;try{body=JSON.parse(text);}catch{return {status:503,body:{ok:false,error:'project_state_unavailable'}};}
    return {status:response.status,body};
  }catch{
    return {status:503,body:{ok:false,error:'project_state_unavailable'}};
  }
}

export function createProjectContinuityHandler({snapshot}={}){
  if(!snapshot||snapshot.schema_version!==1||typeof snapshot.source_sha!=='string')throw new Error('PROJECT_CONTINUITY_SNAPSHOT_REQUIRED');
  return async function handleProjectContinuity(request,env={}){
    const url=new URL(request.url);
    if(!SUPPORTED_PATHS.has(url.pathname))return null;
    const requiredScope=requiredScopeForPath(url.pathname,request.method);
    if(!requiredScope)return json({ok:false,error:'method_not_allowed'},405);
    const auth=await authenticateAdapter(request,env,requiredScope);
    if(!auth.ok)return json({ok:false,error:auth.error},auth.status);
    if(!binding(env))return json({ok:false,error:'project_state_unavailable'},503);

    if(url.pathname==='/brain/project/state'&&request.method==='PUT'){
      let raw;
      try{raw=await parsePublicUpdate(request);}catch{return json({ok:false,error:'invalid_project_state'},400);}
      let projectId;
      try{projectId=normalizeProjectId(raw.project_id);}catch{return json({ok:false,error:'invalid_project_state'},400);}
      let stub;
      try{stub=await projectStub(env,projectId);}catch{return json({ok:false,error:'project_state_unavailable'},503);}
      if(!stub||typeof stub.fetch!=='function')return json({ok:false,error:'project_state_unavailable'},503);
      const internalBody={
        project_id:projectId,
        expected_version:raw.expected_version,
        active_phase:raw.active_phase,
        status:raw.status,
        latest_handoff:raw.latest_handoff,
        job_refs:raw.job_refs,
        runtime_revision:runtimeRevision(env,snapshot),
        updated_by:auth.principal.clientId,
      };
      try{
        const response=await stub.fetch(new Request('https://brain-project.internal/state',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(internalBody)}));
        const text=await response.text();
        let body;try{body=JSON.parse(text);}catch{return json({ok:false,error:'project_state_unavailable'},503);}
        return json(body,response.status);
      }catch{
        return json({ok:false,error:'project_state_unavailable'},503);
      }
    }

    let projectId;
    try{projectId=normalizeProjectId(url.searchParams.get('project_id')||'');}catch{return json({ok:false,error:'invalid_project_id'},400);}
    let stub;
    try{stub=await projectStub(env,projectId);}catch{return json({ok:false,error:'project_state_unavailable'},503);}
    if(!stub||typeof stub.fetch!=='function')return json({ok:false,error:'project_state_unavailable'},503);
    const current=await readProject(stub);

    if(url.pathname==='/brain/project/state'){
      if(current.status===404&&current.body?.error==='project_not_initialized')return json(current.body,404);
      if(current.status!==200)return json({ok:false,error:'project_state_unavailable'},503);
      return json(current.body,200);
    }

    let state=null;
    if(current.status===200&&current.body?.ok===true)state=current.body.state||null;
    else if(!(current.status===404&&current.body?.error==='project_not_initialized'))return json({ok:false,error:'project_state_unavailable'},503);
    const initialized=state!==null;
    const nextActions=Array.isArray(state?.latest_handoff?.next_actions)?state.latest_handoff.next_actions:[];
    const jobRefs=Array.isArray(state?.job_refs)?state.job_refs:[];
    return json({
      ok:true,
      brainAuthority:'GITHUB_BRAIN_V4',
      clientId:auth.principal.clientId,
      sourceSha:snapshot.source_sha,
      releaseId:snapshot.release_id||null,
      runtimeRevision:runtimeRevision(env,snapshot),
      project:{initialized,state},
      jobRefs,
      nextAction:nextActions[0]||null,
      capabilities:{
        projectContinuity:{versioned:true,conflictSafe:true},
        imageV3:{canonical:true,runtimeAvailability:'unknown_until_called'},
      },
      routes:{
        universalRoute:'/brain/universal/route',
        imageJobs:'/brain/image/v3/jobs',
        imageStatus:'/brain/image/v3/jobs/status',
        imageRetry:'/brain/image/v3/jobs/retry',
        imageAssets:'/brain/image/v3/jobs/assets',
      },
    });
  };
}
