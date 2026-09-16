import {authenticateAdapter,requiredScopeForPath} from './universal-auth.js';
import {createStateStores} from './universal-state.js';
import {promoteMemoryCandidate,reviewMemoryCandidate} from './memory-lifecycle.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const MAX_BODY_BYTES=32_000;
const encoder=new TextEncoder();
const REVIEW_FIELDS=new Set(['candidate_id','evidence_count','current','conflict','reviewed_at']);
const QUERY_FIELDS=new Set(['domain','scope','profile','query','limit','query_vector']);

async function parse(request,allowed){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('body_too_large');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('body_too_large');
  const value=JSON.parse(text);
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('invalid_body');
  if(Object.keys(value).some(key=>!allowed.has(key)))throw new Error('invalid_field');
  return value;
}
function clean(value,name,max){
  if(typeof value!=='string'||!value.trim()||value.length>max)throw new Error(`invalid_${name}`);
  return value.trim();
}
function tokens(text){
  return new Set(String(text||'').toLocaleLowerCase('und').normalize('NFKC').split(/[^\p{L}\p{N}_-]+/u).filter(x=>x.length>1).slice(0,128));
}
function lexicalScore(query,content){
  const q=tokens(query),c=tokens(content);if(!q.size||!c.size)return 0;
  let hit=0;for(const token of q)if(c.has(token))hit++;
  return hit/q.size;
}
function publicMemory(row){
  return {
    memory_id:row.memory_id,
    domain:row.domain,
    scope:row.scope,
    content:row.content,
    source:row.source,
    confidence:row.confidence,
    created_at:row.created_at,
    last_verified:row.last_verified,
    evidence_refs:Array.isArray(row.evidence_refs)?[...row.evidence_refs]:[],
    provenance:row.provenance||null,
  };
}

export function createMemoryContextHandler(){
  return async function handleMemoryContext(request,env={}){
    const url=new URL(request.url);
    if(!['/brain/memory/review','/brain/context/query'].includes(url.pathname))return null;
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    const scope=requiredScopeForPath(url.pathname,request.method);
    const auth=await authenticateAdapter(request,env,scope);
    if(!auth.ok)return json({ok:false,error:auth.error},auth.status);
    const stores=createStateStores(env);
    if(!stores.metadata.available)return json({ok:false,error:'shared_state_unavailable'},503);

    if(url.pathname==='/brain/memory/review'){
      if(auth.principal.clientId!=='evergreen'||auth.principal.principalType!=='internal')return json({ok:false,error:'scope_denied'},403);
      let body;try{body=await parse(request,REVIEW_FIELDS);}catch{return json({ok:false,error:'invalid_memory_review'},400);}
      let candidateId;try{candidateId=clean(body.candidate_id,'candidate_id',160);}catch{return json({ok:false,error:'invalid_memory_review'},400);}
      const candidate=await stores.metadata.get(`candidate:${candidateId}`);
      if(candidate?.unavailable)return json({ok:false,error:'shared_state_unavailable'},503);
      if(!candidate)return json({ok:false,error:'candidate_not_found'},404);
      // Lifecycle: only candidate -> {confirmed, rejected, needs_reverify} and
      // needs_reverify -> {confirmed, rejected} are reviewer transitions. A confirmed record is
      // never re-reviewed (it would either re-promote or flip to rejected while its promoted
      // memory stays active) and a rejected one is never resurrected.
      const reviewableStates=new Set(['candidate','needs_reverify']);
      if(!reviewableStates.has(String(candidate.state||'candidate')))return json({ok:false,error:'candidate_not_reviewable',candidateId,state:String(candidate.state)},409);
      const evidenceCount=Number(body.evidence_count);
      if(!Number.isInteger(evidenceCount)||evidenceCount<0||evidenceCount>1000||typeof body.current!=='boolean'||typeof body.conflict!=='boolean')return json({ok:false,error:'invalid_memory_review'},400);
      const review=reviewMemoryCandidate(candidate,{evidence_count:evidenceCount,current:body.current,conflict:body.conflict,reviewed_at:typeof body.reviewed_at==='string'?body.reviewed_at:undefined});
      if(review.decision==='confirmed'){
        let memory;try{memory=promoteMemoryCandidate(candidate,review);}catch{return json({ok:false,error:'memory_promotion_blocked'},409);}
        const memoryKey=`memory:${memory.domain}:${memory.scope}:${memory.memory_id}`;
        const stored=await stores.metadata.put(memoryKey,memory);
        if(stored?.unavailable)return json({ok:false,error:'shared_state_unavailable'},503);
        await stores.metadata.put(`candidate:${candidateId}`,{...candidate,state:'confirmed',active:true,reviewed_at:review.reviewed_at,promoted_memory_key:memoryKey,stable_write:false});
        return json({ok:true,candidateId,decision:'confirmed',state:'active',memoryId:memory.memory_id},200);
      }
      await stores.metadata.put(`candidate:${candidateId}`,{...candidate,state:review.decision,active:false,reviewed_at:String(body.reviewed_at||new Date().toISOString()),stable_write:false});
      return json({ok:true,candidateId,decision:review.decision,state:review.decision},200);
    }

    let body;try{body=await parse(request,QUERY_FIELDS);}catch{return json({ok:false,error:'invalid_context_query'},400);}
    let domain,scopeName,query;try{
      domain=clean(body.domain,'domain',80);scopeName=clean(body.scope,'scope',160);query=clean(body.query,'query',2000);
    }catch{return json({ok:false,error:'invalid_context_query'},400);}
    const profile=String(body.profile||'').trim().toUpperCase();
    if(profile==='FAST')return json({ok:false,error:'fast_memory_preload_forbidden'},400);
    const max=profile==='STANDARD'?4:profile==='DEEP'?8:0;
    if(!max)return json({ok:false,error:'invalid_context_profile'},400);
    const limit=body.limit===undefined?max:Number(body.limit);
    if(!Number.isInteger(limit)||limit<1||limit>max)return json({ok:false,error:'invalid_context_limit'},400);
    const prefix=`memory:${domain}:${scopeName}:`;
    const listed=await stores.metadata.list(prefix,100);
    if(listed?.unavailable)return json({ok:false,error:'shared_state_unavailable'},503);
    let candidates=(listed.items||[]).map(item=>item.value).filter(row=>row&&row.active===true&&row.state==='active'&&row.domain===domain&&row.scope===scopeName&&row.non_sensitive===true&&row.verified===true&&Number(row.confidence)>=0.55);
    candidates=candidates.map(row=>({row,score:lexicalScore(query,row.content)})).sort((a,b)=>b.score-a.score||Number(b.row.confidence)-Number(a.row.confidence)||String(b.row.last_verified).localeCompare(String(a.row.last_verified)));
    let selected=candidates.filter(x=>x.score>0).slice(0,limit).map(x=>x.row);
    let retrievalMode=selected.length?'lexical':'none';
    if(!selected.length&&stores.vector.available&&Array.isArray(body.query_vector)&&body.query_vector.length){
      const vector=await stores.vector.query(body.query_vector,{topK:limit,filter:{domain,scope:scopeName,state:'active'}});
      if(!vector?.unavailable){
        const resolved=[];
        for(const match of vector.items||[]){
          const memoryKey=String(match?.metadata?.memory_key||'');
          if(!memoryKey.startsWith(prefix))continue;
          const row=await stores.metadata.get(memoryKey);
          if(row&&row.active===true&&row.state==='active'&&row.domain===domain&&row.scope===scopeName&&row.non_sensitive===true&&row.verified===true&&Number(row.confidence)>=0.55)resolved.push(row);
          if(resolved.length>=limit)break;
        }
        selected=resolved;retrievalMode=selected.length?'vector':'none';
      }
    }
    return json({ok:true,profile,domain,scope:scopeName,retrievalMode,count:selected.length,items:selected.slice(0,limit).map(publicMemory)});
  };
}
