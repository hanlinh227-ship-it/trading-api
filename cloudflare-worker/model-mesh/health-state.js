const HEALTH_KEY_PREFIX='brain:model-mesh:health:v1:';
const HEALTH_OBJECT_NAME='model-mesh-health-v1';
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

function validHealthKey(key){return typeof key==='string'&&key.startsWith(HEALTH_KEY_PREFIX)&&key.length>HEALTH_KEY_PREFIX.length;}
function internalRequest(path,body){return new Request(`https://model-mesh-health.internal${path}`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});}

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
    async put(key,value,options={}){
      const expirationTtl=Number(options?.expirationTtl)||0;
      const response=await stub.fetch(internalRequest('/put',{key,value,expirationTtl}));
      if(!response.ok)throw new Error(`MODEL_MESH_HEALTH_PUT_FAILED:${response.status}`);
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
      const expiresAt=expirationTtl>0?Date.now()+Math.ceil(expirationTtl*1000):0;
      await this.storage.put(key,{value:body.value,expiresAt});
      return json({ok:true});
    }

    return json({ok:false,error:'not_found'},404);
  }
}
