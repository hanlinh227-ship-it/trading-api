import {createHash} from 'node:crypto';
import {createExnessReadonlyMarketClient,jsonResponse} from './exness-market-data.js';
import {FOREX_PAIRS} from './exness-live-page.js';

const CACHE_LIMIT=3000;
const fixedWindow=(rows,now,windowMs)=>rows.filter(at=>Number(at)>now-windowMs);
// Internal read-only routes only. No mutating internal route exists.
const READ_ONLY_ROUTES=['/instruments','/quote','/account','/limits','/conditions','/candles','/events','/live/ws'];
// Kết nối WebSocket có thể chết mà KHÔNG báo lỗi. Im lặng quá lâu thì coi như chết
// và đóng lại để trình duyệt nối lại bằng một handshake mới, thay vì đứng im vô hạn.
const STREAM_STALL_MS=30_000;
const STREAM_STALL_CHECK_MS=5_000;

export class ExnessMarketDataState{
  constructor(state,env){this.state=state;this.env=env;this.queue=Promise.resolve();this.liveViewers=0;}

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
    if(this.liveViewers>=2)return jsonResponse({ok:false,error:'EXNESS_STREAM_VIEWER_LIMIT',readOnly:true},429);
    this.liveViewers++;
    // Share the existing per-account rate gate and signed host-discovery logic.
    // No Exness credential or account number reaches the downstream client.
    const client=createExnessReadonlyMarketClient(this.env,{store:this.state.storage,reserve:rule=>this.reserve(rule)});
    let stream;
    try{stream=await client.openTicksStream(FOREX_PAIRS);}catch(error){this.liveViewers--;return jsonResponse({ok:false,error:String(error?.code||'EXNESS_STREAM_UNAVAILABLE'),readOnly:true},Number(error?.status)||503);}
    const [browser,server]=Object.values(new WebSocketPair());
    server.accept();
    const upstream=stream.socket,allowed=new Set(FOREX_PAIRS);
    let closed=false,watchdog=null;
    const startedMs=Date.now();
    let lastUpstreamMs=startedMs;            // lần cuối Exness gửi bất cứ thứ gì
    const lastSourceBySymbol=new Map();      // khử tick trùng theo (cặp, mốc nguồn)
    const close=()=>{
      if(closed)return;
      closed=true;
      if(watchdog)clearInterval(watchdog);
      this.liveViewers=Math.max(0,this.liveViewers-1);
      try{upstream.close(1000,'viewer closed');}catch{}
      try{server.close(1000,'stream closed');}catch{}
    };
    watchdog=setInterval(()=>{
      if(closed)return;
      const silentMs=Date.now()-lastUpstreamMs;
      if(silentMs>STREAM_STALL_MS){try{server.send(JSON.stringify({type:'stalled',silentMs}));}catch{}close();}
    },STREAM_STALL_CHECK_MS);
    server.addEventListener('close',close);
    server.addEventListener('error',close);
    server.addEventListener('message',()=>{try{server.close(1008,'read only');}catch{}close();});
    upstream.addEventListener('close',close);
    upstream.addEventListener('error',close);
    upstream.addEventListener('message',event=>{
      lastUpstreamMs=Date.now();
      const raw=typeof event.data==='string'?event.data:'';
      if(raw.length>16384)return;
      const parseStart=performance.now();
      let data;try{data=JSON.parse(raw);}catch{return;}
      if(Number.isFinite(Number(data?.code))&&data?.error_message){try{server.send(JSON.stringify({type:'error',error:'EXNESS_UPSTREAM_ERROR'}));}catch{}close();return;}
      const tick=data?.tick||data?.data?.tick||data?.data||data;
      const instrument=String(tick?.instrument||'');
      if(!allowed.has(instrument))return;
      const bid=Number(tick?.bid),ask=Number(tick?.ask);
      const sourceMs=typeof tick?.timestamp==='number'?tick.timestamp:Date.parse(String(tick?.timestamp||''));
      const receivedMs=Date.now(),age=receivedMs-sourceMs;
      if(!(bid>0&&ask>bid&&Number.isFinite(sourceMs))||age< -1000||age>10000)return;
      if(lastSourceBySymbol.get(instrument)===sourceMs)return;   // tick trùng -> không gửi lại
      lastSourceBySymbol.set(instrument,sourceMs);
      const sentMs=Date.now();
      const workerProcessMs=Math.round((performance.now()-parseStart)*1000)/1000;
      try{server.send(JSON.stringify({type:'tick',source:'EXNESS_WEBSOCKET_TICKS',instrument,bid,ask,sourceTimestamp:new Date(sourceMs).toISOString(),receivedAt:new Date(receivedMs).toISOString(),sentAt:sentMs,workerProcessMs,sourceToWorkerMs:age,streamMs:sentMs-startedMs}));}catch{close();}
    });
    try{stream.subscribe();}catch{close();return jsonResponse({ok:false,error:'EXNESS_SUBSCRIBE_FAILED',readOnly:true},503);}
    return new Response(null,{status:101,webSocket:browser});
  }

  async handle(url){
    const instrument=String(url.searchParams.get('instrument')||'').trim();
    if(!READ_ONLY_ROUTES.includes(url.pathname))return jsonResponse({ok:false,error:'NOT_FOUND',readOnly:true},404);
    const client=createExnessReadonlyMarketClient(this.env,{store:this.state.storage,reserve:rule=>this.reserve(rule)});
    try{
      const result=url.pathname==='/instruments'?await client.instruments()
        :url.pathname==='/quote'?await client.quote(instrument)
        :url.pathname==='/account'?await client.account()
        :url.pathname==='/limits'?await client.limits()
        :url.pathname==='/conditions'?await client.conditions(instrument)
        :url.pathname==='/candles'?await client.candles({instrument,timeframe:url.searchParams.get('timeframe'),from:url.searchParams.get('from'),to:url.searchParams.get('to'),count:url.searchParams.get('count'),price_type:url.searchParams.get('price_type')})
        :await client.events({event:url.searchParams.get('event'),instrument});
      return jsonResponse({ok:true,exchange:'EXNESS',readOnly:true,...result});
    }catch(error){return jsonResponse({ok:false,error:String(error?.code||error?.message||'EXNESS_MARKET_DATA_UNAVAILABLE'),readOnly:true,...(error?.upstreamClass?{upstreamClass:String(error.upstreamClass)}:{})},Number(error?.status)||503);}
  }
}
