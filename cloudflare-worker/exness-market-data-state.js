import {createHash} from 'node:crypto';
import {createExnessReadonlyMarketClient,jsonResponse} from './exness-market-data.js';
import {FOREX_PAIRS} from './exness-live-page.js';
import {createExnessTickHub} from './exness-tick-hub.js';

const CACHE_LIMIT=3000;
const fixedWindow=(rows,now,windowMs)=>rows.filter(at=>Number(at)>now-windowMs);
// Internal read-only routes only. No mutating internal route exists.
const READ_ONLY_ROUTES=['/instruments','/quote','/quotes','/account','/limits','/conditions','/candles','/events','/live/ws'];
// Kết nối WebSocket có thể chết mà KHÔNG báo lỗi. Im lặng quá lâu thì coi như chết
// và đóng lại để trình duyệt nối lại bằng một handshake mới, thay vì đứng im vô hạn.
const STREAM_STALL_MS=30_000;
// Outbound WebSockets keep a Durable Object alive for at most 15 minutes per operation, and
// hibernation does not apply to them, so an alarm re-drives the hub while anyone is consuming.
const HUB_ALARM_MS=30_000;
const QUOTE_WAIT_MS=5_000;
// A multi-pair read right after the subscription starts would otherwise return only the pairs that
// happened to tick first. For a short window after connect it waits briefly for the rest to fill.
const BATCH_WARMUP_WINDOW_MS=10_000;
const BATCH_WARMUP_WAIT_MS=3_000;

export class ExnessMarketDataState{
  constructor(state,env){this.state=state;this.env=env;this.queue=Promise.resolve();this.liveSockets=new Set();}

  client(){return createExnessReadonlyMarketClient(this.env,{store:this.state.storage,reserve:rule=>this.reserve(rule)});}
  get hub(){
    if(!this._hub)this._hub=createExnessTickHub({instruments:FOREX_PAIRS,stallMs:STREAM_STALL_MS,openStream:()=>this.client().openTicksStream(FOREX_PAIRS)});
    return this._hub;
  }
  async arm(){try{await this.state.storage.setAlarm?.(Date.now()+HUB_ALARM_MS);}catch{}}
  async alarm(){if(this._hub&&this._hub.tick()!=='IDLE')await this.arm();}

  // Bộ đếm viewer suy ra từ socket THẬT CÒN SỐNG, không phải một số tự tăng.
  // Đứt bất thường (WebSocket code 1006) có thể KHÔNG kích hoạt handler close,
  // khiến bộ đếm rò rỉ dần rồi chặn luồng VĨNH VIỄN bằng 429. Dọn theo readyState
  // làm bộ đếm tự chữa lành ở mỗi lần kết nối mới.
  get liveViewers(){return this.liveSockets.size;}
  _pruneSockets(){for(const socket of this.liveSockets){let open=false;try{open=socket.readyState===1}catch{}if(!open)this.liveSockets.delete(socket);}}

  async reserve(rule){
    const windowMs=Math.ceil(Number(rule.windowSeconds)*1000),limit=Math.floor(Number(rule.limit)),now=Number(rule.now);
    if(!(windowMs>0&&limit>0&&Number.isFinite(now)))return {allowed:false};
    return this.state.storage.transaction(async txn=>{
      const key=`rate:${rule.key}`;
      if(Number(rule.refillRatePerSecond)>0){
        const previous=await txn.get(key)||{tokens:limit,updatedAt:now};
        const tokens=Math.min(limit,Number(previous.tokens||0)+Math.max(0,now-Number(previous.updatedAt||now))*Number(rule.refillRatePerSecond)/1000);
        if(tokens<1){await txn.put(key,{tokens,updatedAt:now});return {allowed:false};}
        await txn.put(key,{tokens:tokens-1,updatedAt:now});return {allowed:true};
      }
      const history=fixedWindow(await txn.get(key)||[],now,windowMs);
      if(history.length>=limit)return {allowed:false};
      history.push(now);await txn.put(key,history.slice(-CACHE_LIMIT));return {allowed:true};
    });
  }

  async fetch(request){
    const url=new URL(request.url);
    if(request.method!=='GET')return jsonResponse({ok:false,error:'METHOD_NOT_ALLOWED',readOnly:true},405);
    if(!READ_ONLY_ROUTES.includes(url.pathname))return jsonResponse({ok:false,error:'NOT_FOUND',readOnly:true},404);
    const ip=String(request.headers.get('x-exness-client-ip')||'unknown').slice(0,64);
    const clientHash=createHash('sha256').update(ip).digest('hex');
    const gate=await this.reserve({key:'public:'+clientHash,limit:30,windowSeconds:60,now:Date.now()});
    if(!gate.allowed)return new Response(JSON.stringify({ok:false,error:'RATE_LIMITED',readOnly:true}),{status:429,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','retry-after':'60'}});
    if(url.pathname==='/live/ws')return this.liveSocket(request);
    const work=this.queue.then(()=>this.handle(url));
    this.queue=work.catch(()=>undefined);
    return work;
  }

  async liveSocket(request){
    if(request.headers.get('upgrade')?.toLowerCase()!=='websocket')return jsonResponse({ok:false,error:'WEBSOCKET_UPGRADE_REQUIRED',readOnly:true},426);
    this._pruneSockets();
    if(this.liveSockets.size>=2)return jsonResponse({ok:false,error:'EXNESS_STREAM_VIEWER_LIMIT',readOnly:true},429);
    const slot={readyState:0};                 // giữ chỗ trước await; nếu sót sẽ bị _pruneSockets dọn
    this.liveSockets.add(slot);
    // One shared upstream subscription (see exness-tick-hub.js). Viewers are only fan-out
    // targets, so extra viewers never open another Exness connection. No Exness credential
    // or account number reaches the browser.
    const hub=this.hub;
    let ready;
    try{ready=await hub.ensure();}catch{ready={ok:false,error:'EXNESS_STREAM_UNAVAILABLE',status:503};}
    if(!ready.ok){this.liveSockets.delete(slot);return jsonResponse({ok:false,error:String(ready.error||'EXNESS_STREAM_UNAVAILABLE'),readOnly:true},Number(ready.status)||503);}
    const [browser,server]=Object.values(new WebSocketPair());
    server.accept();
    this.liveSockets.delete(slot);
    this.liveSockets.add(server);
    let closed=false,off=()=>{};
    const startedMs=Date.now();
    const close=()=>{
      if(closed)return;
      closed=true;off();
      this.liveSockets.delete(server);this.liveSockets.delete(slot);
      try{server.close(1000,'stream closed');}catch{}
    };
    server.addEventListener('close',close);
    server.addEventListener('error',close);
    server.addEventListener('message',()=>{try{server.close(1008,'read only');}catch{}close();});
    off=hub.subscribe({
      onTick:tick=>{
        const sentMs=Date.now();
        try{server.send(JSON.stringify({type:'tick',source:'EXNESS_WEBSOCKET_TICKS',instrument:tick.instrument,bid:tick.bid,ask:tick.ask,sourceTimestamp:new Date(tick.sourceMs).toISOString(),receivedAt:new Date(tick.receivedMs).toISOString(),sentAt:sentMs,workerProcessMs:Math.round((sentMs-tick.receivedMs)*1000)/1000,sourceToWorkerMs:tick.age,streamMs:sentMs-startedMs}));}catch{close();}
      },
      // The hub reconnects on its own; the viewer is told explicitly and reconnects through
      // the page's existing path, so a dead stream is never shown as a quiet live one.
      onDown:({code,silentMs})=>{
        try{server.send(JSON.stringify(code==='EXNESS_UPSTREAM_ERROR'?{type:'error',error:code}:{type:'stalled',silentMs}));}catch{}
        close();
      },
    });
    await this.arm();
    return new Response(null,{status:101,webSocket:browser});
  }

  // Serve a quote from the shared subscription. Returns null when the hub cannot connect so the
  // caller can use the original one-shot path. A quote is LIVE only while the socket is up and
  // the tick is recent; otherwise the answer is an explicit STALE error without a price.
  async hubQuote(symbol){
    const hub=this.hub;
    let ready;try{ready=await hub.ensure();}catch{return null;}
    if(!ready.ok)return null;
    await this.arm();
    let read=hub.read(symbol);
    if(read.reason==='NO_TICK'){await hub.waitForTick(symbol,QUOTE_WAIT_MS);read=hub.read(symbol);}
    if(read.state==='LIVE'){
      const tick=read.tick;
      return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,instrument:symbol,bid:tick.bid,ask:tick.ask,sourceTimestamp:new Date(tick.sourceMs).toISOString(),receivedAt:new Date(tick.receivedMs).toISOString(),source:'EXNESS_WEBSOCKET_TICKS',state:'LIVE',quoteAgeMs:read.ageMs,connection:read.health});
    }
    const timedOut=read.reason==='NO_TICK';
    return jsonResponse({ok:false,exchange:'EXNESS',readOnly:true,error:timedOut?'EXNESS_TICK_TIMEOUT':'EXNESS_TICK_STALE',state:'STALE',reason:read.reason,quoteAgeMs:read.ageMs,connection:read.health},timedOut?504:503);
  }

  // All 28 FX pairs in one read, from the shared subscription. One request replaces 28 and adds no
  // upstream connection. Each pair is LIVE or STALE on its own; a stale pair never carries a price.
  async hubQuotes(){
    const hub=this.hub;
    let ready;try{ready=await hub.ensure();}catch{ready={ok:false,error:'EXNESS_STREAM_UNAVAILABLE',status:503};}
    if(!ready.ok)return jsonResponse({ok:false,exchange:'EXNESS',readOnly:true,error:String(ready.error||'EXNESS_STREAM_UNAVAILABLE'),state:'STALE',connection:hub.health()},Number(ready.status)||503);
    await this.arm();
    const liveNow=()=>FOREX_PAIRS.filter(symbol=>hub.read(symbol).state==='LIVE').length;
    if(liveNow()===0)await hub.waitForTick(null,QUOTE_WAIT_MS);
    const sinceConnect=hub.sinceConnectMs();
    if(liveNow()<FOREX_PAIRS.length&&sinceConnect!==null&&sinceConnect<BATCH_WARMUP_WINDOW_MS)await hub.waitForCoverage(FOREX_PAIRS.length,Math.min(BATCH_WARMUP_WAIT_MS,BATCH_WARMUP_WINDOW_MS-sinceConnect));
    const quotes={};let live=0;
    for(const symbol of FOREX_PAIRS){
      const read=hub.read(symbol);
      if(read.state==='LIVE'){live++;quotes[symbol]={state:'LIVE',bid:read.tick.bid,ask:read.tick.ask,sourceTimestamp:new Date(read.tick.sourceMs).toISOString(),receivedAt:new Date(read.tick.receivedMs).toISOString(),quoteAgeMs:read.ageMs};}
      else quotes[symbol]={state:'STALE',reason:read.reason,quoteAgeMs:read.ageMs};
    }
    const connection=hub.health();
    if(live===0)return jsonResponse({ok:false,exchange:'EXNESS',readOnly:true,error:'EXNESS_TICK_STALE',state:'STALE',liveCount:0,total:FOREX_PAIRS.length,quotes,connection},503);
    return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,source:'EXNESS_WEBSOCKET_TICKS',state:live===FOREX_PAIRS.length?'LIVE':'PARTIAL',liveCount:live,total:FOREX_PAIRS.length,quotes,connection});
  }

  async handle(url){
    const instrument=String(url.searchParams.get('instrument')||'').trim();
    if(!READ_ONLY_ROUTES.includes(url.pathname))return jsonResponse({ok:false,error:'NOT_FOUND',readOnly:true},404);
    if(url.pathname==='/quotes')return this.hubQuotes();
    try{
      if(url.pathname==='/quote'&&FOREX_PAIRS.includes(instrument)){const shared=await this.hubQuote(instrument);if(shared)return shared;}
    }catch{}
    const client=this.client();
    try{
      const result=url.pathname==='/instruments'?await client.instruments()
        :url.pathname==='/quote'?await client.quote(instrument)
        :url.pathname==='/account'?await client.account()
        :url.pathname==='/limits'?await client.limits()
        :url.pathname==='/conditions'?await client.conditions(instrument)
        :url.pathname==='/candles'?await client.candles({instrument,timeframe:url.searchParams.get('timeframe'),from:url.searchParams.get('from'),to:url.searchParams.get('to'),count:url.searchParams.get('count'),price_type:url.searchParams.get('price_type')})
        :await client.events({event:url.searchParams.get('event'),instrument});
      return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,...result});
    }catch(error){const code=String(error?.code||error?.message||'EXNESS_MARKET_DATA_UNAVAILABLE');return jsonResponse({ok:false,error:code,readOnly:true,...(code==='EXNESS_TICK_STALE'||code==='EXNESS_TICK_TIMEOUT'?{state:'STALE'}:{}),...(error?.upstreamClass?{upstreamClass:String(error.upstreamClass)}:{})},Number(error?.status)||503);}
  }
}
