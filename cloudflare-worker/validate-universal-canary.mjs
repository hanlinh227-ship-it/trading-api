// The real fetch, captured once at module load. `fetchImpl=fetch` used to
// resolve globalThis.fetch at call time, so preloading a fake fetch with
// `node --import` let main() write live-production evidence having made no
// network request at all. Only this exact function counts as the live path.
//
// What this does NOT stop: a preload that replaces globalThis.fetch *before*
// this module is evaluated is captured here as the real one. Node offers no
// portable handle on the built-in fetch to compare against - it is ordinary
// JavaScript, not `[native code]` - so the remaining guarantee is that a fetch
// injected through the `fetchImpl` argument, which is how the tests and any
// in-process caller do it, can no longer produce live-production evidence.
const REAL_FETCH=fetch;

const USER_ADAPTERS=Object.freeze(['chatgpt','claude','gemini']);
const FORBIDDEN_RESPONSE_TERMS=Object.freeze(['chainOfThought','hidden_reasoning','chain_of_thought','raw_private_payload','raw_private_tool_payload']);
const CANARY_NONCE_PARAM='__canary_nonce';
const CANARY_NONCE_MAX_LENGTH=64;
const CANARY_NONCE_PATTERN=/^[A-Za-z0-9._:-]+$/;

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
function generateCanaryNonce(){
  const cryptoObj=globalThis.crypto;
  if(cryptoObj&&typeof cryptoObj.randomUUID==='function'){
    try{
      const uuid=String(cryptoObj.randomUUID());
      if(uuid)return uuid;
    }catch{}
  }
  const stamp=Date.now().toString(36);
  let randomPart='';
  if(cryptoObj&&typeof cryptoObj.getRandomValues==='function'){
    try{
      const bytes=new Uint8Array(16);
      cryptoObj.getRandomValues(bytes);
      randomPart=Array.from(bytes,byte=>byte.toString(16).padStart(2,'0')).join('');
    }catch{}
  }
  // There is no pseudo-random fallback here any more. It was not a CSPRNG,
  // this branch is unreachable on Node >= 18, and a cache-busting nonce that
  // is merely probably unique is one nobody can rely on. It fails loudly.
  if(!randomPart)throw new Error('UNIVERSAL_CANARY_NONCE_UNAVAILABLE');
  return `canary-${stamp}-${randomPart}`;
}
function cleanCanaryNonce(value){
  const text=String(value===undefined||value===null?'':value).trim();
  if(!text)throw new Error('UNIVERSAL_CANARY_NONCE_REQUIRED');
  if(text.length>CANARY_NONCE_MAX_LENGTH)throw new Error('UNIVERSAL_CANARY_NONCE_INVALID');
  if(!CANARY_NONCE_PATTERN.test(text))throw new Error('UNIVERSAL_CANARY_NONCE_INVALID');
  return text;
}
function withCanaryNonce(path,nonce){
  const text=String(path||'');
  const hashIndex=text.indexOf('#');
  const hash=hashIndex>=0?text.slice(hashIndex):'';
  const withoutHash=hashIndex>=0?text.slice(0,hashIndex):text;
  const queryIndex=withoutHash.indexOf('?');
  const base=queryIndex>=0?withoutHash.slice(0,queryIndex):withoutHash;
  const query=queryIndex>=0?withoutHash.slice(queryIndex+1):'';
  const params=new URLSearchParams(query);
  params.set(CANARY_NONCE_PARAM,nonce);
  return `${base}?${params.toString()}${hash}`;
}
//: Cloudflare's own word for what it did with the request. A HIT means a
// cached response answered, so nothing was bypassed; anything else, with no
// non-zero Age, is a response that was not served from cache.
const CACHED_RESPONSE_STATES=Object.freeze(['HIT','STALE','UPDATING','REVALIDATED']);

function observeCacheHeaders(response){
  let cacheStatus=null;
  let age=null;
  try{
    cacheStatus=response?.headers?.get?.('cf-cache-status')??null;
    age=response?.headers?.get?.('age')??null;
  }catch{}
  return {
    cacheStatus:cacheStatus===null||cacheStatus===undefined?null:String(cacheStatus).trim().toUpperCase(),
    age:age===null||age===undefined?null:String(age).trim(),
  };
}

// cache_bypass_proven used to be asserted from the request side only - a nonce
// in the query string and a no-store header - and no response was ever looked
// at. A request that asks not to be cached is not a response that was not
// cached. This is the observation that earns the claim.
export function cacheBypassFromObservations(observations){
  if(!Array.isArray(observations)||observations.length===0)return false;
  return observations.every(observation=>{
    if(!observation||typeof observation!=='object')return false;
    const status=observation.cacheStatus;
    if(typeof status!=='string'||status.length===0)return false;
    if(CACHED_RESPONSE_STATES.includes(status))return false;
    const age=observation.age;
    if(age===null||age===undefined)return true;
    return String(age).trim()==='0';
  });
}

async function requestJsonStatus(fetchImpl,baseUrl,path,{clientId,token,body,method,nonce,observations}={}){
  const headers={
    'x-brain-client':clientId,
    authorization:`Bearer ${token}`,
    'cache-control':'no-store',
    pragma:'no-cache',
    'x-canary-nonce':nonce,
  };
  const init={method:method||(body===undefined?'GET':'POST'),headers};
  if(body!==undefined){headers['content-type']='application/json';init.body=JSON.stringify(body);}
  const response=await fetchImpl(`${baseUrl}${withCanaryNonce(path,nonce)}`,init);
  if(Array.isArray(observations))observations.push(observeCacheHeaders(response));
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

// What this run proves whatever fetch carried it: these are statements about
// the worker's behaviour, and a mocked transport still exercises them.
const TRANSPORT_INDEPENDENT_PROOFS=Object.freeze([
  'project-state round trip proven with versioned write and read-back',
  'fresh Claude bootstrap/resume proven from persisted project state',
  'stale-version 409 conflict proven to block stale writes',
  'project isolation proven across distinct project_id namespaces',
]);

//: Earned only by a run that went out over the real fetch.
const LIVE_CANARY_PROOF=
  'live production service-principal canary executed against the deployed worker';
//: Earned only by a run whose responses were observed not to come from cache.
const CACHE_BYPASS_PROOF=
  'cache bypass observed response-side: every response carried a non-cached '
  +'cf-cache-status and no non-zero Age, under per-run __canary_nonce and no-store';

export function buildLiveProductionEvidence(result){
  // Derived from what ran, never asserted beside it. This function used to
  // hard-code live_canary_pass and cache_bypass_proven to true while the
  // result object it was built next to said false for both - the evidence
  // contradicted its own source, and an injected fetch was indistinguishable
  // from a deployed worker.
  if(!result||typeof result!=='object')throw new Error('UNIVERSAL_CANARY_EVIDENCE_RESULT_REQUIRED');
  const sourceSha=cleanSha(result.sourceSha);
  const frontDoor=result.frontDoor||{};
  const liveCanaryPass=result.usedDefaultFetch===true&&frontDoor.liveCanaryPass===true;
  const cacheBypassProven=liveCanaryPass&&frontDoor.cacheBypassProven===true;
  const proofs=[
    ...(liveCanaryPass?[LIVE_CANARY_PROOF]:[]),
    ...(cacheBypassProven?[CACHE_BYPASS_PROOF]:[]),
    ...TRANSPORT_INDEPENDENT_PROOFS,
  ].map(proof=>String(proof).trim()).filter(proof=>proof.length>0);
  if(proofs.length===0)throw new Error('UNIVERSAL_CANARY_EVIDENCE_PROOFS_REQUIRED');
  return Object.freeze({
    source_sha:sourceSha,
    gate:'FRONT_DOOR_READY',
    ready:false,
    proofs:Object.freeze(proofs),
    live_canary_pass:liveCanaryPass,
    cache_bypass_proven:cacheBypassProven,
    account_integration_proven:false,
    blocking_reason:'native_account_authorization_not_proven',
  });
}

export async function runUniversalCanary({baseUrl,sourceSha,clients,fetchImpl=REAL_FETCH,canaryNonce,requireGeneratedNonce=false}={}){
  const endpoint=cleanBaseUrl(baseUrl);
  const expected=cleanSha(sourceSha);
  // A caller-supplied constant nonce is the same nonce on every manual run,
  // which is the opposite of cache-busting. The main() path refuses one.
  if(requireGeneratedNonce&&canaryNonce!==undefined)throw new Error('UNIVERSAL_CANARY_NONCE_NOT_ACCEPTED');
  const nonce=cleanCanaryNonce(canaryNonce===undefined?generateCanaryNonce():canaryNonce);
  const usedDefaultFetch=fetchImpl===REAL_FETCH;
  const cacheObservations=[];
  if(!clients||typeof clients!=='object')throw new Error('UNIVERSAL_CANARY_CLIENTS_REQUIRED');
  for(const id of USER_ADAPTERS)if(!String(clients[id]||'').trim())throw new Error(`UNIVERSAL_CANARY_CLIENT_TOKEN_REQUIRED:${id}`);
  const primary='chatgpt';
  const primaryToken=String(clients[primary]);

  const health=await requestJson(fetchImpl,endpoint,'/brain/universal/health',{clientId:primary,token:primaryToken,nonce,observations:cacheObservations});
  sanitizeCheck(health,clients);
  if(health.ok!==true||health.brainAuthority!=='GITHUB_BRAIN_V4'||health.sourceSha!==expected||health.fastZeroRtt!==true||health.fastExternalRoutingCalls!==0){
    throw new Error('UNIVERSAL_BRAIN_HEALTH_FAILED');
  }

  const capabilities=await requestJson(fetchImpl,endpoint,'/brain/universal/capabilities',{clientId:primary,token:primaryToken,nonce,observations:cacheObservations});
  sanitizeCheck(capabilities,clients);
  const advertised=new Set(Array.isArray(capabilities.userAdapters)?capabilities.userAdapters:(Array.isArray(capabilities.adapters)?capabilities.adapters:[]));
  for(const id of USER_ADAPTERS)if(!advertised.has(id))throw new Error(`UNIVERSAL_CANARY_ADAPTER_MISSING:${id}`);
  if(capabilities.paidFallback!==false||capabilities.permissionWidening!==false)throw new Error('UNIVERSAL_CANARY_CAPABILITY_SAFETY_FAILED');

  for(const id of USER_ADAPTERS){
    const body={
      text:'explain recursion briefly',request_id:`canary-${id}`,session_id:'production-canary',freshness:'none',data_class:'PUBLIC',requested_action_class:'informational'
    };
    const routed=await requestJson(fetchImpl,endpoint,'/brain/universal/route',{clientId:id,token:String(clients[id]),body,nonce,observations:cacheObservations});
    sanitizeCheck(routed,clients);
    if(routed.ok!==true||routed.clientId!==id||routed.sourceSha!==expected)throw new Error(`UNIVERSAL_ADAPTER_ROUTE_FAILED:${id}`);
  }

  const highRisk=await requestJson(fetchImpl,endpoint,'/brain/universal/route',{
    clientId:primary,
    token:primaryToken,
    nonce,
    observations:cacheObservations,
    body:{text:'giao dịch BTC live',request_id:'canary-live',session_id:'production-canary',freshness:'live',data_class:'PUBLIC',requested_action_class:'live_or_trading'}
  });
  sanitizeCheck(highRisk,clients);
  if(highRisk.ok!==true||highRisk.profile!=='DEEP'||highRisk.onlineBrainRequired!==true||highRisk.safeDegradedAllowed!==false){
    throw new Error('UNIVERSAL_HIGH_RISK_FAIL_CLOSED_FAILED');
  }

  const suffix=expected.slice(0,12);
  const projectId=`canary-${suffix}`;
  const statePath=`/brain/project/state?project_id=${encodeURIComponent(projectId)}`;
  const initial=await requestJsonStatus(fetchImpl,endpoint,statePath,{clientId:primary,token:primaryToken,method:'GET',nonce,observations:cacheObservations});
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
  const written=await requestJsonStatus(fetchImpl,endpoint,'/brain/project/state',{clientId:primary,token:primaryToken,method:'PUT',body:updateBody,nonce,observations:cacheObservations});
  sanitizeCheck(written.value,clients);
  const writtenState=written.value?.state;
  if(written.status!==200||written.value?.ok!==true||writtenState?.project_id!==projectId||writtenState?.version!==previousVersion+1||writtenState?.updated_by!=='chatgpt'||writtenState?.latest_handoff?.summary!==handoff.summary){
    throw new Error('UNIVERSAL_PROJECT_STATE_WRITE_FAILED');
  }
  if(JSON.stringify(writtenState?.job_refs)!==JSON.stringify([jobRef]))throw new Error('UNIVERSAL_PROJECT_JOB_POINTER_FAILED');

  const claudeToken=String(clients.claude);
  const bootstrap=await requestJson(fetchImpl,endpoint,`/brain/bootstrap?project_id=${encodeURIComponent(projectId)}`,{clientId:'claude',token:claudeToken,method:'GET',nonce,observations:cacheObservations});
  sanitizeCheck(bootstrap,clients);
  const bootState=bootstrap?.project?.state;
  if(bootstrap?.ok!==true||bootstrap?.clientId!=='claude'||bootstrap?.sourceSha!==expected||bootstrap?.project?.initialized!==true||bootState?.project_id!==projectId||bootState?.version!==writtenState.version||bootState?.updated_by!=='chatgpt'||bootState?.latest_handoff?.summary!==handoff.summary||JSON.stringify(bootstrap?.jobRefs)!==JSON.stringify([jobRef])){
    throw new Error('UNIVERSAL_PROJECT_BOOTSTRAP_FAILED');
  }

  const staleBody={...updateBody,active_phase:'stale-write-must-not-land',status:'stale-write-must-not-land'};
  const stale=await requestJsonStatus(fetchImpl,endpoint,'/brain/project/state',{clientId:'claude',token:claudeToken,method:'PUT',body:staleBody,nonce,observations:cacheObservations});
  sanitizeCheck(stale.value,clients);
  if(stale.status!==409||stale.value?.ok!==false||stale.value?.error!=='project_state_conflict'||stale.value?.currentVersion!==writtenState.version){
    throw new Error('UNIVERSAL_PROJECT_STALE_WRITE_NOT_BLOCKED');
  }

  const isolationProjectId=`isolation-${suffix}`;
  const isolated=await requestJsonStatus(fetchImpl,endpoint,`/brain/project/state?project_id=${encodeURIComponent(isolationProjectId)}`,{clientId:'claude',token:claudeToken,method:'GET',nonce,observations:cacheObservations});
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

  const cacheBypassObserved=cacheBypassFromObservations(cacheObservations);
  return Object.freeze({
    ok:true,
    sourceSha:expected,
    // What carried this run, so nothing downstream has to guess.
    usedDefaultFetch,
    cacheBypassObserved,
    cacheObservations:Object.freeze(cacheObservations.map(o=>Object.freeze({...o}))),
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
      // Derived, not declared. This function is mockable and may run against
      // an injected fetchImpl, so it says which one carried the run rather
      // than asserting a constant beside a result that contradicts it.
      liveCanaryPass:usedDefaultFetch,
      cacheBypassProven:usedDefaultFetch&&cacheBypassObserved,
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
  if(String(process.env.UNIVERSAL_CANARY_NONCE||'').trim())throw new Error('UNIVERSAL_CANARY_NONCE_NOT_ACCEPTED');
  const result=await runUniversalCanary({
    baseUrl:process.env.WORKER_BASE_URL,
    sourceSha:process.env.SKILL_GATEWAY_SOURCE_SHA||process.env.GITHUB_SHA,
    clients,
    requireGeneratedNonce:true,
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
  const evidence=buildLiveProductionEvidence(result);
  console.log(`LIVE_PRODUCTION_CANARY=${evidence.live_canary_pass?'PASS':'FALSE'}`);
  console.log(`CACHE_BYPASS_PROVEN=${evidence.cache_bypass_proven?'PASS':'FALSE'} observations=${result.cacheObservations.length}`);
  console.log('ACCOUNT_INTEGRATION_PROVEN=FALSE reason=native_account_authorization_not_proven');
  console.log('FRONT_DOOR_READY=FALSE reason=native_account_authorization_not_proven');

  const outputPath=String(process.env.FRONT_DOOR_EVIDENCE_OUTPUT||'').trim();
  if(outputPath){
    const {writeFileSync,renameSync}=await import('node:fs');
    const {randomUUID}=await import('node:crypto');
    const tempPath=`${outputPath}.${randomUUID()}.tmp`;
    writeFileSync(tempPath,`${JSON.stringify(evidence,null,2)}\n`,'utf8');
    renameSync(tempPath,outputPath);
  }
}

if(import.meta.url===`file://${process.argv[1]}`){
  main().catch(error=>{console.error(String(error?.message||error));process.exit(1);});
}
