import {runBybitAutoControlled,recordBybitAutoSchedulerError} from './bybit-auto-controller.js';

const VERSION='BYBIT_CLOUD_MARKET_STREAM_V1';
const SYMBOL='BTCUSDT';
const WS_URL='wss://stream.bybit.com/v5/public/linear';
const FETCH_URL='https://stream.bybit.com/v5/public/linear';
const TOPICS=[
  'orderbook.50.BTCUSDT',
  'publicTrade.BTCUSDT',
  'allLiquidation.BTCUSDT',
  'tickers.BTCUSDT',
];
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const on=v=>String(v||'').toLowerCase()==='true';
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const iso=()=>new Date().toISOString();

function trimByTime(rows,windowMs=60000,now=Date.now()){
  return (Array.isArray(rows)?rows:[]).filter(x=>num(x.t)>=now-windowMs).slice(-4000);
}
function sortedBook(map,side){
  return [...map.entries()]
    .map(([p,q])=>[p,q])
    .filter(([p,q])=>num(p)>0&&num(q)>0)
    .sort((a,b)=>side==='bid'?num(b[0])-num(a[0]):num(a[0])-num(b[0]))
    .slice(0,50);
}
function bookMetrics(bids=[],asks=[]){
  const bb=num(bids[0]?.[0]),ba=num(asks[0]?.[0]),mid=bb>0&&ba>0?(bb+ba)/2:0;
  const n=(x)=>num(x?.[0])*num(x?.[1]);
  const band=(xs,bps)=>xs.filter(x=>mid>0&&Math.abs(num(x[0])-mid)/mid*10000<=bps);
  const sum=xs=>xs.reduce((s,x)=>s+n(x),0);
  const imb=(b,a)=>b+a>0?(b-a)/(b+a):0;
  const bid2=sum(band(bids,2)),ask2=sum(band(asks,2));
  const bid5=sum(band(bids,5)),ask5=sum(band(asks,5));
  const bid10=sum(band(bids,10)),ask10=sum(band(asks,10));
  const bs=num(bids[0]?.[1]),as=num(asks[0]?.[1]),den=bs+as;
  const microprice=den>0?(ba*bs+bb*as)/den:mid;
  return {
    bestBid:bb,bestAsk:ba,mid,
    spreadBps:mid>0&&ba>bb?(ba-bb)/mid*10000:999,
    microprice,
    micropriceEdgeBps:mid>0?(microprice-mid)/mid*10000:0,
    bidDepth2:bid2,askDepth2:ask2,bidDepth5:bid5,askDepth5:ask5,bidDepth10:bid10,askDepth10:ask10,
    imbalance2:imb(bid2,ask2),imbalance5:imb(bid5,ask5),imbalance10:imb(bid10,ask10),
    imbalance:imb(bid5,ask5),
    fragility:Math.abs(imb(bid10,ask10)),
  };
}
function tradeWindow(rows,windowMs,now=Date.now()){
  const x=rows.filter(z=>z.t>=now-windowMs);let buy=0,sell=0;
  for(const z of x){const n=z.p*z.q;if(z.side==='Buy')buy+=n;else if(z.side==='Sell')sell+=n;}
  const total=buy+sell,first=x[0]?.p||0,last=x.at(-1)?.p||0;
  return {
    buyNotional:buy,sellNotional:sell,totalNotional:total,deltaNotional:buy-sell,
    imbalance:total>0?(buy-sell)/total:0,trades:x.length,
    priceChangeBps:first>0&&last>0?(last-first)/first*10000:0,
  };
}
function tradesMetrics(rows=[]){
  const now=Date.now(),w1=tradeWindow(rows,1000,now),w3=tradeWindow(rows,3000,now),w5=tradeWindow(rows,5000,now),w15=tradeWindow(rows,15000,now),w60=tradeWindow(rows,60000,now);
  const b1=Math.max(w60.totalNotional/60,1),b3=Math.max(w60.totalNotional/20,1),b5=Math.max(w60.totalNotional/12,1);
  return {
    aggressorImbalance:w15.imbalance,deltaNotional:w15.deltaNotional,notional15s:w15.totalNotional,notional60s:w60.totalNotional,
    burst1x:w1.totalNotional/b1,burst3x:w3.totalNotional/b3,burst5x:w5.totalNotional/b5,
    priceChange1sBps:w1.priceChangeBps,priceChange3sBps:w3.priceChangeBps,priceChange5sBps:w5.priceChangeBps,
    window1s:w1,window3s:w3,window5s:w5,window15s:w15,window60s:w60,trades:rows.length,updateTime:rows.at(-1)?.t||0,
  };
}
function liquidationMetrics(rows=[]){
  let longUsd=0,shortUsd=0;
  for(const x of rows){
    const usd=x.p*x.q;
    if(x.side==='Buy')longUsd+=usd;
    else if(x.side==='Sell')shortUsd+=usd;
  }
  const total=longUsd+shortUsd;
  return {
    longLiquidationUsd:longUsd,
    shortLiquidationUsd:shortUsd,
    totalUsd:total,
    imbalance:total>0?(shortUsd-longUsd)/total:0,
    events:rows.length,
  };
}

export class BybitMarketStream {
  constructor(state,env){
    this.state=state;
    this.env=env;
    this.ws=null;
    this.connected=false;
    this.connecting=false;
    this.lastMessageAt=0;
    this.lastConnectAt=0;
    this.lastDisconnectAt=0;
    this.lastError=null;
    this.lastEvalAt=0;
    this.evalInFlight=false;
    this.evalPending=false;
    this.evalPendingReason=null;
    this.bids=new Map();
    this.asks=new Map();
    this.trades=[];
    this.liquidations=[];
    this.ticker={};
  }

  async fetch(request){
    const u=new URL(request.url);
    if(u.pathname.endsWith('/connect')){
      await this.ensureConnected();
      return json({ok:true,...this.health()});
    }
    if(u.pathname.endsWith('/snapshot')){
      if(!this.connected&&!this.connecting)await this.ensureConnected();
      return json({ok:true,data:this.snapshot()});
    }
    if(u.pathname.endsWith('/health'))return json({ok:true,...this.health()});
    if(u.pathname.endsWith('/disconnect')){
      try{this.ws?.close(1000,'operator_disconnect');}catch{}
      this.ws=null;this.connected=false;this.connecting=false;
      return json({ok:true,...this.health()});
    }
    return json({ok:false,error:'BYBIT_CLOUD_STREAM_ENDPOINT_NOT_FOUND'},404);
  }

  async alarm(){
    if(!this.connected&&!this.connecting)await this.ensureConnected();
    await this.state.storage.setAlarm(Date.now()+30000);
  }

  health(){
    return {
      version:VERSION,symbol:SYMBOL,url:WS_URL,connected:this.connected,connecting:this.connecting,
      lastConnectAt:this.lastConnectAt||null,lastMessageAt:this.lastMessageAt||null,lastDisconnectAt:this.lastDisconnectAt||null,
      messageAgeMs:this.lastMessageAt?Date.now()-this.lastMessageAt:null,lastError:this.lastError,
      topics:TOPICS,decisionTrigger:'CLOUD_BYBIT_WS_STATE_CHANGE',vpsRequired:false,
    };
  }

  snapshot(){
    const now=Date.now();
    this.trades=trimByTime(this.trades,60000,now);
    this.liquidations=trimByTime(this.liquidations,60000,now);
    const bids=sortedBook(this.bids,'bid'),asks=sortedBook(this.asks,'ask');
    return {
      symbol:SYMBOL,at:this.lastMessageAt||now,source:'CLOUDFLARE_BYBIT_WS',
      book:{...bookMetrics(bids,asks),b:bids,a:asks,updateTime:this.lastMessageAt||0},
      trades:tradesMetrics(this.trades),
      liquidations:liquidationMetrics(this.liquidations),
      ticker:this.ticker,
      health:this.health(),
    };
  }

  async ensureConnected(){
    if(this.connected||this.connecting)return;
    this.connecting=true;
    this.lastError=null;
    try{
      const response=await fetch(FETCH_URL,{headers:{Upgrade:'websocket'}});
      const ws=response.webSocket;
      if(!ws)throw new Error('WEBSOCKET_UPGRADE_REJECTED_'+response.status);
      ws.accept();
      this.ws=ws;
      this.connected=true;
      this.connecting=false;
      this.lastConnectAt=Date.now();
      this.lastError=null;
      ws.addEventListener('message',event=>{
        this.lastMessageAt=Date.now();
        try{this.onMessage(JSON.parse(String(event.data||'{}')));}catch(error){this.lastError='MESSAGE_PARSE:'+String(error?.message||error).slice(0,180);}
      });
      ws.addEventListener('close',event=>{
        this.connected=false;this.connecting=false;this.lastDisconnectAt=Date.now();this.ws=null;
        this.lastError=`WS_CLOSE_${event.code||0}_${String(event.reason||'').slice(0,80)}`;
        this.state.storage.setAlarm(Date.now()+1500).catch(()=>{});
      });
      ws.addEventListener('error',()=>{
        this.connected=false;this.connecting=false;this.lastError='WS_ERROR';
        this.state.storage.setAlarm(Date.now()+1500).catch(()=>{});
      });
      ws.send(JSON.stringify({op:'subscribe',args:TOPICS}));
      await this.state.storage.setAlarm(Date.now()+30000);
    }catch(error){
      this.connecting=false;this.connected=false;this.ws=null;this.lastError='CONNECT_FAILED:'+String(error?.message||error).slice(0,180);
      await this.state.storage.setAlarm(Date.now()+3000);
    }
  }

  onMessage(msg={}){
    const topic=String(msg.topic||'');
    if(topic.startsWith('orderbook.50.'))this.onBook(msg);
    else if(topic.startsWith('publicTrade.'))this.onTrades(msg);
    else if(topic.startsWith('allLiquidation.'))this.onLiquidations(msg);
    else if(topic.startsWith('tickers.'))this.onTicker(msg);
  }

  onBook(msg){
    const d=msg?.data||{};
    if(String(msg.type||'')==='snapshot'){this.bids.clear();this.asks.clear();}
    for(const [p,q] of d.b||[]){if(num(q)<=0)this.bids.delete(String(p));else this.bids.set(String(p),String(q));}
    for(const [p,q] of d.a||[]){if(num(q)<=0)this.asks.delete(String(p));else this.asks.set(String(p),String(q));}
    this.maybeEvaluate('ORDERBOOK');
  }

  onTrades(msg){
    for(const x of Array.isArray(msg?.data)?msg.data:[]){
      const row={t:num(x.T),side:String(x.S||''),q:num(x.v),p:num(x.p)};
      if(row.t>0&&row.q>0&&row.p>0)this.trades.push(row);
    }
    this.trades=trimByTime(this.trades);
    this.maybeEvaluate('TRADE');
  }

  onLiquidations(msg){
    for(const x of Array.isArray(msg?.data)?msg.data:[]){
      const row={t:num(x.T),side:String(x.S||''),q:num(x.v),p:num(x.p)};
      if(row.t>0&&row.q>0&&row.p>0)this.liquidations.push(row);
    }
    this.liquidations=trimByTime(this.liquidations);
    this.maybeEvaluate('LIQUIDATION',true);
  }

  onTicker(msg){
    const d=Array.isArray(msg?.data)?msg.data[0]:(msg?.data||{});
    this.ticker={...this.ticker,...d,ts:num(msg.ts)||Date.now()};
  }

  maybeEvaluate(reason,force=false){
    if(!on(this.env.BYBIT_AUTO_ENABLED))return;
    const now=Date.now();
    const minGap=Math.max(75,Math.min(2000,num(this.env.BYBIT_CLOUD_EVAL_MIN_GAP_MS)||150));
    if(this.evalInFlight){this.evalPending=true;this.evalPendingReason=reason;return;}
    if(!force&&now-this.lastEvalAt<minGap)return;
    const snap=this.snapshot();
    const flow=Math.abs(num(snap.trades?.window3s?.imbalance));
    const move=Math.abs(num(snap.trades?.window3s?.priceChangeBps));
    const book=Math.abs(num(snap.book?.imbalance5));
    const meaningful=force||flow>=.10||move>=1.2||book>=.22;
    if(!meaningful)return;
    this.lastEvalAt=now;this.evalInFlight=true;
    const task=Promise.resolve(runBybitAutoControlled(this.env,{trigger:'CLOUD_BYBIT_WS_STATE_CHANGE',triggerReason:reason,ctx:this.state}))
      .catch(error=>recordBybitAutoSchedulerError(this.env,error))
      .finally(()=>{
        this.evalInFlight=false;
        if(this.evalPending){
          const pendingReason=this.evalPendingReason||'COALESCED_STATE_CHANGE';
          this.evalPending=false;
          this.evalPendingReason=null;
          this.maybeEvaluate(pendingReason,true);
        }
      });
    if(typeof this.state.waitUntil==='function')this.state.waitUntil(task);
  }
}

export const BYBIT_CLOUD_MARKET_STREAM_VERSION=VERSION;
