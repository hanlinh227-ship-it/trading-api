import assert from 'node:assert/strict';
import {Buffer} from 'node:buffer';
import {createHash,generateKeyPairSync,verify} from 'node:crypto';
import {buildExnessSignedHeaders,createExnessReadonlyMarketClient,describeExnessAccessPoint,isApprovedExnessHost,normalizeExnessAccessPoint} from './exness-market-data.js';
import fs from 'node:fs';
import {handleExnessMarketData} from './exness-market-data-handler.js';
import {authState} from './worker-auth.js';
import {ExnessMarketDataState} from './exness-market-data-state.js';

const {privateKey,publicKey}=generateKeyPairSync('ed25519');
const privateKeyPem=privateKey.export({format:'pem',type:'pkcs8'}).toString();
const env={
  EXNESS_ENABLED:'true',EXNESS_MODE:'SHADOW',EXNESS_LIVE_ENABLED:'false',EXNESS_LIVE_ACK:'false',
  EXNESS_API_KEY:'exnsk_test',EXNESS_PRIVATE_KEY:privateKeyPem,EXNESS_ACCOUNT_ID:'123456',
  EXNESS_API_BASE_URL:'https://ap-test.trading.exness.com',
};

assert.throws(()=>createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://attacker.example'},{}),/EXNESS_API_BASE_URL_INVALID/);
assert.doesNotThrow(()=>createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://ap-4decef67.exness.com'},{}));
assert.equal(authState(new Request('https://local'),env).ok,false);
assert.equal(authState(new Request('https://local',{headers:{'x-action-key':'action-test'}}),{...env,GPT_5AI_ACTION_KEY:'action-test'}).source,'ACTION_KEY');
assert.equal(authState(new Request('https://local',{headers:{authorization:'Bearer bridge-test'}}),{V11_AI_BRIDGE_SECRET:'bridge-test'}).source,'VPS_BRIDGE_SECRET');

function verifyExnessSignature(headers,expectedPath){
  const data=Buffer.from(headers['EXN-DATA'].replace(/-/g,'+').replace(/_/g,'/'),'base64');
  const signature=Buffer.from(headers['EXN-SIGN'].replace(/-/g,'+').replace(/_/g,'/'),'base64');
  assert.equal(verify(null,data,publicKey,signature),true);
  const payload=JSON.parse(data.toString('utf8'));
  assert.equal(payload.method,'GET');
  assert.equal(payload.path,expectedPath);
  assert.equal(payload.api_key,headers['EXN-API-KEY']);
  assert.equal(payload.idempotency_key,'');
  assert.equal(payload.body_hash,createHash('sha256').update('').digest('base64url'));
}

class FakeSocket{
  listeners=new Map();
  addEventListener(type,fn){this.listeners.set(type,fn);}
  accept(){}
  send(text){
    this.subscription=JSON.parse(text);
    queueMicrotask(()=>this.listeners.get('message')?.({data:JSON.stringify({instrument:'XAUUSD',bid:2300.12,ask:2300.24,timestamp:'2026-09-30T03:00:00.000Z'})}));
  }
  close(){this.closed=true;}
}

function wsResponse(socket){
  const response=new Response(null,{status:200});
  Object.defineProperty(response,'webSocket',{value:socket});
  return response;
}

{
  const signed=buildExnessSignedHeaders({apiKey:env.EXNESS_API_KEY,privateKey:privateKeyPem,pathWithQuery:'/v1/server-events/accounts/123456/ws/ticks',timestamp:1790737200000});
  verifyExnessSignature(signed,'/v1/server-events/accounts/123456/ws/ticks');
  assert.equal(signed['EXN-IDEMPOTENCY-KEY'],'');
  const der=privateKey.export({format:'der',type:'pkcs8'}),seed=der.subarray(-32),publicRaw=publicKey.export({format:'der',type:'spki'}).subarray(-32);
  verifyExnessSignature(buildExnessSignedHeaders({apiKey:env.EXNESS_API_KEY,privateKey:seed.toString('hex'),pathWithQuery:'/v1/server-events/accounts/123456/ws/ticks',timestamp:1790737200000}),'/v1/server-events/accounts/123456/ws/ticks');
  verifyExnessSignature(buildExnessSignedHeaders({apiKey:env.EXNESS_API_KEY,privateKey:Buffer.concat([seed,publicRaw]).toString('hex'),pathWithQuery:'/v1/server-events/accounts/123456/ws/ticks',timestamp:1790737200000}),'/v1/server-events/accounts/123456/ws/ticks');
}

{
{
  const socket=new FakeSocket(),calls=[];
  const fetchImpl=async(url,init={})=>{
    calls.push({url:String(url),method:init.method,headers:init.headers,body:init.body});
    if(String(url).endsWith('/v1/configuration/accounts/123456/instruments'))return new Response(JSON.stringify({instruments:['EURUSD','XAUUSD']}));
    if(String(url).endsWith('/v1/configuration/accounts/123456/limits'))return new Response(JSON.stringify({limits:{rest:{global_account_rate:{limit:100,window_seconds:60},methods:[{path:'/v1/configuration/accounts/{account_id}/instruments',http_method:'GET',rate_limit:{limit:20,window_seconds:60}}]},websocket:{global_account_limits:{active_connections:{limit:1},connection_rate:{limit:10,window_seconds:60}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:4,window_seconds:1}}}]}}}));
    if(init.headers?.Upgrade==='websocket')return wsResponse(socket);
    return new Response('{}',{status:404});
  };
  const reservations=[],quoteCache=new Map();
  const secretBindings={EXNESS_READONLY_API_KEY:'exnsk_readonly_test',EXNESS_READONLY_PRIVATE_KEY:privateKeyPem,EXNESS_READONLY_ACCOUNT_ID:'123456',EXNESS_READONLY_API_BASE_URL:'https://ap-test.trading.exness.com'};
  const client=createExnessReadonlyMarketClient({...env,...secretBindings},{fetchImpl,store:{get:key=>quoteCache.get(key),put:(key,value)=>quoteCache.set(key,value)},now:()=>1790737200000,maxTickAgeMs:5000,reserve:async rule=>{reservations.push(rule);return {allowed:true};}});
  const quote=await client.quote('XAUUSD');
  assert.deepEqual(quote,{instrument:'XAUUSD',bid:2300.12,ask:2300.24,sourceTimestamp:'2026-09-30T03:00:00.000Z',receivedAt:'2026-09-30T03:00:00.000Z',source:'EXNESS_WEBSOCKET_TICKS'});
  assert.deepEqual(await client.quote('XAUUSD'),quote,'the same quote should be served during the 500 ms cache window');
  assert.equal(calls.filter(x=>x.headers?.Upgrade==='websocket').length,1,'cache hits must not create another Exness WebSocket');
  const handshake=calls.find(x=>x.headers?.Upgrade==='websocket');
  assert.ok(handshake,'must use the signed WebSocket handshake');
  assert.equal(handshake.headers['EXN-API-KEY'],'exnsk_readonly_test','prefer collision-free secret binding over legacy plain variable');
  assert.equal(handshake.method,'GET');
  verifyExnessSignature(handshake.headers,'/v1/server-events/accounts/123456/ws/ticks');
  assert.deepEqual(socket.subscription,{id:'ticks-xauusd-1',subscribe:{event:'ticks',instruments:['XAUUSD']}});
  assert.ok(reservations.length>=1,'must reserve capacity using account-provided limits');
  assert.equal(socket.closed,true);
  const beforeLimited=calls.length;
  const limited=createExnessReadonlyMarketClient(env,{fetchImpl,now:()=>1790737200000,maxTickAgeMs:5000,reserve:async rule=>({allowed:rule.key!=='websocket:connection'})});
  await assert.rejects(limited.quote('XAUUSD'),/EXNESS_RATE_LIMITED/);
  assert.equal(calls.slice(beforeLimited).some(x=>x.headers?.Upgrade==='websocket'),false,'must not connect after account quota is exhausted');
}

{
  const storageMap=new Map(),storage={
    get:key=>storageMap.get(key),put:(key,value)=>storageMap.set(key,value),
    transaction:fn=>fn({get:key=>storageMap.get(key),put:(key,value)=>storageMap.set(key,value)}),
  };
  const state=new ExnessMarketDataState({storage},{EXNESS_API_KEY:'test',EXNESS_PRIVATE_KEY:privateKeyPem,EXNESS_ACCOUNT_ID:'123456',EXNESS_API_BASE_URL:'https://ap-test.trading.exness.com'});
  for(let i=0;i<30;i++){
    const response=await state.fetch(new Request('https://internal/quote?instrument=',{headers:{'x-exness-client-ip':'203.0.113.11'}}));
    assert.notEqual(response.status,429,'first 30 reads from one address should not be blocked');
  }
  const limited=await state.fetch(new Request('https://internal/quote?instrument=',{headers:{'x-exness-client-ip':'203.0.113.11'}}));
  assert.equal(limited.status,429,'31st read from one address is rate limited');
  assert.equal(limited.headers.get('retry-after'),'60');
  assert.equal([...storageMap.keys()].some(key=>key.includes('203.0.113.11')),false,'raw client IP must not be persisted');
  const other=await state.fetch(new Request('https://internal/quote?instrument=',{headers:{'x-exness-client-ip':'203.0.113.12'}}));
  assert.notEqual(other.status,429,'rate limit bucket is isolated per client address');
}

  const socket=new FakeSocket(),calls=[];
  const fetchImpl=async(url,init={})=>{
    calls.push({url:String(url),init});
    if(String(url).endsWith('/instruments'))return new Response(JSON.stringify({instruments:['EURUSD']}));
    if(String(url).endsWith('/limits'))return new Response(JSON.stringify({limits:{rest:{global_account_rate:{limit:100,window_seconds:60},methods:[{path:'/v1/configuration/accounts/{account_id}/instruments',http_method:'GET',rate_limit:{limit:20,window_seconds:60}}]},websocket:{global_account_limits:{active_connections:{limit:1},connection_rate:{limit:10,window_seconds:60}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:4,window_seconds:1}}}]}}}));
    if(init.headers?.Upgrade==='websocket')return wsResponse(socket);
    return new Response('{}',{status:404});
  };
  const client=createExnessReadonlyMarketClient(env,{fetchImpl,now:()=>1790737200000,reserve:async()=>({allowed:true})});
  await assert.rejects(client.quote('XAUUSD'),/EXNESS_INSTRUMENT_NOT_ACCOUNT_SUPPORTED/);
  assert.equal(calls.some(x=>x.init.headers?.Upgrade==='websocket'),false,'unsupported instruments must never be subscribed');
}

{
  const storageMap=new Map(),storage={
    get:key=>storageMap.get(key),put:(key,value)=>storageMap.set(key,value),
    transaction:fn=>fn({get:key=>storageMap.get(key),put:(key,value)=>storageMap.set(key,value)}),
  };
  const state=new ExnessMarketDataState({storage},{EXNESS_API_KEY:'test',EXNESS_PRIVATE_KEY:privateKeyPem,EXNESS_ACCOUNT_ID:'123456',EXNESS_API_BASE_URL:'https://ap-test.trading.exness.com'});
  assert.deepEqual(await state.reserve({key:'websocket:test',limit:1,windowSeconds:5,now:1000}),{allowed:true});
  assert.deepEqual(await state.reserve({key:'websocket:test',limit:1,windowSeconds:5,now:2000}),{allowed:false});
  assert.deepEqual(await state.reserve({key:'websocket:test',limit:1,windowSeconds:5,now:7000}),{allowed:true});
  assert.deepEqual(await state.reserve({key:'websocket:bucket',limit:2,windowSeconds:2,refillRatePerSecond:1,now:1000}),{allowed:true});
  assert.deepEqual(await state.reserve({key:'websocket:bucket',limit:2,windowSeconds:2,refillRatePerSecond:1,now:1000}),{allowed:true});
  assert.deepEqual(await state.reserve({key:'websocket:bucket',limit:2,windowSeconds:2,refillRatePerSecond:1,now:1000}),{allowed:false});
  assert.deepEqual(await state.reserve({key:'websocket:bucket',limit:2,windowSeconds:2,refillRatePerSecond:1,now:2000}),{allowed:true});
}

{
  const socket=new FakeSocket(),fetchImpl=async(url,init={})=>{
    if(String(url).endsWith('/instruments'))return new Response(JSON.stringify({instruments:['XAUUSD']}));
    if(String(url).endsWith('/limits'))return new Response(JSON.stringify({limits:{rest:{global_account_rate:{limit:100,window_seconds:60},methods:[{path:'/v1/configuration/accounts/{account_id}/instruments',http_method:'GET',rate_limit:{limit:20,window_seconds:60}}]},websocket:{global_account_limits:{active_connections:{limit:1},connection_rate:{limit:10,window_seconds:60}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:4,window_seconds:1}}}]}}}));
    if(init.headers?.Upgrade==='websocket'){
      const stale=new FakeSocket();
      stale.send=function(text){this.subscription=JSON.parse(text);queueMicrotask(()=>this.listeners.get('message')?.({data:JSON.stringify({instrument:'XAUUSD',bid:2300.12,ask:2300.24,timestamp:'2026-09-30T02:59:00.000Z'})}));};
      return wsResponse(stale);
    }
    return new Response('{}',{status:404});
  };
  const client=createExnessReadonlyMarketClient(env,{fetchImpl,now:()=>1790737200000,maxTickAgeMs:5000,reserve:async()=>({allowed:true})});
  await assert.rejects(client.quote('XAUUSD'),/EXNESS_TICK_STALE/);
  void socket;
}

{
  let factoryCalls=0;
  const clientFactory=()=>{factoryCalls++;return {instruments:async()=>({instruments:['XAUUSD']}),quote:async()=>({instrument:'XAUUSD',bid:2300.12,ask:2300.24,sourceTimestamp:'2026-09-30T03:00:00.000Z',receivedAt:'2026-09-30T03:00:00.100Z',source:'EXNESS_WEBSOCKET_TICKS'})};};
  const catalog=await handleExnessMarketData(new Request('https://local/exness/instruments'),env,{clientFactory});
  assert.equal(catalog.status,200,'public read-only instrument catalog must not require GPT_5AI_ACTION_KEY');
  assert.deepEqual((await catalog.json()).instruments,['XAUUSD']);
  const quote=await handleExnessMarketData(new Request('https://local/exness/quote?instrument=XAUUSD'),env,{clientFactory});
  assert.equal(quote.status,200,'public read-only quote must not require GPT_5AI_ACTION_KEY');
  const body=await quote.json();
  assert.equal(body.bid,2300.12);
  assert.equal(body.ask,2300.24);
  assert.ok(body.sourceTimestamp);
  assert.ok(body.receivedAt);
  assert.equal(factoryCalls,2);
  const post=await handleExnessMarketData(new Request('https://local/exness/quote?instrument=XAUUSD',{method:'POST'}),env,{clientFactory});
  assert.equal(post.status,405);
  const disabled=await handleExnessMarketData(new Request('https://local/exness/instruments'),{...env,EXNESS_ENABLED:'false'},{clientFactory});
  assert.equal(disabled.status,503);
  const aliasOnly={...env,EXNESS_READONLY_API_KEY:'alias-key',EXNESS_READONLY_PRIVATE_KEY:privateKeyPem,EXNESS_READONLY_ACCOUNT_ID:'654321',EXNESS_READONLY_API_BASE_URL:'https://ap-test.trading.exness.com'};
  delete aliasOnly.EXNESS_API_KEY;delete aliasOnly.EXNESS_PRIVATE_KEY;delete aliasOnly.EXNESS_ACCOUNT_ID;delete aliasOnly.EXNESS_API_BASE_URL;
  let resolvedAccountId='';
  aliasOnly.EXNESS_MARKET_DATA_STATE={idFromName(value){resolvedAccountId=value;return value;},get(){return {fetch:async()=>new Response(JSON.stringify({ok:true,exchange:'EXNESS',readOnly:true,instruments:['XAUUSD']}),{status:200})};}};
  const aliasResponse=await handleExnessMarketData(new Request('https://local/exness/instruments'),aliasOnly);
  assert.equal(aliasResponse.status,200,'handler should accept collision-free secret bindings alone');
  assert.equal(resolvedAccountId,'654321','Durable Object should be partitioned by secret-bound account ID');
}

{
  const storageMap=new Map(),storage={
    get:key=>storageMap.get(key),put:(key,value)=>storageMap.set(key,value),
    transaction:fn=>fn({get:key=>storageMap.get(key),put:(key,value)=>storageMap.set(key,value)}),
  };
  const state=new ExnessMarketDataState({storage},env),socket=new FakeSocket(),originalFetch=globalThis.fetch;
  socket.send=function(text){this.subscription=JSON.parse(text);queueMicrotask(()=>this.listeners.get('message')?.({data:JSON.stringify({instrument:'XAUUSD',bid:2300.12,ask:2300.24,timestamp:new Date().toISOString()})}));};
  globalThis.fetch=async(url,init={})=>{
    if(String(url).endsWith('/v1/configuration/accounts/123456/limits'))return new Response(JSON.stringify({limits:{rest:{global_account_rate:{limit:100,window_seconds:60},methods:[{path:'/v1/configuration/accounts/{account_id}/instruments',http_method:'GET',rate_limit:{limit:20,window_seconds:60}}]},websocket:{global_account_limits:{active_connections:{limit:1},connection_rate:{limit:10,window_seconds:60}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:4,window_seconds:1}}}]}}}));
    if(String(url).endsWith('/v1/configuration/accounts/123456/instruments'))return new Response(JSON.stringify({instruments:['XAUUSD']}));
    if(init.headers?.Upgrade==='websocket')return wsResponse(socket);
    return new Response('{}',{status:404});
  };
  try{
    let forwardedIp='';const binding={idFromName:id=>{assert.equal(id,'123456');return id;},get:id=>({fetch:req=>{forwardedIp=req.headers.get('x-exness-client-ip');return state.fetch(req);}})};
    const response=await handleExnessMarketData(new Request('https://local/exness/quote?instrument=XAUUSD',{headers:{'cf-connecting-ip':'203.0.113.9'}}),{...env,EXNESS_MARKET_DATA_STATE:binding});
    assert.equal(forwardedIp,'203.0.113.9','the Cloudflare client address must be forwarded to the DO');
    assert.equal(response.status,200);
    const body=await response.json();
    assert.equal(body.exchange,'EXNESS');
    assert.equal(body.instrument,'XAUUSD');
    assert.equal(body.bid,2300.12);
    assert.equal(body.ask,2300.24);
    assert.equal(body.source,'EXNESS_WEBSOCKET_TICKS');
    assert.ok(body.sourceTimestamp);
    assert.ok(body.receivedAt);
  }finally{globalThis.fetch=originalFetch;}
}

for(const file of ['exness-market-data.js','exness-market-data-handler.js','exness-market-data-state.js']){
  const source=fs.readFileSync(new URL(file,import.meta.url),'utf8');
  assert.doesNotMatch(source,/\/v1\/trading\/accounts\//i,`${file} must not reference Exness trading routes`);
}

console.log('exness read-only market data contract ok');

{
  const unauthorized=createExnessReadonlyMarketClient(env,{fetchImpl:async()=>new Response(JSON.stringify({error_code:1000}),{status:401})});
  await assert.rejects(unauthorized.instruments(),error=>error.code==='EXNESS_READONLY_UPSTREAM_HTTP_401');
}

const limitsFixture={limits:{rest:{global_account_rate:{limit:100,window_seconds:60},methods:[{path:'/v1/configuration/accounts/{account_id}/instruments',http_method:'GET',rate_limit:{limit:20,window_seconds:60}}]},websocket:{global_account_limits:{active_connections:{limit:1},connection_rate:{limit:10,window_seconds:60}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:4,window_seconds:1}}}]}}};

{
  assert.equal(isApprovedExnessHost('api.exness.com'),true,'documented main review host');
  assert.equal(isApprovedExnessHost('api.exness-api.com'),true,'documented alternative review host');
  assert.equal(isApprovedExnessHost('ap-4decef67.exness.com'),true,'documented access point shape from send-first-request');
  assert.equal(isApprovedExnessHost('ap-qwerty123.trading.exness.com'),true,'documented access point shape from host discovery');
  assert.equal(isApprovedExnessHost('attacker.example'),false);
  assert.equal(isApprovedExnessHost('ap-evil.exness.com.attacker.example'),false,'suffix spoofing must not pass the allowlist');
  assert.equal(isApprovedExnessHost('evil-exness.com'),false);
  assert.equal(normalizeExnessAccessPoint('ap-4decef67.exness.com'),'https://ap-4decef67.exness.com');
  assert.equal(normalizeExnessAccessPoint('https://ap-qwerty123.trading.exness.com'),'https://ap-qwerty123.trading.exness.com');
  assert.throws(()=>normalizeExnessAccessPoint('http://ap-x.exness.com'),/EXNESS_ACCESS_POINT_INVALID/,'plaintext transport must be rejected');
  assert.throws(()=>normalizeExnessAccessPoint('attacker.example'),/EXNESS_ACCESS_POINT_INVALID/);
  assert.throws(()=>normalizeExnessAccessPoint(''),/EXNESS_ACCESS_POINT_MISSING/);
  // Host discovery may hand back an object, a differently named field, or nested payload.
  assert.equal(normalizeExnessAccessPoint({access_point:'ap-discovered.trading.exness.com'}),'https://ap-discovered.trading.exness.com');
  assert.equal(normalizeExnessAccessPoint({accessPoint:'ap-camel.exness.com',account_id:123456}),'https://ap-camel.exness.com');
  assert.equal(normalizeExnessAccessPoint({host:'ap-hostfield.exness.com'}),'https://ap-hostfield.exness.com');
  assert.equal(normalizeExnessAccessPoint({data:{access_point:'https://ap-nested.exness.com'}}),'https://ap-nested.exness.com');
  assert.throws(()=>normalizeExnessAccessPoint({access_point:'attacker.example'}),/EXNESS_ACCESS_POINT_INVALID/);
  {
    // A payload that is really an ErrorResponse must be reported with its sanitized key
    // shape, so a failed discovery is diagnosable from the canary reason alone.
    const failure=(()=>{try{normalizeExnessAccessPoint({code:2000,error_message:'ACCOUNT_NOT_FOUND'});return null;}catch(error){return error;}})();
    assert.equal(failure.code,'EXNESS_ACCESS_POINT_MISSING');
    assert.match(failure.upstreamClass,/APVALUE_OBJECT_KEYS_/);
    assert.match(failure.upstreamClass,/CODE/);
    assert.match(failure.upstreamClass,/ERROR_MESSAGE/);
  }
  assert.match(describeExnessAccessPoint('ap-abc.exness.com'),/AP_PREFIX_YES/);
  assert.match(describeExnessAccessPoint('ap-abc.exness.com'),/TAIL_EXNESS_COM/);
  assert.equal(describeExnessAccessPoint(undefined),'APVALUE_ABSENT');
  assert.equal(describeExnessAccessPoint({}),'APVALUE_OBJECT_KEYS_');
  // The diagnostic token must never echo the discovered host label.
  assert.doesNotMatch(describeExnessAccessPoint('ap-secretlabel.exness.com'),/SECRETLABEL/);
}

{
  const socket=new FakeSocket(),calls=[],limitsBody=JSON.stringify(limitsFixture);
  const fetchImpl=async(url,init={})=>{
    const target=String(url);calls.push({url:target,headers:init.headers});
    if(target==='https://api.exness.com/v1/trading/access-point?account_id=123456')return new Response(JSON.stringify({access_point:'ap-discovered.trading.exness.com',account_id:123456}));
    if(target==='https://ap-discovered.trading.exness.com/v1/configuration/accounts/123456/limits')return new Response(limitsBody);
    if(target==='https://ap-discovered.trading.exness.com/v1/configuration/accounts/123456/instruments')return new Response(JSON.stringify({instruments:['XAUUSD']}));
    if(init.headers?.Upgrade==='websocket')return wsResponse(socket);
    return new Response('404 page not found',{status:404,headers:{'content-type':'text/plain; charset=utf-8'}});
  };
  const client=createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://api.exness.com'},{fetchImpl,now:()=>1790737200000,maxTickAgeMs:5000,reserve:async()=>({allowed:true})});
  const quote=await client.quote('XAUUSD');
  assert.equal(quote.bid,2300.12);
  assert.equal(quote.ask,2300.24);
  const discovery=calls.find(x=>x.url.includes('/v1/trading/access-point?account_id=123456'));
  assert.ok(discovery,'the static review host must be exchanged for the account access point');
  verifyExnessSignature(discovery.headers,'/v1/trading/access-point?account_id=123456');
  assert.equal(calls.some(x=>x.url.startsWith('https://api.exness.com/v1/configuration/')),false,'account-scoped reads must never go to the static review host');
  const scoped=calls.filter(x=>x.url.startsWith('https://ap-discovered.trading.exness.com/'));
  assert.ok(scoped.some(x=>x.url.endsWith('/limits')),'limits must be read from the resolved access point');
  assert.ok(scoped.some(x=>x.url.endsWith('/instruments')),'instruments must be read from the resolved access point');
  const handshake=calls.find(x=>x.headers?.Upgrade==='websocket');
  assert.equal(handshake.url,'https://ap-discovered.trading.exness.com/v1/server-events/accounts/123456/ws/ticks','the WebSocket handshake must use the resolved access point');
  await client.instruments();
  assert.equal(calls.filter(x=>x.url.includes('/v1/trading/access-point')).length,1,'the resolved access point must be memoized per client');
}

{
  const fetchImpl=async url=>String(url).includes('/v1/trading/access-point')
    ? new Response(JSON.stringify({access_point:'attacker.example'}))
    : new Response(JSON.stringify(limitsFixture));
  const client=createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://api.exness.com'},{fetchImpl,now:()=>1790737200000,reserve:async()=>({allowed:true})});
  await assert.rejects(client.instruments(),/EXNESS_ACCESS_POINT_INVALID/,'a discovered host outside the allowlist must be refused');
}

{
  const ingress=createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://ap-test.trading.exness.com'},{fetchImpl:async()=>new Response('404 page not found',{status:404,headers:{'content-type':'text/plain; charset=utf-8'}}),now:()=>1790737200000});
  await assert.rejects(ingress.instruments(),error=>error.code==='EXNESS_READONLY_UPSTREAM_HTTP_404'&&error.upstreamStatus===404&&error.upstreamClass==='UPSTREAM_ROUTE_NOT_FOUND_PLAINTEXT','an ingress route miss must be distinguishable from an account miss');
  const jsonNotFound=createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://ap-test.trading.exness.com'},{fetchImpl:async()=>new Response(JSON.stringify({code:2000,error_message:'ACCOUNT_NOT_FOUND'}),{status:404,headers:{'content-type':'application/json'}}),now:()=>1790737200000});
  await assert.rejects(jsonNotFound.instruments(),error=>error.upstreamStatus===404&&error.upstreamClass==='UPSTREAM_ENTITY_404_JSON','an application 404 must be reported as an entity miss');
}
