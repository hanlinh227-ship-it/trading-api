import {authenticateAdapter} from './universal-auth.js';
import {createStateStores} from './universal-state.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const MAX_BODY_BYTES=32_000;
const encoder=new TextEncoder();
const ALLOWED=new Set(['candidate_id','domain','scope','content','source','confidence','created_at','evidence_refs','reusable','verified','non_sensitive','conflicts_with']);
const FORBIDDEN_KEYS=new Set(['raw_private_chat','hidden_reasoning','chain_of_thought','secrets','credentials','api_keys','private_keys','authentication_tokens','seed_phrases','raw_private_tool_payload']);
const SENSITIVE=[/api[_ -]?key\s*[:=]/i,/private[_ -]?key\s*[:=]/i,/authorization\s*:\s*bearer/i,/bearer\s+[a-z0-9._-]{8,}/i,/seed\s+phrase\s*[:=]/i,/authentication[_ -]?token\s*[:=]/i];

async function parse(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('body_too_large');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('body_too_large');
  const value=JSON.parse(text);
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('invalid_body');
  if(Object.keys(value).some(key=>FORBIDDEN_KEYS.has(key)))throw new Error('forbidden_field');
  if(Object.keys(value).some(key=>!ALLOWED.has(key)))throw new Error('invalid_field');
  return value;
}

function cleanString(value,name,max=2000){
  if(typeof value!=='string'||!value.trim()||value.length>max)throw new Error(`invalid_${name}`);
  return value.trim();
}
function cleanRefs(value){
  if(!Array.isArray(value)||value.length<1||value.length>24)throw new Error('invalid_evidence_refs');
  return value.map(x=>cleanString(x,'evidence_ref',500));
}
function sensitive(value){
  const content=String(value?.content||'');
  return SENSITIVE.some(pattern=>pattern.test(content));
}

export function normalizeMemoryCandidate(value,clientId){
  if(sensitive(value))throw new Error('sensitive_content');
  const confidence=Number(value.confidence);
  if(!Number.isFinite(confidence)||confidence<0||confidence>1)throw new Error('invalid_confidence');
  const conflicts=value.conflicts_with===undefined?[]:value.conflicts_with;
  if(!Array.isArray(conflicts)||conflicts.length>24)throw new Error('invalid_conflicts');
  return Object.freeze({
    candidate_id:cleanString(value.candidate_id,'candidate_id',160),
    domain:cleanString(value.domain,'domain',80),
    scope:cleanString(value.scope,'scope',160),
    content:cleanString(value.content,'content',4000),
    source:cleanString(value.source,'source',240),
    confidence,
    created_at:cleanString(value.created_at,'created_at',64),
    evidence_refs:cleanRefs(value.evidence_refs),
    reusable:value.reusable===true,
    verified:value.verified===true,
    non_sensitive:value.non_sensitive===true,
    conflicts_with:conflicts.map(x=>cleanString(x,'conflict',160)),
    submitted_by:String(clientId||''),
    state:'candidate',
    active:false,
    stable_write:false,
  });
}

export function createMemoryCandidateHandler(){
  return async function handleMemoryCandidate(request,env={},ctx={}){
    const url=new URL(request.url);
    if(url.pathname!=='/brain/memory/candidates')return null;
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    const auth=await authenticateAdapter(request,env,'brain.submit_candidate_memory');
    if(!auth.ok)return json({ok:false,error:auth.error},auth.status);
    let raw;
    try{raw=await parse(request);}catch(error){
      const reason=String(error?.message||error);
      return json({ok:false,error:reason==='sensitive_content'?'candidate_rejected_sensitive':'invalid_memory_candidate'},400);
    }
    let candidate;
    try{candidate=normalizeMemoryCandidate(raw,auth.principal.clientId);}catch(error){
      const reason=String(error?.message||error);
      return json({ok:false,error:reason==='sensitive_content'?'candidate_rejected_sensitive':'invalid_memory_candidate'},400);
    }
    const stores=createStateStores(env);
    if(!stores.metadata.available)return json({ok:false,error:'shared_state_unavailable'},503);
    const stored=await stores.metadata.put(`candidate:${candidate.candidate_id}`,candidate);
    if(stored?.unavailable)return json({ok:false,error:'shared_state_unavailable'},503);
    if(stores.queue.available)ctx?.waitUntil?.(stores.queue.enqueue({type:'memory_candidate_review',candidate_id:candidate.candidate_id,domain:candidate.domain,scope:candidate.scope}));
    return json({ok:true,candidateId:candidate.candidate_id,state:'candidate',active:false,stableWrite:false},202);
  };
}
