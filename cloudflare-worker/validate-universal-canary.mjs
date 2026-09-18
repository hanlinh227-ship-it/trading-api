const USER_ADAPTERS=Object.freeze(['chatgpt','claude','gemini']);
const FORBIDDEN_RESPONSE_TERMS=Object.freeze(['chainOfThought','hidden_reasoning','chain_of_thought','raw_private_payload','raw_private_tool_payload']);

function cleanBaseUrl(value){
  const text=String(value||'').trim().replace(/\/+$/,'');
  if(!/^https:\/\//i.test(text))throw new Error('WORKER_BASE_URL_REQUIRED');
  return text;
}
function cleanSha(value){
  const text=String(value||'').trim().toLowerCase();
  if(!/^[a-f0-9]{40}$/.test(text))throw new Error('SOURCE_SHA_REQUIRED');
  return text;
}
function sanitizeCheck(value,tokens){
  const text=JSON.stringify(value);
  for(const term of FORBIDDEN_RESPONSE_TERMS)if(text.includes(term))throw new Error(`UNIVERSAL_CANARY_FORBIDDEN_RESPONSE_FIELD:${term}`);
  for(const token of Object.values(tokens))if(token&&text.includes(token))throw new Error('UNIVERSAL_CANARY_TOKEN_ECHO');
}
async function requestJsonStatus(fetchImpl,baseUrl,path,{clientId,token,body,method}={}){
  const headers={'x-brain-client':clientId,authorization:`Bearer ${token}`};
  const init={method:method||(body===undefined?'GET':'POST'),headers};
  if(body!==undefined){headers['content-type']='application/json';init.body=JSON.stringify(body);}
  const response=await fetchImpl(`${baseUrl}${path}`,init);
  const text=await response.text();
  let value;
  try{value=JSON.parse(text);}catch{throw new Error(`UNIVERSAL_CANARY_INVALID_JSON:${path}`);}
  return {status:response.status,ok:response.ok,value};
}
async function requestJson(fetchImpl,baseUrl,path,options={}){
  const result=await requestJsonStatus(fetchImpl,baseUrl,path,options);
  if(!result.ok)throw new Error(`UNIVERSAL_CANARY_HTTP_${result.status}:${path}`);
  return result.value;
}

export async function runUniversalCanary({baseUrl,sourceSha,clients,fetchImpl=fetch}={}){
  const endpoint=cleanBaseUrl(baseUrl);
  const expected=cleanSha(sourceSha);
  if(!clients||typeof clients!=='object')throw new Error('UNIVERSAL_CANARY_CLIENTS_REQUIRED');
  for(const id of USER_ADAPTERS)if(!String(clients[id]||'').trim())throw new Error(`UNIVERSAL_CANARY_CLIENT_TOKEN_REQUIRED:${id}`);
  const primary='chatgpt';
  const primaryToken=String(clients[primary]);

  const health=await requestJson(fetchImpl,endpoint,'/brain/universal/health',{clientId:primary,token:primaryToken});
  sanitizeCheck(health,clients);
  if(health.ok!==true||health.brainAuthority!=='GITHUB_BRAIN_V4'||health.sourceSha!==expected||health.fastZeroRtt!==true||health.fastExternalRoutingCalls!==0){
    throw new Error('UNIVERSAL_BRAIN_HEALTH_FAILED');
  }

  const capabilities=await requestJson(fetchImpl,endpoint,'/brain/universal/capabilities',{clientId:primary,token:primaryToken});
  sanitizeCheck(capabilities,clients);
  const advertised=new Set(Array.isArray(capabilities.userAdapters)?capabilities.userAdapters:(Array.isArray(capabilities.adapters)?capabilities.adapters:[]));
  for(const id of USER_ADAPTERS)if(!advertised.has(id))throw new Error(`UNIVERSAL_CANARY_ADAPTER_MISSING:${id}`);
  if(capabilities.paidFallback!==false||capabilities.permissionWidening!==false)throw new Error('UNIVERSAL_CANARY_CAPABILITY_SAFETY_FAILED');

  for(const id of USER_ADAPTERS){
    const body={
      text:'explain recursion briefly',request_id:`canary-${id}`,session_id:'production-canary',freshness:'none',data_class:'PUBLIC',requested_action_class:'informational'
    };
    const routed=await requestJson(fetchImpl,endpoint,'/brain/universal/route',{clientId:id,token:String(clients[id]),body});
    sanitizeCheck(routed,clients);
    if(routed.ok!==true||routed.clientId!==id||routed.sourceSha!==expected)throw new Error(`UNIVERSAL_ADAPTER_ROUTE_FAILED:${id}`);
  }

  const highRisk=await requestJson(fetchImpl,endpoint,'/brain/universal/route',{
    clientId:primary,
    token:primaryToken,
    body:{text:'giao dịch BTC live',request_id:'canary-live',session_id:'production-canary',freshness:'live',data_class:'PUBLIC',requested_action_class:'live_or_trading'}
  });
  sanitizeCheck(highRisk,clients);
  if(highRisk.ok!==true||highRisk.profile!=='DEEP'||highRisk.onlineBrainRequired!==true||highRisk.safeDegradedAllowed!==false){
    throw new Error('UNIVERSAL_HIGH_RISK_FAIL_CLOSED_FAILED');
  }

  const suffix=expected.slice(0,12);
  const projectId=`canary-${suffix}`;
  const statePath=`/brain/project/state?project_id=${encodeURIComponent(projectId)}`;
  const initial=await requestJsonStatus(fetchImpl,endpoint,statePath,{clientId:primary,token:primaryToken,method:'GET'});
  sanitizeCheck(initial.value,clients);
  let previousVersion=0;
  if(initial.status===200&&initial.value?.ok===true&&initial.value?.state?.project_id===projectId&&Number.isInteger(initial.value?.state?.version)){
    previousVersion=initial.value.state.version;
  }else if(!(initial.status===404&&initial.value?.error==='project_not_initialized')){
    throw new Error('UNIVERSAL_PROJECT_STATE_READ_FAILED');
  }

  const jobRef={subsystem:'image-v3',job_id:`canary-image-${suffix}`,state:'canary-pointer'};
  const handoff={summary:`continuity-canary:${suffix}`,blockers:[],next_actions:[`resume-canary-${suffix}`],refs:[`source-${suffix}`]};
  const updateBody={
    project_id:projectId,
    expected_version:previousVersion,
    active_phase:'production-continuity-canary',
    status:'canary-ready',
    latest_handoff:handoff,
    job_refs:[jobRef],
  };
  const written=await requestJsonStatus(fetchImpl,endpoint,'/brain/project/state',{clientId:primary,token:primaryToken,method:'PUT',body:updateBody});
  sanitizeCheck(written.value,clients);
  const writtenState=written.value?.state;
  if(written.status!==200||written.value?.ok!==true||writtenState?.project_id!==projectId||writtenState?.version!==previousVersion+1||writtenState?.updated_by!=='chatgpt'||writtenState?.latest_handoff?.summary!==handoff.summary){
    throw new Error('UNIVERSAL_PROJECT_STATE_WRITE_FAILED');
  }
  if(JSON.stringify(writtenState?.job_refs)!==JSON.stringify([jobRef]))throw new Error('UNIVERSAL_PROJECT_JOB_POINTER_FAILED');

  const claudeToken=String(clients.claude);
  const bootstrap=await requestJson(fetchImpl,endpoint,`/brain/bootstrap?project_id=${encodeURIComponent(projectId)}`,{clientId:'claude',token:claudeToken,method:'GET'});
  sanitizeCheck(bootstrap,clients);
  const bootState=bootstrap?.project?.state;
  if(bootstrap?.ok!==true||bootstrap?.clientId!=='claude'||bootstrap?.sourceSha!==expected||bootstrap?.project?.initialized!==true||bootState?.project_id!==projectId||bootState?.version!==writtenState.version||bootState?.updated_by!=='chatgpt'||bootState?.latest_handoff?.summary!==handoff.summary||JSON.stringify(bootstrap?.jobRefs)!==JSON.stringify([jobRef])){
    throw new Error('UNIVERSAL_PROJECT_BOOTSTRAP_FAILED');
  }

  const staleBody={...updateBody,active_phase:'stale-write-must-not-land',status:'stale-write-must-not-land'};
  const stale=await requestJsonStatus(fetchImpl,endpoint,'/brain/project/state',{clientId:'claude',token:claudeToken,method:'PUT',body:staleBody});
  sanitizeCheck(stale.value,clients);
  if(stale.status!==409||stale.value?.ok!==false||stale.value?.error!=='project_state_conflict'||stale.value?.currentVersion!==writtenState.version){
    throw new Error('UNIVERSAL_PROJECT_STALE_WRITE_NOT_BLOCKED');
  }

  const isolationProjectId=`isolation-${suffix}`;
  const isolated=await requestJsonStatus(fetchImpl,endpoint,`/brain/project/state?project_id=${encodeURIComponent(isolationProjectId)}`,{clientId:'claude',token:claudeToken,method:'GET'});
  sanitizeCheck(isolated.value,clients);
  if(isolated.status===200){
    const isolatedState=isolated.value?.state;
    const isolatedText=JSON.stringify(isolated.value);
    if(isolated.value?.ok!==true||isolatedState?.project_id!==isolationProjectId||isolatedText.includes(projectId)||isolatedText.includes(handoff.summary)||isolatedText.includes(jobRef.job_id)){
      throw new Error('UNIVERSAL_PROJECT_ISOLATION_FAILED');
    }
  }else if(!(isolated.status===404&&isolated.value?.error==='project_not_initialized')){
    throw new Error('UNIVERSAL_PROJECT_ISOLATION_FAILED');
  }

  return Object.freeze({
    ok:true,
    sourceSha:expected,
    adapters:[...USER_ADAPTERS],
    highRiskFailClosed:true,
    projectContinuity:true,
    staleWriteBlocked:true,
    projectIsolation:true,
    projectId,
    isolationProjectId,
    projectVersion:writtenState.version,
    frontDoor:Object.freeze({
      backendReady:true,
      clientAdapterReady:true,
      newSessionResumePass:true,
      versionConflict409Pass:true,
      // Repository-side adapters authenticate service principals. They cannot
      // prove that a native ChatGPT account has been authorized on the platform.
      accountIntegrationProven:false,
      ready:false,
      blockingReason:'native_account_authorization_not_proven',
    }),
  });
}

async function main(){
  const clients={
    chatgpt:String(process.env.BRAIN_CLIENT_CHATGPT_TOKEN||''),
    claude:String(process.env.BRAIN_CLIENT_CLAUDE_TOKEN||''),
    gemini:String(process.env.BRAIN_CLIENT_GEMINI_TOKEN||''),
  };
  const result=await runUniversalCanary({
    baseUrl:process.env.WORKER_BASE_URL,
    sourceSha:process.env.SKILL_GATEWAY_SOURCE_SHA||process.env.GITHUB_SHA,
    clients,
  });
  console.log(`UNIVERSAL_BRAIN_HEALTH=PASS sourceSha=${result.sourceSha}`);
  console.log(`UNIVERSAL_ADAPTER_CANARY=PASS ${result.adapters.join(' ')}`);
  console.log('UNIVERSAL_HIGH_RISK_FAIL_CLOSED=PASS');
  console.log(`UNIVERSAL_PROJECT_CONTINUITY=PASS projectId=${result.projectId} version=${result.projectVersion} staleWriteBlocked=${result.staleWriteBlocked}`);
  console.log(`UNIVERSAL_PROJECT_ISOLATION=PASS projectId=${result.projectId} isolatedProjectId=${result.isolationProjectId}`);
  console.log('FRONT_DOOR_BACKEND_READY=PASS');
  console.log('CLIENT_ADAPTER_READY=PASS');
  console.log('NEW_SESSION_RESUME_PASS=PASS');
  console.log('VERSION_CONFLICT_409_PASS=PASS');
  console.log('ACCOUNT_INTEGRATION_PROVEN=FALSE reason=native_account_authorization_not_proven');
  console.log('FRONT_DOOR_READY=FALSE reason=native_account_authorization_not_proven');
}

if(import.meta.url===`file://${process.argv[1]}`){
  main().catch(error=>{console.error(String(error?.message||error));process.exit(1);});
}
