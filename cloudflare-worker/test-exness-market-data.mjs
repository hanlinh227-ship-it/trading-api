import assert from 'node:assert/strict';
import {Buffer} from 'node:buffer';
import {createHash,generateKeyPairSync,verify} from 'node:crypto';
import {buildExnessSignedHeaders,createExnessReadonlyMarketClient} from './exness-market-data.js';
import fs from 'node:fs';
import {handleExnessMarketData} from './exness-market-data-handler.js';
import {authState} from './worker-auth.js';
import {ExnessMarketDataState} from './exness-market-data-state.js';

const {privateKey,publicKey}=generateKeyPairSync('ed25519');
const privateKeyPem=privateKey.export({format:'pem',type:'pkcs8'}).toString();
const env={
  EXNESS_ENABLED:'true',EXNESS_MODE:'SHADOW',EXNESS_LIVE_ENABLED:'false',EXNESS_LIVE_ACK:'false',
  EXNESS_API_KEY:'exnsk_test',EXNESS_PRIVATE_KEY:privateKeyPem,EXNESS_ACCOUNT_ID:'123456',
  EXNESS_API_BASE_URL:'https://ap-test.trading.exness.com',GPT_5AI_ACTION_KEY:'action-test',
};

assert.throws(()=>createExnessReadonlyMarketClient({...env,EXNESS_API_BASE_URL:'https://attacker.example'},{}),/EXNESS_API_BASE_URL_INVALID/);
assert.equal(authState(new Request('https://local'),env).ok,false);
assert.equal(authState(new Request('https://local',{headers:{'x-action-key':'action-test'}}),env).source,'ACTION_KEY');
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
  const socket=new FakeSocket(),calls=[];
  const fetchImpl=async(url,init={})=>{
    calls.push({url:String(url),method:init.method,headers:init.headers,body:init.body});
    if(String(url).endsWith('/v1/configuration/accounts/123456/instruments'))return new Response(JSON.stringify({instruments:['EURUSD','XAUUSD']}));
    if(String(url).endsWith('/v1/configuration/accounts/123456/limits'))return new Response(JSON.stringify({limits:{rest:{global_account_rate:{limit:100,window_seconds:60},methods:[{path:'/v1/configuration/accounts/{account_id}/instruments',http_method:'GET',rate_limit:{limit:20,window_seconds:60}}]},websocket:{global_account_limits:{active_connections:{limit:1},connection_rate:{limit:10,window_seconds:60}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:4,window_seconds:1}}}]}}}));
    if(init.headers?.Upgrade==='websocket')return wsResponse(socket);
    return new Response('{}',{status:404});
  };
  const reservations=[];
  const client=createExnessReadonlyMarketClient(env,{fetchImpl,now:()=>1790737200000,maxTickAgeMs:5000,reserve:async rule=>{reservations.push(rule);return {allowed:true};}});
  const quote=await client.quote('XAUUSD');
  assert.deepEqual(quote,{instrument:'XAUUSD',bid:2300.12,ask:2300.24,sourceTimestamp:'2026-09-30T03:00:00.000Z',receivedAt:'2026-09-30T03:00:00.000Z',source:'EXNESS_WEBSOCKET_TICKS'});
  const handshake=calls.find(x=>x.headers?.Upgrade==='websocket');
  assert.ok(handshake,'must use the signed WebSocket handshake');
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
  const state=new ExnessMarketDataState({storage},{});
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
  const unauthorized=await handleExnessMarketData(new Request('https://local/exness/instruments'),env,{clientFactory});
  assert.equal(unauthorized.status,401);
  assert.equal(factoryCalls,0,'unauthenticated requests must not call Exness');
  const authorized=await handleExnessMarketData(new Request('https://local/exness/instruments',{headers:{'x-action-key':'action-test'}}),env,{clientFactory});
  assert.equal(authorized.status,200);
  assert.deepEqual((await authorized.json()).instruments,['XAUUSD']);
  const quote=await handleExnessMarketData(new Request('https://local/exness/quote?instrument=XAUUSD',{headers:{authorization:'Bearer action-test'}}),env,{clientFactory});
  assert.equal(quote.status,200);
  const body=await quote.json();
  assert.equal(body.bid,2300.12);
  assert.equal(body.ask,2300.24);
  assert.ok(body.sourceTimestamp);
  assert.ok(body.receivedAt);
  assert.equal(factoryCalls,2);
  const post=await handleExnessMarketData(new Request('https://local/exness/quote?instrument=XAUUSD',{method:'POST',headers:{'x-action-key':'action-test'}}),env,{clientFactory});
  assert.equal(post.status,405);
  const disabled=await handleExnessMarketData(new Request('https://local/exness/instruments',{headers:{'x-action-key':'action-test'}}),{...env,EXNESS_ENABLED:'false'},{clientFactory});
  assert.equal(disabled.status,503);
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
    const binding={idFromName:id=>{assert.equal(id,'123456');return id;},get:id=>({fetch:req=>state.fetch(req)})};
    const response=await handleExnessMarketData(new Request('https://local/exness/quote?instrument=XAUUSD',{headers:{'x-action-key':'action-test'}}),{...env,EXNESS_MARKET_DATA_STATE:binding});
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
