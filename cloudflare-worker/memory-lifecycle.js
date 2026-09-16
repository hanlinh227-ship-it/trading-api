// Single credential-pattern list shared by candidate intake and review so the two stages can
// never disagree about what counts as a secret.
export const SENSITIVE_PATTERNS=Object.freeze([
  /api[_ -]?key\s*[:=]/i,
  /private[_ -]?key\s*[:=]/i,
  /authorization\s*:\s*bearer/i,
  /bearer\s+[a-z0-9._-]{8,}/i,
  /seed\s+phrase\s*[:=]/i,
  /authentication[_ -]?token\s*[:=]/i,
  /password\s*[:=]/i,
  /passphrase\s*[:=]/i,
  /sk-[a-z0-9_-]{8,}/i,
]);
// Every top-level string (and string-array item) of a candidate is scanned: a token in `source`
// or `evidence_refs` is stored and echoed to every client exactly like one in `content`.
export function sensitiveStrings(value){
  const out=[];
  for(const item of Object.values(value||{})){
    if(typeof item==='string')out.push(item);
    else if(Array.isArray(item))for(const inner of item)if(typeof inner==='string')out.push(inner);
  }
  return out;
}
const FORBIDDEN_FIELDS=new Set(['raw_private_chat','hidden_reasoning','chain_of_thought','secrets','credentials','api_keys','private_keys','authentication_tokens','seed_phrases','raw_private_tool_payload']);

function cleanString(value,name,max=4000){
  if(typeof value!=='string'||!value.trim()||value.length>max)throw new Error(`invalid_${name}`);
  return value.trim();
}
function cleanArray(value,name,max=24){
  if(!Array.isArray(value)||value.length>max)throw new Error(`invalid_${name}`);
  return value.map(item=>cleanString(item,name,500));
}

export function isSensitiveMemoryContent(value){
  if(!value||typeof value!=='object')return true;
  if(Object.keys(value).some(key=>FORBIDDEN_FIELDS.has(key)))return true;
  return sensitiveStrings(value).some(text=>SENSITIVE_PATTERNS.some(pattern=>pattern.test(text)));
}

function candidateGate(candidate){
  if(!candidate||typeof candidate!=='object')return {ok:false,reason:'candidate_required'};
  if(isSensitiveMemoryContent(candidate))return {ok:false,reason:'sensitive_content'};
  if(candidate.reusable!==true)return {ok:false,reason:'not_reusable'};
  if(candidate.verified!==true)return {ok:false,reason:'not_verified'};
  if(candidate.non_sensitive!==true)return {ok:false,reason:'not_non_sensitive'};
  const confidence=Number(candidate.confidence);
  if(!Number.isFinite(confidence)||confidence<0.55||confidence>1)return {ok:false,reason:'confidence_below_threshold'};
  if(!Array.isArray(candidate.evidence_refs)||candidate.evidence_refs.length<1)return {ok:false,reason:'evidence_required'};
  if(Array.isArray(candidate.conflicts_with)&&candidate.conflicts_with.length>0)return {ok:false,reason:'candidate_conflict'};
  return {ok:true};
}

export function reviewMemoryCandidate(candidate,evidence={}){
  const gate=candidateGate(candidate);
  if(!gate.ok)return Object.freeze({decision:'rejected',reason:gate.reason,evidence_count:Number(evidence?.evidence_count||0),current:evidence?.current===true,conflict:evidence?.conflict===true});
  const evidenceCount=Number(evidence?.evidence_count||0);
  if(evidence?.conflict===true)return Object.freeze({decision:'rejected',reason:'review_conflict',evidence_count:evidenceCount,current:evidence?.current===true,conflict:true});
  if(!Number.isFinite(evidenceCount)||evidenceCount<1||evidence?.current!==true)return Object.freeze({decision:'needs_reverify',reason:'insufficient_current_evidence',evidence_count:Number.isFinite(evidenceCount)?evidenceCount:0,current:evidence?.current===true,conflict:false});
  return Object.freeze({decision:'confirmed',reason:'evidence_gate_passed',evidence_count:evidenceCount,current:true,conflict:false,reviewed_at:String(evidence?.reviewed_at||new Date().toISOString())});
}

export function promoteMemoryCandidate(candidate,review){
  const gate=candidateGate(candidate);
  if(!gate.ok)throw new Error(`memory_promotion_blocked:${gate.reason}`);
  if(review?.decision!=='confirmed'||Number(review?.evidence_count||0)<1||review?.current!==true||review?.conflict===true)throw new Error('memory_promotion_blocked:review_not_confirmed');
  const candidateId=cleanString(candidate.candidate_id,'candidate_id',160);
  const domain=cleanString(candidate.domain,'domain',80);
  const scope=cleanString(candidate.scope,'scope',160);
  const evidenceRefs=cleanArray(candidate.evidence_refs,'evidence_refs');
  const conflicts=Array.isArray(candidate.conflicts_with)?cleanArray(candidate.conflicts_with,'conflicts_with'):[];
  if(conflicts.length)throw new Error('memory_promotion_blocked:candidate_conflict');
  const reviewedAt=String(review.reviewed_at||new Date().toISOString());
  return Object.freeze({
    memory_id:candidateId,
    candidate_id:candidateId,
    domain,
    scope,
    content:cleanString(candidate.content,'content',4000),
    source:cleanString(candidate.source,'source',240),
    confidence:Number(candidate.confidence),
    created_at:cleanString(candidate.created_at,'created_at',64),
    last_verified:reviewedAt,
    reviewed_at:reviewedAt,
    evidence_refs:evidenceRefs,
    provenance:{submitted_by:String(candidate.submitted_by||''),candidate_id:candidateId,evidence_refs:evidenceRefs},
    reusable:true,
    verified:true,
    non_sensitive:true,
    state:'active',
    active:true,
    superseded_by:null,
    stable_write:false,
    routing_authority:false,
    reasoning_authority:false,
  });
}

export function supersedeMemory(active,replacement){
  if(!active||active.state!=='active'||active.active!==true)throw new Error('active_memory_required');
  const replacementId=cleanString(replacement?.memory_id||replacement?.candidate_id,'replacement_id',160);
  return Object.freeze({...active,state:'superseded',active:false,superseded_by:replacementId,superseded_at:String(replacement?.last_verified||replacement?.reviewed_at||new Date().toISOString())});
}
