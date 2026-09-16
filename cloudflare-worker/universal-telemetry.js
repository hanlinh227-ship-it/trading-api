const ALLOWED=new Set([
  'event_type','client_id','request_id','profile','domain','primary_skill','capsule_hash','release_id','source_sha',
  'latency_ms','tool_class','provider_id','model_family','cache_outcome','retrieval_outcome','fallback_state',
  'memory_event','promotion_event','recovery_event','failure_category','verification','status','timestamp'
]);
const MAX_FIELD_CHARS=1200;
const MAX_EVENT_CHARS=20_000;

function cleanPrimitive(value,key){
  if(value===null||value===undefined)return value;
  if(typeof value==='number'||typeof value==='boolean')return value;
  if(typeof value==='string'){
    if(value.length>MAX_FIELD_CHARS)throw new Error('telemetry_field_too_large');
    return value;
  }
  if(Array.isArray(value)){
    const out=value.slice(0,24).map(item=>cleanPrimitive(item,key));
    return out;
  }
  // Nested payloads are intentionally not retained; they are where prompts,
  // tool payloads and private provider responses most often leak.
  return undefined;
}

export function sanitizeEvent(event){
  if(!event||typeof event!=='object'||Array.isArray(event))throw new Error('telemetry_event_required');
  const out={};
  for(const key of ALLOWED){
    if(!(key in event))continue;
    const value=cleanPrimitive(event[key],key);
    if(value!==undefined)out[key]=value;
  }
  if(!out.event_type)throw new Error('telemetry_event_type_required');
  out.timestamp=String(out.timestamp||new Date().toISOString());
  const raw=JSON.stringify(out);
  if(raw.length>MAX_EVENT_CHARS)throw new Error('telemetry_event_too_large');
  return Object.freeze(out);
}

function eventKey(event){
  const request=String(event.request_id||'no-request').replace(/[^a-zA-Z0-9._-]/g,'_').slice(0,120);
  const type=String(event.event_type||'event').replace(/[^a-zA-Z0-9._-]/g,'_').slice(0,80);
  const stamp=String(event.timestamp||Date.now()).replace(/[^0-9A-Za-z]/g,'').slice(0,32);
  return `telemetry:${stamp}:${request}:${type}`;
}

export async function recordUniversalEvent(stores,event){
  let safe;
  try{safe=sanitizeEvent(event);}catch(error){return {ok:false,error:String(error?.message||error)};}
  if(!stores?.metadata?.available)return {ok:false,unavailable:true};
  try{
    const result=await stores.metadata.put(eventKey(safe),safe);
    if(result?.unavailable)return {ok:false,unavailable:true};
    return {ok:true};
  }catch{return {ok:false,unavailable:true};}
}

export const UNIVERSAL_TELEMETRY_ALLOWED_FIELDS=Object.freeze([...ALLOWED]);
