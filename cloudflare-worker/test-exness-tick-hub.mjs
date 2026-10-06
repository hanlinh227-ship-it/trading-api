import assert from 'node:assert/strict';
import {createExnessTickHub,HUB_BACKOFF_MS} from './exness-tick-hub.js';
import {createExnessReadonlyMarketClient} from './exness-market-data.js';
import {FOREX_PAIRS} from './exness-live-page.js';
import {ExnessMarketDataState} from './exness-market-data-state.js';

class FakeSocket{
  constructor(){this.handlers=new Map();this.sent=[];this.closed=false;this.peer=null;}
  accept(){}
  addEventListener(type,handler){this.handlers.set(type,handler);}
  send(value){this.sent.push(value);this.peer?.emit('message',{data:value});}
  close(){if(this.closed)return;this.closed=true;this.emit('close',{});this.peer?.emit('close',{});}
  emit(type,event){this.handlers.get(type)?.(event);}
}
const frame=(instrument,bid,ask,timestamp)=>({data:JSON.stringify({tick:{instrument,bid,ask,timestamp}})});

function harness(overrides={}){
  const clock={ms:1_800_000_000_000},timers=[],sockets=[],opens={count:0,fail:[]};
  const hub=createExnessTickHub({
    instruments:FOREX_PAIRS,now:()=>clock.ms,
    setTimer:(fn,ms)=>{const timer={fn,ms,at:clock.ms+ms,cancelled:false};timers.push(timer);return timer;},
    clearTimer:timer=>{if(timer)timer.cancelled=true;},
    openStream:async()=>{
      opens.count++;
      const failure=opens.fail.shift();if(failure)throw Object.assign(new Error(failure.code),failure);
      const socket=new FakeSocket();sockets.push(socket);
      return {socket,subscribe:()=>socket.send(JSON.stringify({subscribe:{event:'ticks',instruments:FOREX_PAIRS}}))};
    },
    ...overrides,
  });
  const fire=()=>{const due=timers.filter(t=>!t.cancelled);const last=due[due.length-1];if(last){last.cancelled=true;last.fn();}};
  return {hub,clock,timers,sockets,opens,fire};
}

// Symbol mapping, single upstream, fan-out.
{
  const {hub,clock,sockets,opens}=harness();
  const a=[],b=[];
  hub.subscribe({onTick:t=>a.push(t)});hub.subscribe({onTick:t=>b.push(t)});
  assert.deepEqual(await hub.ensure(),{ok:true});await hub.ensure();
  assert.equal(opens.count,1,'many consumers share one upstream subscription');
  const up=sockets[0];
  up.emit('message',frame('EURUSD',1.1,1.1002,clock.ms-50));
  up.emit('message',frame('XAUUSD',2000,2000.5,clock.ms-50));      // not in the mapped universe
  up.emit('message',frame('USDJPY',150,149.9,clock.ms-50));        // crossed book
  up.emit('message',frame('GBPUSD',1.3,1.3001,clock.ms-60_000));   // far too old at ingest
  up.emit('message',{data:'not json'});
  assert.equal(a.length,1);assert.equal(b.length,1);
  assert.equal(a[0].instrument,'EURUSD');
  up.emit('message',frame('EURUSD',1.1,1.1002,clock.ms-50));       // duplicate source timestamp
  assert.equal(a.length,1,'duplicate source tick is not fanned out twice');
  up.emit('message',frame('EURUSD',1.2,1.2,clock.ms-10));         // zero spread is a real quote
  assert.equal(a.length,2);
}

// Freshness: LIVE only with an up socket and a recent tick; never cached after disconnect.
{
  const {hub,clock,sockets}=harness();
  await hub.ensure();
  assert.equal(hub.read('EURUSD').reason,'NO_TICK');
  sockets[0].emit('message',frame('EURUSD',1.1,1.1002,clock.ms-200));
  const live=hub.read('EURUSD');
  assert.equal(live.state,'LIVE');assert.equal(live.ageMs,200);assert.equal(live.tick.bid,1.1);assert.equal(live.health.state,'LIVE');
  clock.ms+=6000;
  const old=hub.read('EURUSD');
  assert.equal(old.state,'STALE');assert.equal(old.reason,'TICK_OLD');assert.equal(old.tick,null,'a stale quote carries no price');
  clock.ms-=6000;
  sockets[0].close();                                              // upstream dies while the tick is still young
  const down=hub.read('EURUSD');
  assert.equal(down.state,'STALE');assert.equal(down.reason,'DISCONNECTED');assert.equal(down.tick,null,'cached quote must not stay fresh after disconnect');
  assert.equal(down.health.lastError,'EXNESS_STREAM_CLOSED');
}

// Reconnect with bounded backoff; late events from the dead socket are ignored.
{
  const {hub,clock,timers,sockets,opens,fire}=harness();
  const downs=[];hub.subscribe({onDown:d=>downs.push(d)});
  await hub.ensure();
  const first=sockets[0];
  first.emit('message',frame('EURUSD',1.1,1.1002,clock.ms));
  first.close();
  assert.equal(downs.length,1);assert.equal(downs[0].code,'EXNESS_STREAM_CLOSED');
  assert.equal(hub.health().state,'BACKOFF');
  assert.equal(timers.at(-1).ms,HUB_BACKOFF_MS[0]);
  assert.deepEqual(await hub.ensure(),{ok:false,error:'EXNESS_STREAM_CLOSED',status:503},'no reconnect storm inside the backoff window');
  assert.equal(opens.count,1);
  fire();await Promise.resolve();await Promise.resolve();
  assert.equal(opens.count,2,'timer reconnects');
  first.emit('message',frame('GBPUSD',1.3,1.3001,clock.ms));
  assert.equal(hub.read('GBPUSD').tick,null,'late frame from the old socket is ignored');
  sockets[1].emit('message',frame('GBPUSD',1.3,1.3001,clock.ms));
  assert.equal(hub.read('GBPUSD').state,'LIVE');
  assert.equal(hub.health().reconnectAttempts,0,'backoff resets after the first frame');
  assert.equal(hub.health().reconnects,1);
}

// Auth / connection errors: surfaced as a sanitized code, then bounded exponential backoff.
{
  const {hub,clock,timers,opens,fire}=harness();
  opens.fail.push({code:'EXNESS_READONLY_UPSTREAM_HTTP_401',status:503},{code:'EXNESS_WEBSOCKET_HANDSHAKE_FAILED',status:503},{code:'EXNESS_RATE_LIMITED',status:429});
  let result=await hub.ensure();
  assert.deepEqual(result,{ok:false,error:'EXNESS_READONLY_UPSTREAM_HTTP_401',status:503});
  assert.equal(hub.read('EURUSD').state,'STALE');
  fire();await Promise.resolve();await Promise.resolve();
  clock.ms+=1000;
  fire();await Promise.resolve();await Promise.resolve();
  result=await hub.ensure();
  assert.equal(result.error,'EXNESS_RATE_LIMITED');assert.equal(result.status,429);
  assert.deepEqual(timers.filter(t=>t.ms>=1000).slice(0,3).map(t=>t.ms),HUB_BACKOFF_MS.slice(0,3));
  for(let i=0;i<10;i++){opens.fail.push({code:'X'});}
}

// Stalled upstream (connection dead without any error): detected by tick() and reconnected.
{
  const {hub,clock,sockets}=harness();
  const downs=[];hub.subscribe({onDown:d=>downs.push(d)});
  await hub.ensure();
  sockets[0].emit('message',frame('EURUSD',1.1,1.1002,clock.ms));
  clock.ms+=20_000;assert.equal(hub.tick(),'LIVE','within the stall window nothing happens');
  clock.ms+=15_000;assert.equal(hub.tick(),'BACKOFF');
  assert.equal(downs[0].code,'EXNESS_STREAM_STALLED');assert.ok(downs[0].silentMs>=35_000);
  assert.equal(sockets[0].closed,true,'the dead socket is closed');
}

// Upstream error frame (for example an Exness ErrorResponse) is treated as a failure.
{
  const {hub,sockets}=harness();
  await hub.ensure();
  sockets[0].emit('message',{data:JSON.stringify({code:2000,error_message:'ACCOUNT_NOT_FOUND'})});
  assert.equal(hub.health().lastError,'EXNESS_UPSTREAM_ERROR');assert.equal(hub.health().state,'BACKOFF');
}

// waitForTick(null) resolves on the first tick of any instrument and times out otherwise.
{
  const {hub,clock,sockets,timers}=harness();
  await hub.ensure();
  let released=false;const waiting=hub.waitForTick(null,5000).then(()=>{released=true;});
  await Promise.resolve();assert.equal(released,false);
  sockets[0].emit('message',frame('AUDNZD',1.08,1.0802,clock.ms-20));
  await waiting;assert.equal(released,true);
  await hub.waitForTick(null,5000);   // already has a tick: resolves immediately
  assert.ok(timers.length>=1);
}

// Idle shutdown protects Free-plan duration: with no consumer the upstream is released.
{
  const {hub,clock,sockets}=harness();
  const off=hub.subscribe({});await hub.ensure();off();
  clock.ms+=121_000;assert.equal(hub.tick(),'IDLE');assert.equal(sockets[0].closed,true);
  assert.equal(hub.read('EURUSD').state,'STALE');
}

// Durable Object level: public quote shape is preserved and extended, staleness is explicit.
{
  const RealResponse=globalThis.Response,realFetch=globalThis.fetch,realPair=globalThis.WebSocketPair;
  globalThis.Response=class {constructor(body,{status=200,headers={},webSocket}={}){this.body=body;this.status=status;this.headers=headers;this.webSocket=webSocket;}async text(){return String(this.body);}async json(){return JSON.parse(this.body);}};
  globalThis.WebSocketPair=class {constructor(){const a=new FakeSocket(),b=new FakeSocket();a.peer=b;b.peer=a;return [a,b];}};
  const limits={limits:{rest:{global_account_rate:{limit:50,window_seconds:1},methods:[{http_method:'GET',path:'/v1/configuration/accounts/{account_id}/instruments',rate_limit:{limit:10,window_seconds:1}}]},websocket:{global_account_limits:{max_active_connections:1,max_inbound_message_bytes:65536,connection_rate:{limit:100,window_seconds:1}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:100,window_seconds:1}}}]}}};
  const upstream=[];let handshakes=0,authFailure=false;
  globalThis.fetch=async url=>{
    if(authFailure)return {ok:false,status:401,headers:{get:()=>'application/json'},json:async()=>({})};
    if(url.endsWith('/limits'))return {ok:true,json:async()=>limits};
    if(url.endsWith('/instruments'))return {ok:true,json:async()=>({instruments:[...FOREX_PAIRS,'XAUUSD']})};
    if(url.endsWith('/ws/ticks')){handshakes++;const socket=new FakeSocket();upstream.push(socket);return {status:101,webSocket:socket};}
    throw new Error('unexpected '+url);
  };
  const db=new Map(),storage={get:async k=>db.get(k),put:async(k,v)=>db.set(k,v),transaction:async fn=>fn(storage),setAlarm:async at=>{storage.alarmAt=at;}};
  const env={EXNESS_API_KEY:'fake',EXNESS_PRIVATE_KEY:Buffer.alloc(32,1).toString('base64'),EXNESS_ACCOUNT_ID:'12345',EXNESS_API_BASE_URL:'https://ap-test.exness.com'};
  try{
    const state=new ExnessMarketDataState({storage},env);
    const ask=(path,ip='ip-1')=>state.fetch(new Request('https://exness-market-data.internal'+path,{headers:{'x-exness-client-ip':ip,...(path==='/live/ws'?{Upgrade:'websocket'}:{})}}));
    const pending=ask('/quote?instrument=EURUSD');
    for(let i=0;i<50&&!upstream.length;i++)await new Promise(r=>setTimeout(r,2));
    upstream[0].emit('message',frame('EURUSD',1.1,1.1002,Date.now()-120));
    const response=await pending,body=JSON.parse(await response.text());
    assert.equal(response.status,200);
    for(const key of ['ok','exchange','readOnly','instrument','bid','ask','sourceTimestamp','receivedAt','source'])assert.ok(key in body,'existing public key kept: '+key);
    assert.equal(body.exchange,'EXNESS');assert.equal(body.source,'EXNESS_WEBSOCKET_TICKS');assert.equal(body.state,'LIVE');
    assert.ok(body.quoteAgeMs>=100&&body.quoteAgeMs<5000);assert.equal(body.connection.connected,true);
    assert.ok(!JSON.stringify(body).includes('12345'),'account id never leaves the Worker');
    assert.ok(storage.alarmAt>Date.now(),'an alarm keeps the shared subscription driven');
    // A second quote and a live viewer reuse the SAME upstream connection.
    upstream[0].emit('message',frame('GBPUSD',1.3,1.3001,Date.now()-50));
    const second=JSON.parse(await (await ask('/quote?instrument=GBPUSD','ip-2')).text());
    assert.equal(second.state,'LIVE');
    const viewer=await ask('/live/ws','ip-3');
    assert.equal(viewer.status,101);
    const seen=[];viewer.webSocket.addEventListener('message',e=>seen.push(JSON.parse(e.data)));
    upstream[0].emit('message',frame('EURUSD',1.1001,1.1003,Date.now()-10));
    assert.equal(seen[0]?.type,'tick');
    assert.equal(handshakes,1,'quote + viewer + second quote share one Exness connection');
    // One read returns all 28 pairs from the shared subscription, adds no upstream connection,
    // and a pair without a fresh tick is STALE with no price.
    const batch=JSON.parse(await (await ask('/quotes','ip-6')).text());
    assert.equal(batch.ok,true);assert.equal(batch.exchange,'EXNESS');assert.equal(batch.total,28);
    assert.equal(batch.state,'PARTIAL');assert.ok(batch.liveCount>=2&&batch.liveCount<28);
    assert.equal(Object.keys(batch.quotes).length,28);
    assert.equal(batch.quotes.EURUSD.state,'LIVE');assert.ok(batch.quotes.EURUSD.ask>=batch.quotes.EURUSD.bid);
    assert.equal(batch.quotes.USDJPY.state,'STALE');assert.ok(!('bid' in batch.quotes.USDJPY),'stale pair carries no price');
    assert.equal(batch.connection.state,'LIVE');assert.ok(!JSON.stringify(batch).includes('12345'));
    assert.equal(handshakes,1,'batch read shares the single upstream connection');
    // Disconnect: an explicit stale answer, never the cached tick.
    upstream[0].close();
    assert.equal(seen.at(-1).type,'stalled','viewer is told the stream stalled');
    const stale=await ask('/quote?instrument=EURUSD','ip-4'),staleBody=JSON.parse(await stale.text());
    assert.equal(staleBody.ok,false,JSON.stringify(staleBody));
    assert.ok(!('bid' in staleBody),'no price on a stale answer');
    assert.equal(staleBody.state,'STALE',JSON.stringify(staleBody)+' '+'stale is explicit even when the one-shot fallback times out');
    // Hub is in backoff, so the original one-shot path serves (and reconnect is bounded).
    assert.ok(handshakes>=1);
    // Auth failure surfaces a sanitized code through the fallback path.
    const state2=new ExnessMarketDataState({storage:{...storage,get:async()=>undefined,put:async()=>{}}},env);
    authFailure=true;
    const denied=await state2.fetch(new Request('https://exness-market-data.internal/quote?instrument=EURUSD',{headers:{'x-exness-client-ip':'ip-5'}}));
    assert.equal(JSON.parse(await denied.text()).error,'EXNESS_READONLY_UPSTREAM_HTTP_401');
    state._hub.stop();state2._hub?.stop();
  }finally{globalThis.Response=RealResponse;globalThis.fetch=realFetch;globalThis.WebSocketPair=realPair;}
}

{
  const {handleExnessMarketData}=await import('./exness-market-data-handler.js');
  const env={EXNESS_ENABLED:'true',EXNESS_MODE:'SHADOW',EXNESS_API_KEY:'k',EXNESS_PRIVATE_KEY:'p',EXNESS_ACCOUNT_ID:'1',EXNESS_API_BASE_URL:'https://ap-test.exness.com'};
  const ok=await handleExnessMarketData(new Request('https://local/exness/quotes'),env,{clientFactory:()=>({quotes:async()=>({state:'LIVE',liveCount:28,total:28,quotes:{}})})});
  assert.equal(ok.status,200);assert.equal((await ok.json()).exchange,'EXNESS');
  const post=await handleExnessMarketData(new Request('https://local/exness/quotes',{method:'POST'}),env,{clientFactory:()=>({})});
  assert.equal(post.status,405,'read-only: only GET is accepted');
}

console.log('Exness tick hub contract PASS');
