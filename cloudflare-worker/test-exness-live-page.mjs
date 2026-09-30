import assert from 'node:assert/strict';
import vm from 'node:vm';
import {createExnessReadonlyMarketClient} from './exness-market-data.js';
import {EXNESS_LIVE_PAGE,FOREX_PAIRS,FOREX_EIGHT_CURRENCIES} from './exness-live-page.js';
import {ExnessMarketDataState} from './exness-market-data-state.js';

assert.equal(FOREX_PAIRS.length,28);
assert.equal(new Set(FOREX_PAIRS).size,28);
for(let i=0;i<FOREX_EIGHT_CURRENCIES.length;i++)for(let j=i+1;j<FOREX_EIGHT_CURRENCIES.length;j++)assert.equal(FOREX_PAIRS.filter(p=>p===FOREX_EIGHT_CURRENCIES[i]+FOREX_EIGHT_CURRENCIES[j]||p===FOREX_EIGHT_CURRENCIES[j]+FOREX_EIGHT_CURRENCIES[i]).length,1);
assert.ok(!/EXNESS_PRIVATE_KEY|EXNESS_API_KEY|ACCOUNT_ID|place.*order/i.test(EXNESS_LIVE_PAGE));
new vm.Script(EXNESS_LIVE_PAGE.match(/<script>([\s\S]*?)<\/script>/)?.[1]||'missing script');

const sent=[],requests=[];
const socket={accept(){},send(s){sent.push(JSON.parse(s));}};
const limits={limits:{rest:{global_account_rate:{limit:5,window_seconds:1},methods:[{http_method:'GET',path:'/v1/configuration/accounts/{account_id}/instruments',rate_limit:{limit:1,window_seconds:1}}]},websocket:{global_account_limits:{max_active_connections:10,max_inbound_message_bytes:8192,connection_rate:{limit:10,window_seconds:1}},endpoints:[{path:'/v1/server-events/accounts/{account_id}/ws/ticks',subscription_operation_rate:{ticks:{limit:25,window_seconds:1}}}]}}};
const env={EXNESS_API_KEY:'fake-test-key',EXNESS_PRIVATE_KEY:Buffer.alloc(32,1).toString('base64'),EXNESS_ACCOUNT_ID:'12345',EXNESS_API_BASE_URL:'https://ap-test.exness.com'};
const fetchImpl=async(url,options)=>{requests.push({url,options});if(url.endsWith('/limits'))return {ok:true,json:async()=>limits};if(url.endsWith('/instruments'))return {ok:true,json:async()=>({instruments:FOREX_PAIRS})};if(url.endsWith('/ws/ticks'))return {status:101,webSocket:socket};throw Error('unexpected '+url)};
const memory=new Map(),store={get:async k=>memory.get(k),put:async(k,v)=>memory.set(k,v)};
const client=createExnessReadonlyMarketClient(env,{fetchImpl,store,reserve:async()=>({allowed:true}),now:()=>1790785000000});
const stream=await client.openTicksStream(FOREX_PAIRS);
assert.equal(stream.socket,socket);
assert.equal(sent.length,0,'install downstream listeners before sending subscription');
stream.subscribe();
assert.deepEqual(sent[0],{id:'forex-eight-currencies',subscribe:{event:'ticks',instruments:FOREX_PAIRS}});
const handshake=requests.find(x=>x.url.endsWith('/ws/ticks'));
assert.ok(handshake);
assert.equal(handshake.options.method,'GET');
const signed=JSON.parse(Buffer.from(handshake.options.headers['EXN-DATA'],'base64url').toString('utf8'));
assert.equal(signed.path,'/v1/server-events/accounts/12345/ws/ticks');
assert.ok(!EXNESS_LIVE_PAGE.includes('fake-test-key'));
await assert.rejects(client.openTicksStream([...FOREX_PAIRS,'XAUUSD']),/EXNESS_STREAM_INSTRUMENTS_INVALID/);

// End-to-end mock: browser upgrade -> Durable Object -> signed Exness stream -> browser.
const RealResponse=globalThis.Response,realFetch=globalThis.fetch,realPair=globalThis.WebSocketPair;
class FakeSocket{
  constructor(){this.handlers=new Map();this.sent=[];this.peer=null;}
  accept(){}
  addEventListener(type,handler){this.handlers.set(type,handler)}
  send(value){this.sent.push(value);this.peer?.emit('message',{data:value})}
  close(){this.emit('close',{});this.peer?.emit('close',{})}
  emit(type,event){this.handlers.get(type)?.(event)}
}
globalThis.Response=class {constructor(body,{status=200,headers={},webSocket}={}){this.body=body;this.status=status;this.headers=headers;this.webSocket=webSocket}};
globalThis.WebSocketPair=class {constructor(){const a=new FakeSocket(),b=new FakeSocket();a.peer=b;b.peer=a;return [a,b]}};
const liveUpstream=new FakeSocket();const db=new Map();
const storage={get:async k=>db.get(k),put:async(k,v)=>db.set(k,v),transaction:async fn=>fn(storage)};
globalThis.fetch=async(url,options)=>{if(url.endsWith('/limits'))return {ok:true,json:async()=>limits};if(url.endsWith('/instruments'))return {ok:true,json:async()=>({instruments:FOREX_PAIRS})};if(url.endsWith('/ws/ticks'))return {status:101,webSocket:liveUpstream};throw Error('unexpected '+url)};
try{
  const state=new ExnessMarketDataState({storage},env);
  const browserResponse=await state.fetch(new Request('https://exness-market-data.internal/live/ws',{headers:{Upgrade:'websocket','x-exness-client-ip':'test-ip'}}));
  assert.equal(browserResponse.status,101);
  assert.equal(state.liveViewers,1);
  assert.equal(JSON.parse(liveUpstream.sent[0]).subscribe.instruments.length,28);
  const received=[];browserResponse.webSocket.addEventListener('message',e=>received.push(JSON.parse(e.data)));
  const now=Date.now();
  liveUpstream.emit('message',{data:JSON.stringify({tick:{instrument:'EURUSD',bid:1.12,ask:1.1202,timestamp:new Date(now).toISOString(),account_id:'12345'}})});
  assert.equal(received[0].type,'tick');assert.equal(received[0].instrument,'EURUSD');assert.ok(!JSON.stringify(received).includes('12345'));
  liveUpstream.emit('message',{data:JSON.stringify({tick:{instrument:'XAUUSD',bid:1,ask:2,timestamp:new Date(now).toISOString()}})});
  liveUpstream.emit('message',{data:JSON.stringify({tick:{instrument:'USDJPY',bid:150,ask:150.01,timestamp:new Date(now-60000).toISOString()}})});
  assert.equal(received.length,1,'non-universe and stale ticks are not sent');

  // Số đo vận chuyển phải có mặt để trang tách được độ trễ khỏi tuổi tick.
  assert.equal(typeof received[0].sentAt,'number','sentAt (đồng hồ Cloudflare) phải có');
  assert.ok(received[0].sentAt>=now-1000,'sentAt phải là mili giây epoch');
  assert.equal(typeof received[0].workerProcessMs,'number','workerProcessMs phải có');
  assert.ok(received[0].workerProcessMs>=0&&received[0].workerProcessMs<1000,'workerProcessMs phải nhỏ');
  assert.equal(typeof received[0].streamMs,'number','streamMs phải có');

  // Tick trùng (cùng cặp, cùng mốc nguồn) không được gửi lại.
  liveUpstream.emit('message',{data:JSON.stringify({tick:{instrument:'EURUSD',bid:1.12,ask:1.1202,timestamp:new Date(now).toISOString()}})});
  assert.equal(received.length,1,'tick trùng không được gửi lại');
  // Cùng cặp nhưng mốc nguồn MỚI thì phải gửi.
  liveUpstream.emit('message',{data:JSON.stringify({tick:{instrument:'EURUSD',bid:1.1201,ask:1.1203,timestamp:new Date(now+50).toISOString()}})});
  assert.equal(received.length,2,'mốc nguồn mới phải được gửi');

  browserResponse.webSocket.close();assert.equal(state.liveViewers,0);
}finally{globalThis.Response=RealResponse;globalThis.fetch=realFetch;globalThis.WebSocketPair=realPair}

// Trang phải giữ các cơ chế ổn định đã thiết kế.
assert.match(EXNESS_LIVE_PAGE,/visibilitychange/,'tab ẩn phải tạm dừng luồng để bảo vệ quota');
assert.match(EXNESS_LIVE_PAGE,/requestAnimationFrame/,'vẽ phải gom theo frame');
assert.match(EXNESS_LIVE_PAGE,/fmtCache/,'formatter phải được cache theo cặp, không tạo mỗi tick');
assert.match(EXNESS_LIVE_PAGE,/type==='stalled'/,'trang phải xử lý tín hiệu nguồn im lặng');
assert.match(EXNESS_LIVE_PAGE,/BUDGET_MS/,'trang phải có hạn mức truyền theo ngày để bảo vệ quota');
assert.match(EXNESS_LIVE_PAGE,/q\.sourceToWorkerMs\+\(perf-q\._arrived\)/,'tuổi tick phải = tuổi tại Worker + thời gian trôi qua, không dùng đồng hồ máy');
assert.match(EXNESS_LIVE_PAGE,/const perf=performance\.now\(\)/,'phải dùng performance.now cho phần thời gian trôi qua');
assert.doesNotMatch(EXNESS_LIVE_PAGE,/now-Date\.parse\(q\.sourceTimestamp\)/,'không được tính tuổi tick bằng đồng hồ thiết bị');
assert.doesNotMatch(EXNESS_LIVE_PAGE,/new Intl\.NumberFormat[^;]*format\(n\)/,'không được tạo formatter trong hàm format');
console.log('Exness 28-pair cloud WebSocket contract PASS');
