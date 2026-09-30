import {Buffer} from 'node:buffer';
import {createHash,createPrivateKey,createPublicKey,sign} from 'node:crypto';

const utf8=value=>Buffer.from(String(value),'utf8');
const b64url=value=>Buffer.from(value).toString('base64url');
const sha256=value=>createHash('sha256').update(value).digest();
const jsonHeaders={'content-type':'application/json','cache-control':'no-store'};
const MAX_TICK_FRAME_BYTES=16_384;
const MAX_EVENT_FRAME_BYTES=65_536;
// The server events stream documents exactly these subscriptions.
const EVENTS_SUBSCRIBABLE=['transactions','account_state','instruments','hmr'];
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
const STATIC_REVIEW_HOSTS=new Set(['api.exness.com','api.exness-api.com']);
// Any host Exness itself can serve the API from. The value is either operator-configured
// or returned by Exness's own signed host-discovery response, so the control that matters
// is that it stays inside the exness.com registrable domain.
export function isApprovedExnessHost(hostname){
  const host=String(hostname||'').toLowerCase().replace(/\.+$/,'');
  if(!host||host.length>253)return false;
  if(STATIC_REVIEW_HOSTS.has(host))return true;
  if(!/^[a-z0-9.-]+$/.test(host)||host.includes('..'))return false;
  return host.endsWith('.exness.com')||host.endsWith('.exness-api.com');
}
function isStaticReviewHost(baseUrl){try{return STATIC_REVIEW_HOSTS.has(new URL(String(baseUrl||'')).hostname.toLowerCase());}catch{return false;}}
function cleanBaseUrl(value){let u;try{u=new URL(String(value||''));}catch{throw fail('EXNESS_API_BASE_URL_INVALID',503);}if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||!isApprovedExnessHost(u.hostname))throw fail('EXNESS_API_BASE_URL_INVALID',503);return u.origin;}
// The host-discovery payload may carry the host as a bare string, under a differently
// named field, or nested one level deep. Accept all of those rather than guessing one.
function extractAccessPointHost(value){
  if(typeof value==='string')return value.trim();
  if(!value||typeof value!=='object')return '';
  for(const key of ['access_point','accessPoint','host','hostname','url','endpoint','origin']){
    const candidate=value[key];
    if(typeof candidate==='string'&&candidate.trim())return candidate.trim();
  }
  for(const key of ['data','result','access_point','accessPoint']){
    const nested=value[key];
    if(nested&&typeof nested==='object'){const found=extractAccessPointHost(nested);if(found)return found;}
  }
  return '';
}
// Sanitized shape token: enough to diagnose a rejected access point without ever echoing
// the host itself. Uppercase and underscores only, so a canary can append it verbatim.
export function describeExnessAccessPoint(value){
  if(value==null)return 'APVALUE_ABSENT';
  if(typeof value==='object'){
    const keys=Object.keys(value).slice(0,8).map(key=>String(key).replace(/[^A-Za-z0-9]+/g,'_').toUpperCase()).join('_');
    return ('APVALUE_OBJECT_KEYS_'+keys).toUpperCase().replace(/[^A-Z0-9_]/g,'').slice(0,120);
  }
  if(typeof value!=='string')return ('APVALUE_TYPE_'+typeof value).toUpperCase().replace(/[^A-Z0-9_]/g,'');
  const raw=value.trim();
  if(!raw)return 'APVALUE_EMPTY';
  let u;try{u=new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)?raw:'https://'+raw);}catch{return 'APVALUE_UNPARSABLE'+(raw.includes('/')?'_SLASH':'')+(raw.includes(' ')?'_SPACE':'');}
  const labels=u.hostname.toLowerCase().replace(/\.+$/,'').split('.').filter(Boolean);
  const tail=labels.slice(-2).join('_').replace(/[^a-z0-9_]/g,'').toUpperCase();
  return ['APVALUE_STRING',`SCHEME_${u.protocol.replace(':','').toUpperCase()}`,`LABELS_${labels.length}`,`TAIL_${tail}`,`AP_PREFIX_${/^ap-/.test(labels[0]||'')?'YES':'NO'}`,`HAD_QUERY_${u.search?'YES':'NO'}`,`HAD_USERINFO_${(u.username||u.password)?'YES':'NO'}`].join('_');
}
export function normalizeExnessAccessPoint(value){
  const raw=extractAccessPointHost(value);
  if(!raw){const error=fail('EXNESS_ACCESS_POINT_MISSING',503);error.upstreamClass=describeExnessAccessPoint(value);throw error;}
  let u;try{u=new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)?raw:'https://'+raw);}catch{const error=fail('EXNESS_ACCESS_POINT_INVALID',503);error.upstreamClass=describeExnessAccessPoint(value);throw error;}
  if(u.protocol!=='https:'||u.username||u.password||!isApprovedExnessHost(u.hostname)){const error=fail('EXNESS_ACCESS_POINT_INVALID',503);error.upstreamClass=describeExnessAccessPoint(value);throw error;}
  return u.origin;
}
function classifyUpstreamError(status,response){
  if(Number(status)!==404)return 'UPSTREAM_HTTP_ERROR';
  const contentType=String(response?.headers?.get?.('content-type')||'').toLowerCase();
  if(contentType.includes('application/json'))return 'UPSTREAM_ENTITY_404_JSON';
  if(contentType.includes('text/plain'))return 'UPSTREAM_ROUTE_NOT_FOUND_PLAINTEXT';
  return 'UPSTREAM_UNCLASSIFIED_404';
}
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

// Shared WebSocket admission rules for the events and ticks streams. The per-operation
// subscription rate comes from the live limits payload, never from a hardcoded value.
function ruleForStream(limits,accountId,stream,operation){
  const websocket=limits?.limits?.websocket,global=websocket?.global_account_limits;
  const active=Number(global?.active_connections?.limit??global?.max_active_connections??global?.active_connections_limit??global?.active_connections);
  if(!Number.isFinite(active)||active<1)throw fail('EXNESS_WEBSOCKET_CONNECTION_LIMIT_UNAVAILABLE');
  const connection=rateRule(global?.connection_rate??global?.connection_creation_rate);
  const path=`/v1/server-events/accounts/${accountId}/ws/${stream}`;
  const suffix=`/accounts/{account_id}/ws/${stream}`;
  const endpoint=(websocket?.endpoints||[]).find(x=>String(x.path||'')===path||String(x.path||'').includes(suffix));
  const subscription=rateRule(endpoint?.subscription_operation_rate?.[operation]??endpoint?.subscription_operation_rate?.[0]);
  if(!connection||!subscription)throw fail('EXNESS_WEBSOCKET_RATE_LIMIT_UNAVAILABLE');
  return {active,connection,subscription,path};
}
function ruleForTicks(limits,accountId){return ruleForStream(limits,accountId,'ticks','ticks');}

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
  let resolvedBaseUrl=null,accessPointRequest=null;
  async function resolveBaseUrl(){
    if(resolvedBaseUrl)return resolvedBaseUrl;
    if(!isStaticReviewHost(cfg.baseUrl))return resolvedBaseUrl=cfg.baseUrl;
    if(!accessPointRequest){
      accessPointRequest=(async()=>{
        if(store){const saved=await store.get('cache:access-point');if(saved&&Number(saved.expiresAt)>now()&&saved.value)return saved.value;}
        const path=`/v1/trading/access-point?account_id=${encodeURIComponent(cfg.accountId)}`;
        const payload=await rawGet(path,cfg.baseUrl);
        const base=normalizeExnessAccessPoint(payload);
        if(store)await store.put('cache:access-point',{value:base,expiresAt:now()+900_000});
        return base;
      })().catch(error=>{accessPointRequest=null;throw error;});
    }
    return resolvedBaseUrl=await accessPointRequest;
  }
  async function rawGet(path,baseUrl){
    const target=String(baseUrl||await resolveBaseUrl())+path;
    const headers=buildExnessSignedHeaders({apiKey:cfg.apiKey,privateKey:cfg.privateKey,pathWithQuery:path,timestamp:now()});
    let response;try{response=await fetchImpl(target,{method:'GET',headers,cache:'no-store'});}catch{throw fail('EXNESS_READONLY_UPSTREAM_UNAVAILABLE');}
    if(!response.ok){const upstreamStatus=Number(response.status)||503,isLimited=upstreamStatus===429;const error=fail(isLimited?'EXNESS_UPSTREAM_RATE_LIMITED':'EXNESS_READONLY_UPSTREAM_HTTP_'+upstreamStatus,isLimited?429:503);error.upstreamStatus=upstreamStatus;error.upstreamClass=classifyUpstreamError(upstreamStatus,response);return Promise.reject(error);}
    try{return await response.json();}catch{throw fail('EXNESS_UPSTREAM_INVALID_JSON');}
  }
  async function restGet(path,limits){
    const operationRule=ruleForRest(limits,path),globalRule=rateRule(limits?.limits?.rest?.global_account_rate);
    await reserveRule(`rest:${path}`,operationRule);
    await reserveRule('rest:global',globalRule);
    return rawGet(path);
  }
  // Read-only configuration and market-data reads. The per-method rate rule is applied when
  // the account limits publish one; otherwise only the documented global account rate
  // applies, so a read endpoint cannot be blocked by a limits payload that does not list it.
  async function restRead(path,limits,key){
    const operationRule=ruleForRest(limits,path),globalRule=rateRule(limits?.limits?.rest?.global_account_rate);
    if(operationRule)await reserveRule(`rest:${key||path}`,operationRule);
    if(globalRule)await reserveRule('rest:global',globalRule);
    return rawGet(path);
  }
  // The trading account number must never leave the Worker, even in a read-only payload.
  function withoutAccountId(value){
    if(!value||typeof value!=='object'||Array.isArray(value))return value;
    const rest={...value};
    delete rest.account_id;delete rest.accountId;
    return rest;
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
  async function loadAccount(){
    return cacheRead('account',60_000,async()=>{
      const limits=await limitsForRequest(),path=`/v1/configuration/accounts/${cfg.accountId}/account`;
      const result=await restRead(path,limits,'account');
      return {...withoutAccountId(result),receivedAt:new Date(now()).toISOString()};
    });
  }
  async function loadLimits(){
    return cacheRead('limits-read',300_000,async()=>{
      const limits=await limitsForRequest();
      return {...withoutAccountId(limits),receivedAt:new Date(now()).toISOString()};
    });
  }
  async function loadConditions(instrument){
    const symbol=String(instrument||'').trim();
    if(!/^[A-Za-z0-9._-]{1,11}$/.test(symbol))throw fail('EXNESS_INSTRUMENT_INVALID',400);
    return cacheRead('conditions:'+symbol,300_000,async()=>{
      const limits=await limitsForRequest(),path=`/v1/configuration/accounts/${cfg.accountId}/instruments/${encodeURIComponent(symbol)}/conditions`;
      const result=await restRead(path,limits,'conditions');
      return {...withoutAccountId(result),receivedAt:new Date(now()).toISOString()};
    });
  }
  // Candle history. `from` is required and must be paired with either `count` or `to`.
  async function loadCandles(query={}){
    const symbol=String(query.instrument||'').trim();
    if(!/^[A-Za-z0-9._-]{1,11}$/.test(symbol))throw fail('EXNESS_INSTRUMENT_INVALID',400);
    const timeframe=String(query.timeframe||'').trim().toUpperCase();
    if(!/^(?:S1|S5|S15|M1|M3|M5|M10|M15|M30|H1|H2|H4|D1|W1|MN)$/.test(timeframe))throw fail('EXNESS_TIMEFRAME_INVALID',400);
    const priceType=String(query.price_type||'bid').trim().toLowerCase();
    if(!['bid','ask','both'].includes(priceType))throw fail('EXNESS_PRICE_TYPE_INVALID',400);
    const fromMs=Date.parse(String(query.from||''));
    if(!Number.isFinite(fromMs))throw fail('EXNESS_TIME_RANGE_INVALID',400);
    const to=String(query.to||'').trim(),count=String(query.count||'').trim();
    if(to&&count)throw fail('EXNESS_TIME_RANGE_INVALID',400);
    if(!to&&!count)throw fail('EXNESS_COUNT_OR_TO_REQUIRED',400);
    let toMs=NaN;
    if(to){toMs=Date.parse(to);if(!Number.isFinite(toMs)||toMs<=fromMs)throw fail('EXNESS_TIME_RANGE_INVALID',400);}
    if(count&&!/^[0-9]{1,6}$/.test(count))throw fail('EXNESS_COUNT_INVALID',400);
    const params=new URLSearchParams({instrument:symbol,timeframe,from:new Date(fromMs).toISOString(),price_type:priceType});
    if(to)params.set('to',new Date(toMs).toISOString());
    if(count)params.set('count',count);
    // The signed path is the same string that is transmitted, so parameter order cannot drift.
    const search=params.toString();
    return cacheRead('candles:'+search,5_000,async()=>{
      const limits=await limitsForRequest(),path=`/v1/market-data/accounts/${cfg.accountId}/candles?${search}`;
      const result=await restRead(path,limits,'candles');
      return {...withoutAccountId(result),receivedAt:new Date(now()).toISOString()};
    });
  }
  // Server events stream. Returns the first message the server sends after the subscription
  // (a snapshot for `transactions` and `hmr`). Read-only: the connection is signed as a GET
  // and the only message sent is the subscribe command.
  async function loadEvents(query={}){
    const event=String(query.event||'').trim().toLowerCase();
    if(!EVENTS_SUBSCRIBABLE.includes(event))throw fail('EXNESS_EVENT_INVALID',400);
    const instruments=(Array.isArray(query.instruments)?query.instruments:String(query.instrument||'').split(',')).map(value=>String(value||'').trim()).filter(Boolean);
    if(instruments.some(value=>!/^[A-Za-z0-9._-]{1,11}$/.test(value)))throw fail('EXNESS_INSTRUMENT_INVALID',400);
    if(event==='hmr'&&instruments.length===0)throw fail('EXNESS_HMR_INSTRUMENTS_REQUIRED',400);
    const limits=await limitsForRequest(),rules=ruleForStream(limits,cfg.accountId,'events',event);
    if(rules.active<1)throw fail('EXNESS_WEBSOCKET_CONNECTION_LIMIT_BLOCKED');
    await reserveRule('websocket:connection',rules.connection);
    await reserveRule('websocket:subscribe:'+event,rules.subscription);
    const path=rules.path,url=new URL(path,await resolveBaseUrl());
    const headers={...buildExnessSignedHeaders({apiKey:cfg.apiKey,privateKey:cfg.privateKey,pathWithQuery:path,timestamp:now()}),Upgrade:'websocket'};
    let response;try{response=await fetchImpl(url.toString(),{method:'GET',headers,cache:'no-store'});}catch{throw fail('EXNESS_WEBSOCKET_HANDSHAKE_FAILED');}
    const socket=response?.webSocket;if(!socket)throw fail(response?.status===429?'EXNESS_UPSTREAM_RATE_LIMITED':'EXNESS_WEBSOCKET_HANDSHAKE_FAILED',response?.status===429?429:503);
    try{
      socket.accept?.();
      const messagePromise=new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>reject(fail('EXNESS_EVENT_TIMEOUT',504)),timeoutMs);
        const finish=(fn,value)=>{clearTimeout(timeout);fn(value);};
        socket.addEventListener('message',incoming=>{
          const data=typeof incoming.data==='string'?incoming.data:String(incoming.data);
          if(new TextEncoder().encode(data).byteLength>MAX_EVENT_FRAME_BYTES)return finish(reject,fail('EXNESS_EVENT_FRAME_TOO_LARGE'));
          let message;try{message=JSON.parse(data);}catch{return;}
          if(Number.isFinite(Number(message?.code))&&message?.error_message)return finish(reject,fail('EXNESS_WEBSOCKET_UPSTREAM_ERROR'));
          finish(resolve,message);
        });
        socket.addEventListener('error',()=>finish(reject,fail('EXNESS_WEBSOCKET_STREAM_FAILED')));
        socket.addEventListener('close',()=>finish(reject,fail('EXNESS_WEBSOCKET_CLOSED_BEFORE_EVENT')));
      });
      const subscription={id:`events-${event}-1`,subscribe:{event}};
      if(instruments.length)subscription.subscribe.instruments=instruments;
      socket.send(JSON.stringify(subscription));
      return {event,source:'EXNESS_WEBSOCKET_EVENTS',message:await messagePromise,receivedAt:new Date(now()).toISOString()};
    }finally{try{socket.close(1000,'event received');}catch{}}
  }
  async function quote(instrument){
    const symbol=String(instrument||'').trim();if(!/^[A-Za-z0-9._-]{1,11}$/.test(symbol))throw fail('EXNESS_INSTRUMENT_INVALID',400);
    return cacheRead('quote:'+symbol,500,async()=>{
      const catalog=await loadInstruments();if(!catalog.instruments.includes(symbol))throw fail('EXNESS_INSTRUMENT_NOT_ACCOUNT_SUPPORTED',404);
      const limits=await limitsForRequest(),rules=ruleForTicks(limits,cfg.accountId);
      if(rules.active<1)throw fail('EXNESS_WEBSOCKET_CONNECTION_LIMIT_BLOCKED');
      await reserveRule('websocket:connection',rules.connection);
      await reserveRule('websocket:subscribe:ticks',rules.subscription);
      const path=rules.path,url=new URL(path,await resolveBaseUrl());
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
    });
  }
  // A browser never sees these signed headers. The caller installs message handlers
  // before calling subscribe(), so the Exness initial snapshot cannot be lost.
  async function openTicksStream(instruments){
    if(!Array.isArray(instruments)||instruments.length<1||instruments.length>28||new Set(instruments).size!==instruments.length)throw fail('EXNESS_STREAM_INSTRUMENTS_INVALID',400);
    const catalog=await loadInstruments();
    if(instruments.some(symbol=>!/^[A-Z]{6}$/.test(symbol)||!catalog.instruments.includes(symbol)))throw fail('EXNESS_INSTRUMENT_NOT_ACCOUNT_SUPPORTED',400);
    const limits=await limitsForRequest(),rules=ruleForTicks(limits,cfg.accountId);
    if(rules.active<1)throw fail('EXNESS_WEBSOCKET_CONNECTION_LIMIT_BLOCKED');
    const subscription=JSON.stringify({id:'forex-eight-currencies',subscribe:{event:'ticks',instruments}});
    const maxBytes=Number(limits?.limits?.websocket?.global_account_limits?.max_inbound_message_bytes);
    if(!(maxBytes>0)||utf8(subscription).length>maxBytes)throw fail('EXNESS_STREAM_SUBSCRIPTION_TOO_LARGE');
    await reserveRule('websocket:connection',rules.connection);
    await reserveRule('websocket:subscribe:ticks',rules.subscription);
    const path=rules.path,url=new URL(path,await resolveBaseUrl());
    const headers={...buildExnessSignedHeaders({apiKey:cfg.apiKey,privateKey:cfg.privateKey,pathWithQuery:path,timestamp:now()}),Upgrade:'websocket'};
    let response;try{response=await fetchImpl(url.toString(),{method:'GET',headers,cache:'no-store'});}catch{throw fail('EXNESS_WEBSOCKET_HANDSHAKE_FAILED');}
    const socket=response?.webSocket;
    if(!socket)throw fail(response?.status===429?'EXNESS_UPSTREAM_RATE_LIMITED':'EXNESS_WEBSOCKET_HANDSHAKE_FAILED',response?.status===429?429:503);
    socket.accept?.();
    return {socket,subscribe:()=>socket.send(subscription)};
  }
  return {instruments:loadInstruments,quote,openTicksStream,account:loadAccount,limits:loadLimits,conditions:loadConditions,candles:loadCandles,events:loadEvents,config:{accountId:cfg.accountId,readOnly:true}};
}

export function jsonResponse(body,status=200){return new Response(JSON.stringify(body),{status,headers:jsonHeaders});}
