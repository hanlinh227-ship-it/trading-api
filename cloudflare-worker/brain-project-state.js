const STATE_KEY='brain-project-state-v1';
const encoder=new TextEncoder();
const MAX_BODY_BYTES=64_000;
const TOP_FIELDS=new Set(['project_id','expected_version','active_phase','status','latest_handoff','job_refs','runtime_revision','updated_by']);
const HANDOFF_FIELDS=new Set(['summary','blockers','next_actions','refs']);
const JOB_FIELDS=new Set(['subsystem','job_id','state']);
const SECRET_PATTERNS=Object.freeze([
  /authorization\s*:/i,
  /bearer\s+\S{8,}/i,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/i,
  /(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}/,
  /(?:^|[^A-Za-z0-9])pk-[A-Za-z0-9_-]{8,}/,
]);

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

function assertObject(value){
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('invalid_project_state');
  return value;
}
function assertExactFields(value,allowed){
  if(Object.keys(value).some(key=>!allowed.has(key)))throw new Error('invalid_project_state');
}
function assertSecretFree(value){
  const text=String(value);
  if(SECRET_PATTERNS.some(pattern=>pattern.test(text)))throw new Error('invalid_project_state');
  return text;
}
function boundedString(value,max,{allowEmpty=false}={}){
  if(typeof value!=='string')throw new Error('invalid_project_state');
  const text=value.trim();
  if((!allowEmpty&&!text)||text.length>max)throw new Error('invalid_project_state');
  return assertSecretFree(text);
}
function boundedStringList(value,maxItems=32,maxChars=500){
  if(!Array.isArray(value)||value.length>maxItems)throw new Error('invalid_project_state');
  return value.map(item=>boundedString(item,maxChars));
}
function normalizeHandoff(value){
  const row=assertObject(value);
  assertExactFields(row,HANDOFF_FIELDS);
  if(!Object.hasOwn(row,'summary')||!Object.hasOwn(row,'blockers')||!Object.hasOwn(row,'next_actions')||!Object.hasOwn(row,'refs'))throw new Error('invalid_project_state');
  return Object.freeze({
    summary:boundedString(row.summary,4000,{allowEmpty:true}),
    blockers:Object.freeze(boundedStringList(row.blockers)),
    next_actions:Object.freeze(boundedStringList(row.next_actions)),
    refs:Object.freeze(boundedStringList(row.refs)),
  });
}
function normalizeJobRefs(value){
  if(!Array.isArray(value)||value.length>32)throw new Error('invalid_project_state');
  return Object.freeze(value.map(raw=>{
    const row=assertObject(raw);
    assertExactFields(row,JOB_FIELDS);
    if(!Object.hasOwn(row,'subsystem')||!Object.hasOwn(row,'job_id')||!Object.hasOwn(row,'state'))throw new Error('invalid_project_state');
    return Object.freeze({
      subsystem:boundedString(row.subsystem,160),
      job_id:boundedString(row.job_id,160),
      state:boundedString(row.state,160),
    });
  }));
}

export function normalizeProjectId(value){
  if(typeof value!=='string')throw new Error('invalid_project_id');
  const text=value.trim().toLowerCase();
  if(!text||text.length>80||text.includes('..')||/[\/\\\r\n\0]/.test(text)||!/^[a-z0-9][a-z0-9._-]*$/.test(text))throw new Error('invalid_project_id');
  return text;
}

function normalizeUpdate(raw,currentVersion){
  const row=assertObject(raw);
  assertExactFields(row,TOP_FIELDS);
  for(const required of TOP_FIELDS)if(!Object.hasOwn(row,required))throw new Error('invalid_project_state');
  const expectedVersion=Number(row.expected_version);
  if(!Number.isInteger(expectedVersion)||expectedVersion<0||expectedVersion>Number.MAX_SAFE_INTEGER)throw new Error('invalid_project_state');
  return Object.freeze({
    project_id:normalizeProjectId(row.project_id),
    expected_version:expectedVersion,
    current_version:currentVersion,
    active_phase:boundedString(row.active_phase,160),
    status:boundedString(row.status,160),
    latest_handoff:normalizeHandoff(row.latest_handoff),
    job_refs:normalizeJobRefs(row.job_refs),
    runtime_revision:boundedString(row.runtime_revision,160),
    updated_by:boundedString(row.updated_by,160),
  });
}

async function readJson(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('invalid_project_state');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('invalid_project_state');
  let value;
  try{value=JSON.parse(text);}catch{throw new Error('invalid_project_state');}
  return value;
}

export function createBrainProjectStateClass({now=Date.now}={}){
  if(typeof now!=='function')throw new Error('invalid_project_state_clock');
  return class BrainProjectStateRuntime{
    constructor(state,env={}){
      if(!state?.storage)throw new Error('project_state_storage_required');
      this.state=state;
      this.env=env;
    }

    async fetch(request){
      const url=new URL(request.url);
      if(url.pathname!=='/state')return json({ok:false,error:'not_found'},404);
      if(request.method==='GET'){
        const state=await this.state.storage.get(STATE_KEY);
        if(!state)return json({ok:false,error:'project_not_initialized'},404);
        return json({ok:true,state});
      }
      if(request.method!=='PUT')return json({ok:false,error:'method_not_allowed'},405);

      let raw;
      try{raw=await readJson(request);}catch{return json({ok:false,error:'invalid_project_state'},400);}
      const current=await this.state.storage.get(STATE_KEY);
      const currentVersion=Number.isInteger(current?.version)?current.version:0;
      let update;
      try{update=normalizeUpdate(raw,currentVersion);}catch{return json({ok:false,error:'invalid_project_state'},400);}
      if(current&&current.project_id!==update.project_id)return json({ok:false,error:'invalid_project_state'},400);
      if(update.expected_version!==currentVersion){
        return json({ok:false,error:'project_state_conflict',currentVersion},409);
      }
      const snapshot=Object.freeze({
        project_id:update.project_id,
        schema_version:1,
        version:currentVersion+1,
        active_phase:update.active_phase,
        status:update.status,
        latest_handoff:update.latest_handoff,
        job_refs:update.job_refs,
        runtime_revision:update.runtime_revision,
        updated_at:new Date(Number(now())).toISOString(),
        updated_by:update.updated_by,
      });
      await this.state.storage.put(STATE_KEY,snapshot);
      return json({ok:true,state:snapshot});
    }
  };
}

export const BrainProjectState=createBrainProjectStateClass();
