const HEALTH_KEY_PREFIX='brain:model-mesh:health:v1:';
const HEALTH_OBJECT_NAME='model-mesh-health-v1';
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

function validHealthKey(key){return typeof key==='string'&&key.startsWith(HEALTH_KEY_PREFIX)&&key.length>HEALTH_KEY_PREFIX.length;}
function internalRequest(path,body){return new Request(`https://model-mesh-health.internal${path}`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});}

// How many stored rows one opportunistic sweep may examine. Evidence is keyed
// per source revision, so every deploy leaves the previous revision's rows
// behind; nothing reads them again, so nothing would ever delete them. The
// sweep is bounded so a large store can never turn one put into a long request.
const SWEEP_LIMIT=128;

function createStrongHealthStore(namespace){
  const id=namespace.idFromName(HEALTH_OBJECT_NAME);
  const stub=namespace.get(id);
  return {
    kind:'DURABLE_OBJECT_STRONG',
    async get(key){
      const response=await stub.fetch(internalRequest('/get',{key}));
      if(!response.ok)throw new Error(`MODEL_MESH_HEALTH_GET_FAILED:${response.status}`);
      const body=await response.json();
      return typeof body?.value==='string'?body.value:null;
    },
    // Returns the OUTCOME of the write, not void. A writer that is told only
    // "no exception" cannot tell "my observation is now the record" from "a
    // newer observation was already there and mine was refused" - and those
    // are two different facts that this store must never let share one answer.
    async put(key,value,options={}){
      const expirationTtl=Number(options?.expirationTtl)||0;
      const observedAt=Number(options?.observedAtMs);
      const response=await stub.fetch(internalRequest('/put',{key,value,expirationTtl,observedAt:Number.isFinite(observedAt)?observedAt:null}));
      if(!response.ok)throw new Error(`MODEL_MESH_HEALTH_PUT_FAILED:${response.status}`);
      const body=await response.json();
      return {stored:body?.stored!==false,reason:body?.reason||null,guardEnforced:true};
    },
  };
}

export function resolveModelHealthStore(env={}){
  const namespace=env?.MODEL_MESH_HEALTH;
  if(namespace&&typeof namespace.idFromName==='function'&&typeof namespace.get==='function')return createStrongHealthStore(namespace);
  return env?.TRADING_STATE||null;
}

export class ModelMeshHealthState{
  constructor(ctx){this.storage=ctx.storage;}
  async fetch(request){
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
    const key=body?.key;
    if(!validHealthKey(key))return json({ok:false,error:'invalid_health_key'},400);

    const url=new URL(request.url);
    if(url.pathname==='/get'){
      const row=await this.storage.get(key);
      if(!row)return json({value:null});
      if(Number(row?.expiresAt)||0){
        if(Number(row.expiresAt)<=Date.now()){
          await this.storage.delete(key);
          return json({value:null});
        }
      }
      return json({value:typeof row?.value==='string'?row.value:null});
    }

    if(url.pathname==='/put'){
      if(typeof body?.value!=='string')return json({ok:false,error:'invalid_health_value'},400);
      const expirationTtl=Math.max(0,Number(body?.expirationTtl)||0);
      const now=Date.now();
      const expiresAt=expirationTtl>0?now+Math.ceil(expirationTtl*1000):0;
      const observedAt=Number.isFinite(Number(body?.observedAt))?Number(body.observedAt):null;

      // The whole point of putting this in the Durable Object: it is the only
      // place where read-compare-write is atomic. Two probes of the same model
      // can overlap - the Worker's own cron, the authenticated deploy probe and
      // the opportunistic self-heal probe are three independent paths - and
      // under a plain last-writer-wins store the SLOWEST probe wins rather than
      // the LATEST one. That is how a provider that a probe had just observed
      // LIVE_HEALTHY could read back as unavailable moments later, with no
      // amount of re-reading able to fix it, because the losing write had
      // already destroyed the winning evidence.
      if(observedAt!==null){
        const current=await this.storage.get(key);
        const currentObservedAt=Number(current?.observedAt);
        const currentLive=!current?.expiresAt||Number(current.expiresAt)>now;
        if(currentLive&&Number.isFinite(currentObservedAt)&&currentObservedAt>observedAt){
          return json({ok:true,stored:false,reason:'superseded_by_newer_observation'});
        }
      }

      await this.storage.put(key,{value:body.value,expiresAt,observedAt});
      await this.sweepExpired(now);
      return json({ok:true,stored:true});
    }

    return json({ok:false,error:'not_found'},404);
  }

  /**
   * Delete a bounded batch of rows whose TTL has passed.
   *
   * Evidence is keyed per source revision, so a row belonging to a superseded
   * revision is never read again - and `/get`'s lazy delete only ever fires on
   * a read. Without this the store would grow by one row per model per deploy,
   * for ever.
   */
  async sweepExpired(nowMs){
    let rows;
    try{rows=await this.storage.list({prefix:HEALTH_KEY_PREFIX,limit:SWEEP_LIMIT});}catch{return 0;}
    const expired=[];
    for(const [key,row] of rows){
      const expiresAt=Number(row?.expiresAt)||0;
      if(expiresAt&&expiresAt<=nowMs)expired.push(key);
    }
    if(!expired.length)return 0;
    try{await this.storage.delete(expired);}catch{return 0;}
    return expired.length;
  }
}
