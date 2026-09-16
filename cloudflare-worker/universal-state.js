const PREFIX='brain:v1:';
const META_PREFIX='brain:v1:meta:';
const unavailable=(extra={})=>({unavailable:true,...extra});

function validKey(key){
  const value=String(key||'');
  if(!value||value.length>240||value.includes('..')||/[\r\n\0]/.test(value))throw new Error('invalid_state_key');
  return value;
}
function validListPrefix(value=''){
  const text=String(value||'');
  if(text.length>200||text.includes('..')||/[\r\n\0]/.test(text))throw new Error('invalid_state_prefix');
  return text;
}
function validLimit(limit=50){
  const value=Number(limit);
  if(!Number.isInteger(value)||value<1||value>100)throw new Error('invalid_state_limit');
  return value;
}

function jsonKvStore(binding,prefix){
  if(!binding||typeof binding.get!=='function'||typeof binding.put!=='function'){
    return {
      available:false,
      async get(){return unavailable();},
      async put(){return unavailable();},
      async delete(){return unavailable();},
      async list(){return unavailable({items:[],cursor:null});},
    };
  }
  return {
    available:true,
    async get(key){
      key=validKey(key);
      try{
        const raw=await binding.get(prefix+key,'json');
        return raw===null?null:raw;
      }catch{
        try{
          const raw=await binding.get(prefix+key);
          return raw===null?null:JSON.parse(raw);
        }catch{return unavailable();}
      }
    },
    async put(key,value){
      key=validKey(key);
      if(value===undefined)throw new Error('state_value_required');
      await binding.put(prefix+key,JSON.stringify(value));
      return {ok:true};
    },
    async delete(key){
      key=validKey(key);
      if(typeof binding.delete!=='function')return unavailable();
      await binding.delete(prefix+key);
      return {ok:true};
    },
    async list(keyPrefix='',limit=50){
      keyPrefix=validListPrefix(keyPrefix);limit=validLimit(limit);
      if(typeof binding.list!=='function')return unavailable({items:[],cursor:null});
      try{
        const listed=await binding.list({prefix:prefix+keyPrefix,limit});
        const keys=Array.isArray(listed?.keys)?listed.keys.slice(0,limit):[];
        const items=[];
        for(const row of keys){
          const name=String(row?.name||'');
          if(!name.startsWith(prefix))continue;
          const raw=await binding.get(name,'json');
          const value=raw===null?null:raw;
          items.push({key:name.slice(prefix.length),value});
        }
        return {unavailable:false,items,cursor:listed?.list_complete===false?String(listed?.cursor||''):null};
      }catch{return unavailable({items:[],cursor:null});}
    },
  };
}

function vectorStore(binding){
  if(!binding||typeof binding.query!=='function')return {available:false,async query(){return unavailable({items:[]});}};
  return {
    available:true,
    async query(vector,options={}){
      try{
        const result=await binding.query(vector,options);
        const matches=Array.isArray(result?.matches)?result.matches:[];
        return {unavailable:false,items:matches};
      }catch{return unavailable({items:[]});}
    },
  };
}

function objectStore(binding){
  if(!binding||typeof binding.get!=='function'||typeof binding.put!=='function')return {available:false,async get(){return unavailable();},async put(){return unavailable();}};
  return {
    available:true,
    async get(key){try{return await binding.get(validKey(key));}catch{return unavailable();}},
    async put(key,value){try{await binding.put(validKey(key),value);return {ok:true};}catch{return unavailable();}},
  };
}

function taskQueue(binding){
  if(!binding||typeof binding.send!=='function')return {available:false,async enqueue(){return unavailable();}};
  return {
    available:true,
    async enqueue(message){try{await binding.send(message);return {ok:true};}catch{return unavailable();}},
  };
}

function leaseLock(binding){
  if(!binding||typeof binding.withLease!=='function')return {available:false,async withLease(){return unavailable();}};
  return {
    available:true,
    async withLease(key,fn){return await binding.withLease(validKey(key),fn);},
  };
}

export function createStateStores(env={}){
  const preferred=env?.BRAIN_STATE;
  const compatible=preferred?null:env?.TRADING_STATE;
  const kvBinding=preferred||compatible||null;
  const backend=preferred?'BRAIN_STATE':compatible?'TRADING_STATE_NAMESPACED':'UNAVAILABLE';
  return Object.freeze({
    authority:false,
    routingAuthority:false,
    reasoningAuthority:false,
    backend,
    kv:jsonKvStore(kvBinding,PREFIX),
    metadata:jsonKvStore(kvBinding,META_PREFIX),
    vector:vectorStore(env?.BRAIN_VECTOR),
    objects:objectStore(env?.BRAIN_OBJECTS),
    queue:taskQueue(env?.BRAIN_QUEUE),
    locks:leaseLock(env?.BRAIN_LOCK),
  });
}

export const UNIVERSAL_STATE_PREFIX=PREFIX;
export const UNIVERSAL_STATE_META_PREFIX=META_PREFIX;
