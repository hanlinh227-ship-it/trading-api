import {routeSkillRequest} from '../../cloudflare-worker/skill-gateway.js';
import {classifyEntrySafety,degradedDecision,effectiveProfile,normalizeUniversalRequest} from '../../cloudflare-worker/universal-entry-contract.js';

const SHA_RE=/^[0-9a-f]{40}$/;

function verifiedSnapshot(snapshot){
  return Boolean(snapshot&&snapshot.schema_version===1&&SHA_RE.test(String(snapshot.source_sha||''))&&typeof snapshot.release_id==='string'&&snapshot.release_id&&snapshot.capsules&&typeof snapshot.capsules==='object');
}
function endpointUrl(base,path){return `${String(base||'').replace(/\/$/,'')}${path}`;}
function requestBody(value){return JSON.stringify(value);}
function publicCapsule(snapshot,skillId){
  const c=snapshot?.capsules?.[skillId];if(!c)return null;
  return {skill_id:c.skill_id,domain:c.domain,output_contract:c.output_contract,permissions:Array.isArray(c.permissions)?[...c.permissions]:[],risk_ceiling:c.risk_ceiling,capsule_hash:c.capsule_hash,tools:Array.isArray(c.tools)?[...c.tools]:[],sources:Array.isArray(c.sources)?[...c.sources]:[]};
}
function normalizeForClient(request,clientId){return normalizeUniversalRequest(request,clientId,'sdk-1.0');}

export function createBrainAdapter({clientId,token,endpoint,hotSnapshot,stableSnapshot=null,fetchImpl=globalThis.fetch}={}){
  clientId=String(clientId||'').trim().toLowerCase();
  token=String(token||'');
  endpoint=String(endpoint||'').trim();
  if(!clientId||!token||!endpoint)throw new Error('brain_adapter_configuration_required');
  if(typeof fetchImpl!=='function')throw new Error('brain_adapter_fetch_required');

  async function cloud(path,payload){
    const response=await fetchImpl(endpointUrl(endpoint,path),{method:'POST',headers:{'x-brain-client':clientId,authorization:`Bearer ${token}`,'content-type':'application/json'},body:requestBody(payload)});
    let body=null;try{body=await response.json();}catch{}
    if(!response.ok)throw new Error(String(body?.error||`brain_http_${response.status}`));
    return body;
  }

  function localRoute(request,snapshot,{degraded=false,degradedReason=null}={}){
    if(!verifiedSnapshot(snapshot))throw new Error('verified_brain_snapshot_required');
    const normalized=normalizeForClient(request,clientId);
    const safety=classifyEntrySafety(normalized);
    const canonical=routeSkillRequest({text:normalized.text},snapshot);
    const profile=effectiveProfile(canonical.profile,safety.profileFloor);
    const capsule=publicCapsule(snapshot,canonical.primarySkill);
    if(!capsule)throw new Error('brain_capsule_missing');
    return {ok:true,clientId,requestId:normalized.request_id,profile,canonicalProfile:canonical.profile,onlineBrainRequired:profile!=='FAST',safeDegradedAllowed:safety.safeDegradedAllowed,degraded,degradedReason,sourceSha:snapshot.source_sha,releaseId:snapshot.release_id,route:{...canonical,profile,safetyEscalated:profile!==canonical.profile},capsule,local:true};
  }

  return Object.freeze({
    clientId,
    async route(request){
      const normalized=normalizeForClient(request,clientId);
      const safety=classifyEntrySafety(normalized);
      if(verifiedSnapshot(hotSnapshot)){
        const local=localRoute(request,hotSnapshot);
        if(local.profile==='FAST')return local;
      }
      try{return await cloud('/brain/universal/route',request);}catch(error){
        const decision=degradedDecision({classification:safety,stableSnapshotAvailable:verifiedSnapshot(stableSnapshot)});
        if(!decision.allowed)throw new Error(`brain_unavailable_fail_closed:${String(error?.message||error)}`);
        const fallback=localRoute(request,stableSnapshot,{degraded:true,degradedReason:'cloud_brain_unavailable'});
        if(fallback.profile==='FAST')throw new Error('degraded_profile_contract_invalid');
        return fallback;
      }
    },
    async queryContext(request){
      const profile=String(request?.profile||'').trim().toUpperCase();
      if(profile==='FAST')throw new Error('fast_memory_preload_forbidden');
      if(!['STANDARD','DEEP'].includes(profile))throw new Error('invalid_context_profile');
      return await cloud('/brain/context/query',request);
    },
    async submitMemoryCandidate(candidate){return await cloud('/brain/memory/candidates',candidate);},
    snapshotStatus(){return {hotVerified:verifiedSnapshot(hotSnapshot),stableVerified:verifiedSnapshot(stableSnapshot),hotSourceSha:verifiedSnapshot(hotSnapshot)?hotSnapshot.source_sha:null,stableSourceSha:verifiedSnapshot(stableSnapshot)?stableSnapshot.source_sha:null};},
  });
}
