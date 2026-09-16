import {authenticateAdapter,requiredScopeForPath,UNIVERSAL_INTERNAL_CLIENT_IDS,UNIVERSAL_USER_CLIENT_IDS} from './universal-auth.js';
import {classifyEntrySafety,effectiveProfile,normalizeUniversalRequest} from './universal-entry-contract.js';
import {createStateStores} from './universal-state.js';
import {recordUniversalEvent} from './universal-telemetry.js';

const MAX_BODY_BYTES=64_000;
const encoder=new TextEncoder();
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const ROUTE_FIELDS=new Set(['text','request_id','session_id','project_hint','freshness','declared_capabilities','tool_classes','data_class','requested_action_class']);

async function parseBody(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('body_too_large');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('body_too_large');
  const value=JSON.parse(text);
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('invalid_body');
  if(Object.keys(value).some(key=>!ROUTE_FIELDS.has(key)))throw new Error('invalid_field');
  return value;
}

function publicCapsule(capsule){
  if(!capsule)return null;
  return {
    skill_id:capsule.skill_id,
    domain:capsule.domain,
    output_contract:capsule.output_contract,
    permissions:Array.isArray(capsule.permissions)?[...capsule.permissions]:[],
    risk_ceiling:capsule.risk_ceiling,
    capsule_hash:capsule.capsule_hash,
    tools:Array.isArray(capsule.tools)?[...capsule.tools]:[],
    sources:Array.isArray(capsule.sources)?[...capsule.sources]:[],
  };
}

export function createUniversalEntryHandler({snapshot,routeSkill}={}){
  if(!snapshot||snapshot.schema_version!==1||typeof snapshot.source_sha!=='string')throw new Error('UNIVERSAL_ENTRY_SNAPSHOT_REQUIRED');
  if(typeof routeSkill!=='function')throw new Error('UNIVERSAL_ENTRY_ROUTE_SKILL_REQUIRED');
  return async function handleUniversalEntry(request,env={},ctx={}){
    const url=new URL(request.url);
    const supported=new Set(['/brain/universal/route','/brain/universal/health','/brain/universal/capabilities']);
    if(!supported.has(url.pathname))return null;
    const requiredScope=requiredScopeForPath(url.pathname,request.method);
    if(!requiredScope)return json({ok:false,error:'method_not_allowed'},405);
    const auth=await authenticateAdapter(request,env,requiredScope);
    if(!auth.ok)return json({ok:false,error:auth.error},auth.status);

    if(url.pathname==='/brain/universal/health'){
      return json({
        ok:true,
        service:'universal-brain-entry',
        brainAuthority:'GITHUB_BRAIN_V4',
        routingAuthority:false,
        reasoningAuthority:false,
        sourceSha:snapshot.source_sha,
        releaseId:snapshot.release_id||null,
        fastZeroRtt:true,
        fastExternalRoutingCalls:0,
        sharedStateRequiredForFast:false,
      });
    }
    if(url.pathname==='/brain/universal/capabilities'){
      return json({
        ok:true,
        brainAuthority:'GITHUB_BRAIN_V4',
        adapters:[...UNIVERSAL_USER_CLIENT_IDS],
        userAdapters:[...UNIVERSAL_USER_CLIENT_IDS],
        internalPrincipals:[...UNIVERSAL_INTERNAL_CLIENT_IDS],
        profiles:['FAST','STANDARD','DEEP'],
        futureAdapterWithoutBrainCoreChange:true,
        paidFallback:false,
        permissionWidening:false,
      });
    }

    let raw;
    try{raw=await parseBody(request);}catch{return json({ok:false,error:'invalid_universal_entry_request'},400);}
    let normalized;
    try{normalized=normalizeUniversalRequest(raw,auth.principal.clientId,'1.0');}catch{return json({ok:false,error:'invalid_universal_entry_request'},400);}
    const safety=classifyEntrySafety(normalized);
    let canonicalRoute;
    try{canonicalRoute=routeSkill({text:normalized.text});}catch(error){
      return json({ok:false,error:'brain_route_failed',detail:String(error?.message||error).slice(0,120)},503);
    }
    const profile=effectiveProfile(canonicalRoute.profile,safety.profileFloor);
    const route={...canonicalRoute,profile,safetyEscalated:profile!==canonicalRoute.profile};
    const capsule=publicCapsule(snapshot.capsules?.[route.primarySkill]);
    if(!capsule)return json({ok:false,error:'brain_capsule_missing'},503);

    if(profile!=='FAST'&&typeof ctx?.waitUntil==='function'){
      const stores=createStateStores(env);
      ctx.waitUntil(recordUniversalEvent(stores,{
        event_type:'route',
        client_id:auth.principal.clientId,
        request_id:normalized.request_id,
        profile,
        domain:route.domain,
        primary_skill:route.primarySkill,
        capsule_hash:route.capsuleHash,
        release_id:snapshot.release_id||null,
        source_sha:snapshot.source_sha,
        latency_ms:route.routeLatencyMs,
        status:'ok',
      }));
    }

    return json({
      ok:true,
      clientId:auth.principal.clientId,
      requestId:normalized.request_id,
      profile,
      canonicalProfile:canonicalRoute.profile,
      onlineBrainRequired:profile!=='FAST',
      safeDegradedAllowed:safety.safeDegradedAllowed,
      degraded:false,
      degradedReason:null,
      sourceSha:snapshot.source_sha,
      releaseId:snapshot.release_id||null,
      route,
      capsule,
    });
  };
}
