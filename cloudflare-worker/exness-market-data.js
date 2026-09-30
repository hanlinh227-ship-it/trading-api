import {Buffer} from 'node:buffer';
import {createHash,createPrivateKey,createPublicKey,sign} from 'node:crypto';

const utf8=value=>Buffer.from(String(value),'utf8');
const b64url=value=>Buffer.from(value).toString('base64url');
const sha256=value=>createHash('sha256').update(value).digest();
const jsonHeaders={'content-type':'application/json','cache-control':'no-store'};
const MAX_TICK_FRAME_BYTES=16_384;
const PKCS8_ED25519_PREFIX=Buffer.from('302e020100300506032b657004220420','hex');

function fail(code,status=503){const error=new Error(code);error.code=code;error.status=status;return error;}
function rawSeedToPrivateKey(seed){if(seed.length!==32)throw new Error('unsupported key');return createPrivateKey({key:Buffer.concat([PKCS8_ED25519_PREFIX,seed]),format:'der',type:'pkcs8'});}
function loadPrivateKey(secret){
  let value=String(secret||'').trim();
  if((value.startsWith('"')&&value.endsWith('"'))||(value.startsWith("'")&&value.endsWith("'")))value=value.slice(1,-1).trim();
  if(value.startsWith('{')){const jwk=JSON.parse(value);if(jwk.kty!=='OKP'||jwk.crv!=='Ed25519'||!jwk.d)throw new Error('not Ed25519');return createPrivateKey({key:jwk,format:'jwk'});}
  if(/-----BEGIN (?:PRIVATE KEY|ED25519 PRIVATE KEY)-----/.test(value)){const key=createPrivateKey(value);if(key.asymmetricKeyType!=='ed25519')throw new Error('not Ed25519');return key;}
  if(/^0x[0-9a-fA-F]{64}$/i.test(value))value=value.slice(2);
  let bytes;
  if(/^[0-9a-fA-F]{64}$/.test(value)||/^[0-9a-fA-F]{128}$/.test(value))bytes=Buffer.from(value,'hex');
  else{const normalized=value.replace(/\s/g,'').replace(/-/g,'+').replace(/_/g,'/');if(!/^[A-Za-z0-9+/]+={0,2}$/.test(normalized))throw new Error('unsupported key');bytes=Buffer.from(normalized,'base64');if(bytes.toString('base64').replace(/=+$/,'')!==normalized.replace(/=+$/,''))throw new Error('unsupported key');}
  if(bytes.length===64){const key=rawSeedToPrivateKey(bytes.subarray(0,32)),derived=createPublicKey(key).export({format:'der',type:'spki'}).subarray(-32);if(!derived.equals(bytes.subarray(32)))throw new Error('invalid key pair');return key;}
  if(bytes.length===96){const matches=[];for(let seedOffset=0;seedOffset<=64;seedOffset++){const key=rawSeedToPrivateKey(bytes.subarray(seedOffset,seedOffset+32)),derived=createPublicKey(key).export({format:'der',type:'spki'}).subarray(-32);for(let publicOffset=0;publicOffset<=64;publicOffset+=32)if(Math.abs(seedOffset-publicOffset)>=32&&derived.equals(bytes.subarray(publicOffset,publicOffset+32)))matches.push({seedOffset,key});}const unique=new Map(matches.map(x=>[x.seedOffset,x.key]));if(unique.size===1)return [...unique.values()][0];throw new Error('ambiguous key bundle');}
  if(bytes.length===32)return rawSeedToPrivateKey(bytes);
  const key=createPrivateKey({key:bytes,format:'der',type:'pkcs8'});if(key.asymmetricKeyType!=='ed25519')throw new Error('not Ed25519');return key;
}
function cleanBaseUrl(value){let u;try{u=new URL(String(value||''));}catch{throw fail('EXNESS_API_BASE_URL_INVALID',503);}const approved=/^(?:api[.]exness[.]com|api[.]exness-api[.]com|[a-z0-9-]+[.]trading[.]exness[.]com)$/i.test(u.hostname);if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||!approved)throw fail('EXNESS_API_BASE_URL_INVALID',503);return u.origin;}
function configOf(env={}){
  const config={apiKey:String(env.EXNESS_READONLY_API_KEY||env.EXNESS_API_KEY||'').trim(),privateKey:String(env.EXNESS_READONLY_PRIVATE_KEY||env.EXNESS_PRIVATE_KEY||'').replace(/\\n/g,'\n').trim(),accountId:String(env.EXNESS_READONLY_ACCOUNT_ID||env.EXNESS_ACCOUNT_ID||'').trim(),baseUrl:cleanBaseUrl(env.EXNESS_READONLY_API_BASE_URL||env.EXNESS_API_BASE_URL)};
  if(!config.apiKey)throw fail('EXNESS_API_KEY_MISSING');
  if(!config.privateKey)throw fail('EXNESS_PRIVATE_KEY_MISSING');
  if(!/^[0-9]{1,20}$/.test(config.accountId))throw fail('EXNESS_ACCOUNT_ID_INVALID');
  return config;
}

function rateRule(value){
  if(!value||typeof value!=='object')return null;
  const limit=Number(value.limit??value.capacity??value.burst);
  const refillRatePerSecond=Number(value.refill_rate_per_second??value.refill_per_second);
  const windowSeconds=Number(value.window_seconds??value.period_seconds??(refillRatePerSecond>0?limit/refillRatePerSecond:NaN));
  if(!Number.isFinite(limit)||limit<1||!Number.isFinite(windowSeconds)||windowSeconds<=0)return null;
  return {limit:Math.floor(limit),windowSeconds,...(refillRatePerSecond>0?{refillRatePerSecond}:{} )};
}

function ruleForRest(limits,path){
  const methods=limits?.limits?.rest?.methods;
  if(!Array.isArray(methods))return null;
  const normalize=value=>String(value||'').replace(/\/accounts\/(?:\d+|:account_id)\//,'/accounts/{account_id}/');
  const normalized=normalize(path);
  const row=methods.find(x=>normalize(x.path)===normalized&&String(x.http_method||'').toUpperCase()==='GET');
  return rateRule(row?.rate_limit);
}

function ruleForTicks(limits,accountId){
  const websocket=limits?.limits?.websocket,global=websocket?.global_account_limits;
  const active=Number(global?.active_connections?.limit??global?.max_active_connections??global?.active_connections_limit??global?.active_connections);
  if(!Number.isFinite(active)||active<1)throw fail('EXNESS_WEBSOCKET_CONNECTION_LIMIT_UNAVAILABLE');
  const connection=rateRule(global?.connection_rate??global?.connection_creation_rate);
  const path=`/v1/server-events/accounts/${accountId}/ws/ticks`;
  const endpoint=(websocket?.endpoints||[]).find(x=>String(x.path||'')===path||String(x.path||'').includes('/accounts/{account_id}/ws/ticks'));
  const subscription=rateRule(endpoint?.subscription_operation_rate?.ticks??endpoint?.subscription_operation_rate?.[0]);
  if(!connection||!subscription)throw fail('EXNESS_WEBSOCKET_RATE_LIMIT_UNAVAILABLE');
  return {active,connection,subscription,path};
}

export function buildExnessSignedHeaders({apiKey,privateKey,method='GET',pathWithQuery,body='',timestamp=Date.now()}={}){
  if(String(method).toUpperCase()!=='GET')throw fail('EXNESS_READ_ONLY_GET_REQUIRED',405);
  const path=String(pathWithQuery||'');
  if(!path.startsWith('/')||path.includes('#'))throw fail('EXNESS_SIGNED_PATH_REQUIRED',400);
  const ts=Number(timestamp);if(!Number.isSafeInteger(Math.trunc(ts))||ts<=0)throw fail('EXNESS_TIMESTAMP_INVALID',400);
  const payload={api_key:String(apiKey||''),idempotency_key:'',timestamp:Math.trunc(ts),sign_version:1,method:'GET',path,body_hash:b64url(sha256(utf8(body)))};
  let key;try{key=loadPrivateKey(privateKey);}catch{throw fail('EXNESS_PRIVATE_KEY_FORMAT_UNSUPPORTED');}
  const data=utf8(JSON.stringify(payload));
  return {'EXN-API-KEY':payload.api_key,'EXN-IDEMPOTENCY-KEY':'','EXN-TIMESTAMP':String(payload.timestamp),'EXN-SIGN-VERSION':'1','EXN-DATA':b64url(data),'EXN-SIGN':b64url(sign(null,data,key))};
}

export function createExnessReadonlyMarketClient(env={},opts={}){
  const cfg=configOf(env),fetchImpl=opts.fetchImpl||fetch,now=opts.now||Date.now,store=opts.store||null,reserve=opts.reserve||null,timeoutMs=Number(opts.timeoutMs||5000),maxTickAgeMs=Number(opts.maxTickAgeMs||5000);
  async function cacheRead(key,ttlMs,loader){
    if(store){const saved=await store.get(`cache:${key}`);if(saved&&Number(saved.expiresAt)>now())return saved.value;}
    const value=await loader();
    if(store)await store.put(`cache:${key}`,{value,expiresAt:now()+ttlMs});
    return value;
  }
  async function getLimits(){
    const path=`/v1/configuration/accounts/${cfg.accountId}/limits`,saved=store?await store.get('cache:limits'):null;
    if(saved&&Number(saved.expiresAt)>now())return saved.value;
    if(saved?.value){
      const operationRule=ruleForRest(saved.value,path),globalRule=rateRule(saved.value?.limits?.rest?.global_account_rate);
      await reserveRule('rest:limits',operationRule);
      await reserveRule('rest:global',globalRule);
    }
    const limits=await rawGet(path);
    if(store)await store.put('cache:limits',{value:limits,expiresAt:now()+300_000});
    return limits;
  }
  async function reserveRule(key,rule){
    if(!rule)throw fail('EXNESS_RATE_LIMIT_UNAVAILABLE');
    if(!reserve)throw fail('EXNESS_RATE_GATE_UNAVAILABLE');
    const result=await reserve({key,limit:rule.limit,windowSeconds:rule.windowSeconds,refillRatePerSecond:rule.refillRatePerSecond||null,now:now()});
    if(!result?.allowed)throw fail('EXNESS_RATE_LIMITED',429);
  }
  async function rawGet(path){
    const headers=buildExnessSignedHeaders({apiKey:cfg.apiKey,privateKey:cfg.privateKey,pathWithQuery:path,timestamp:now()});
    let response;try{response=await fetchImpl(cfg.baseUrl+path,{method:'GET',headers,cache:'no-store'});}catch{throw fail('EXNESS_READONLY_UPSTREAM_UNAVAILABLE');}
    if(!response.ok){const error=fail(response.status===429?'EXNESS_UPSTREAM_RATE_LIMITED':'EXNESS_READONLY_UPSTREAM_FAILED',response.status===429?429:503);error.upstreamStatus=response.status;return Promise.reject(error);}
    try{return await response.json();}catch{throw fail('EXNESS_UPSTREAM_INVALID_JSON');}
  }
  async function restGet(path,limits){
    const operationRule=ruleForRest(limits,path),globalRule=rateRule(limits?.limits?.rest?.global_account_rate);
    await reserveRule(`rest:${path}`,operationRule);
    await reserveRule('rest:global',globalRule);
    return rawGet(path);
  }
  async function limitsForRequest(){
    return getLimits();
  }
  async function loadInstruments(){
    return cacheRead('instruments',60_000,async()=>{
      const limits=await limitsForRequest(),path=`/v1/configuration/accounts/${cfg.accountId}/instruments`;
      const result=await restGet(path,limits);
      const rows=Array.isArray(result?.instruments)?result.instruments:[];
      const instruments=rows.map(x=>typeof x==='string'?x:String(x?.instrument||x?.symbol||'')).filter(x=>/^[A-Za-z0-9._-]{1,11}$/.test(x));
      return {instruments:[...new Set(instruments)],receivedAt:new Date(now()).toISOString()};
    });
  }
  async function quote(instrument){
    const symbol=String(instrument||'').trim();if(!/^[A-Za-z0-9._-]{1,11}$/.test(symbol))throw fail('EXNESS_INSTRUMENT_INVALID',400);
    const catalog=await loadInstruments();if(!catalog.instruments.includes(symbol))throw fail('EXNESS_INSTRUMENT_NOT_ACCOUNT_SUPPORTED',404);
    const limits=await limitsForRequest(),rules=ruleForTicks(limits,cfg.accountId);
    if(rules.active<1)throw fail('EXNESS_WEBSOCKET_CONNECTION_LIMIT_BLOCKED');
    await reserveRule('websocket:connection',rules.connection);
    await reserveRule('websocket:subscribe:ticks',rules.subscription);
    const path=rules.path,url=new URL(path,cfg.baseUrl);
    const headers={...buildExnessSignedHeaders({apiKey:cfg.apiKey,privateKey:cfg.privateKey,pathWithQuery:path,timestamp:now()}),Upgrade:'websocket'};
    let response;try{response=await fetchImpl(url.toString(),{method:'GET',headers,cache:'no-store'});}catch{throw fail('EXNESS_WEBSOCKET_HANDSHAKE_FAILED');}
    const socket=response?.webSocket;if(!socket){throw fail(response?.status===429?'EXNESS_UPSTREAM_RATE_LIMITED':'EXNESS_WEBSOCKET_HANDSHAKE_FAILED',response?.status===429?429:503);}
    try{
      socket.accept?.();
      const tickPromise=new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>reject(fail('EXNESS_TICK_TIMEOUT',504)),timeoutMs);
        const finish=(fn,value)=>{clearTimeout(timeout);fn(value);};
        socket.addEventListener('message',event=>{
          const data=typeof event.data==='string'?event.data:String(event.data);
          if(new TextEncoder().encode(data).byteLength>MAX_TICK_FRAME_BYTES)return finish(reject,fail('EXNESS_TICK_FRAME_TOO_LARGE'));
          let message;try{message=JSON.parse(data);}catch{return;}
          if(Number.isFinite(Number(message?.code))&&message?.error_message)return finish(reject,fail('EXNESS_WEBSOCKET_UPSTREAM_ERROR'));
          const tick=message?.tick||message?.data?.tick||message?.data||message;
          if(String(tick?.instrument||'')!==symbol)return;
          const bid=Number(tick?.bid),ask=Number(tick?.ask),sourceMs=typeof tick?.timestamp==='number'?tick.timestamp:Date.parse(String(tick?.timestamp||''));
          if(!(Number.isFinite(bid)&&bid>0&&Number.isFinite(ask)&&ask>0&&Number.isFinite(sourceMs)))return finish(reject,fail('EXNESS_TICK_INVALID'));
          const receivedMs=now(),age=receivedMs-sourceMs;
          if(age< -1000||age>maxTickAgeMs)return finish(reject,fail('EXNESS_TICK_STALE',503));
          finish(resolve,{instrument:symbol,bid,ask,sourceTimestamp:new Date(sourceMs).toISOString(),receivedAt:new Date(receivedMs).toISOString(),source:'EXNESS_WEBSOCKET_TICKS'});
        });
        socket.addEventListener('error',()=>finish(reject,fail('EXNESS_WEBSOCKET_STREAM_FAILED')));
        socket.addEventListener('close',()=>finish(reject,fail('EXNESS_WEBSOCKET_CLOSED_BEFORE_TICK')));
      });
      socket.send(JSON.stringify({id:`ticks-${symbol.toLowerCase()}-1`,subscribe:{event:'ticks',instruments:[symbol]}}));
      return await tickPromise;
    }finally{try{socket.close(1000,'quote received');}catch{}}
  }
  return {instruments:loadInstruments,quote,config:{accountId:cfg.accountId,readOnly:true}};
}

export function jsonResponse(body,status=200){return new Response(JSON.stringify(body),{status,headers:jsonHeaders});}
