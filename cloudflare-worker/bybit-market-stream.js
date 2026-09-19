import {recordBybitAutoSchedulerError} from './bybit-auto-controller.js';
import {runBybitMultiAssetControlled} from './bybit-multi-asset-controller.js';
import {BYBIT_TRADE_UNIVERSE,normalizeBybitSymbol} from './bybit-coin-profiles.js';

const VERSION='BYBIT_CLOUD_MARKET_STREAM_V4_PER_SYMBOL_DIRECT';
const DEFAULT_SYMBOL='BTCUSDT';
const WS_URL='wss://stream.bybit.com/v5/public/linear';
const FETCH_URL='https://stream.bybit.com/v5/public/linear';
const CORE_TICKER_SYMBOLS=[...new Set(BYBIT_TRADE_UNIVERSE.map(x=>normalizeBybitSymbol(x)).filter(Boolean))];
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const on=v=>String(v||'').toLowerCase()==='true';
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

function validSymbol(v=''){
  const s=normalizeBybitSymbol(v||DEFAULT_SYMBOL);
  return /^[A-Z0-9]{2,28}USDT$/.test(s)?s:null;
}
function topicsForSymbol(symbol){
  const s=validSymbol(symbol)||DEFAULT_SYMBOL;
  const base=[
    `orderbook.50.${s}`,
    `publicTrade.${s}`,
    `allLiquidation.${s}`,
    `kline.5.${s}`,
    `kline.15.${s}`,
    `kline.60.${s}`,
    `tickers.${s}`,
  ];
  if(s===DEFAULT_SYMBOL)for(const x of CORE_TICKER_SYMBOLS)if(x!==DEFAULT_SYMBOL)base.push('tickers.'+x);
  return [...new Set(base)];
}
function trimByTime(rows,windowMs=60000,now=Date.now()){
  return (Array.isArray(rows)?rows:[]).filter(x=>num(x.t)>=now-windowMs).slice(-4000);
}
function sortedBook(map,side){
  return [...map.entries()].map(([p,q])=>[p,q]).filter(([p,q])=>num(p)>0&&num(q)>0)
    .sort((a,b)=>side==='bid'?num(b[0])-num(a[0]):num(a[0])-num(b[0])).slice(0,50);
}
function bookMetrics(bids=[],asks=[]){
  const bb=num(bids[0]?.[0]),ba=num(asks[0]?.[0]),mid=bb>0&&ba>0?(bb+ba)/2:0;
  const n=x=>num(x?.[0])*num(x?.[1]),band=(xs,bps)=>xs.filter(x=>mid>0&&Math.abs(num(x[0])-mid)/mid*10000<=bps),sum=xs=>xs.reduce((s,x)=>s+n(x),0),imb=(b,a)=>b+a>0?(b-a)/(b+a):0;
  const bid2=sum(band(bids,2)),ask2=sum(band(asks,2)),bid5=sum(band(bids,5)),ask5=sum(band(asks,5)),bid10=sum(band(bids,10)),ask10=sum(band(asks,10)),bs=num(bids[0]?.[1]),as=num(asks[0]?.[1]),den=bs+as,microprice=den>0?(ba*bs+bb*as)/den:mid;
  return {bestBid:bb,bestAsk:ba,mid,spreadBps:mid>0&&ba>bb?(ba-bb)/mid*10000:999,microprice,micropriceEdgeBps:mid>0?(microprice-mid)/mid*10000:0,bidDepth2:bid2,askDepth2:ask2,bidDepth5:bid5,askDepth5:ask5,bidDepth10:bid10,askDepth10:ask10,imbalance2:imb(bid2,ask2),imbalance5:imb(bid5,ask5),imbalance10:imb(bid10,ask10),imbalance:imb(bid5,ask5),fragility:Math.abs(imb(bid10,ask10))};
}
function tradeWindow(rows,windowMs,now=Date.now()){
  const x=rows.filter(z=>z.t>=now-windowMs);let buy=0,sell=0;
  for(const z of x){const n=z.p*z.q;if(z.side==='Buy')buy+=n;else if(z.side==='Sell')sell+=n;}
  const total=buy+sell,first=x[0]?.p||0,last=x.at(-1)?.p||0;
  return {buyNotional:buy,sellNotional:sell,totalNotional:total,deltaNotional:buy-sell,imbalance:total>0?(buy-sell)/total:0,trades:x.length,priceChangeBps:first>0&&last>0?(last-first)/first*10000:0};
}
function tradesMetrics(rows=[]){
  const now=Date.now(),w1=tradeWindow(rows,1000,now),w3=tradeWindow(rows,3000,now),w5=tradeWindow(rows,5000,now),w15=tradeWindow(rows,15000,now),w60=tradeWindow(rows,60000,now),b1=Math.max(w60.totalNotional/60,1),b3=Math.max(w60.totalNotional/20,1),b5=Math.max(w60.totalNotional/12,1);
  return {aggressorImbalance:w15.imbalance,deltaNotional:w15.deltaNotional,notional15s:w15.totalNotional,notional60s:w60.totalNotional,burst1x:w1.totalNotional/b1,burst3x:w3.totalNotional/b3,burst5x:w5.totalNotional/b5,priceChange1sBps:w1.priceChangeBps,priceChange3sBps:w3.priceChangeBps,priceChange5sBps:w5.priceChangeBps,window1s:w1,window3s:w3,window5s:w5,window15s:w15,window60s:w60,trades:rows.length,updateTime:rows.at(-1)?.t||0};
}
function liquidationMetrics(rows=[]){
  let longUsd=0,shortUsd=0;for(const x of rows){const usd=x.p*x.q;if(x.side==='Buy')longUsd+=usd;else if(x.side==='Sell')shortUsd+=usd;}
  const total=longUsd+shortUsd;return {longLiquidationUsd:longUsd,shortLiquidationUsd:shortUsd,totalUsd:total,imbalance:total>0?(shortUsd-longUsd)/total:0,events:rows.length};
}

export class BybitMarketStream {
  constructor(state,env){
    this.state=state;this.env=env;this.symbol=null;this.ws=null;this.connected=false;this.connecting=false;this.lastMessageAt=0;this.lastConnectAt=0;this.lastDisconnectAt=0;this.lastError=null;this.lastEvalAt=0;this.evalInFlight=false;this.evalPending=false;this.evalPendingReason=null;this.bids=new Map();this.asks=new Map();this.trades=[];this.liquidations=[];this.ticker={};this.tickers=new Map();this.klines={'5':[],'15':[],'60':[]};
  }

  async resolveSymbol(requested=null){
    const req=validSymbol(requested||'');
    if(!this.symbol){try{this.symbol=validSymbol(await this.state.storage.get('symbol'))||null;}catch{}}
    const target=req||this.symbol||DEFAULT_SYMBOL;
    if(this.symbol&&this.symbol!==target)throw new Error(`STREAM_SYMBOL_MISMATCH_${this.symbol}_${target}`);
    if(!this.symbol){this.symbol=target;try{await this.state.storage.put('symbol',target);}catch{}}
    return this.symbol;
  }

  async fetch(request){
    const u=new URL(request.url),symbol=await this.resolveSymbol(u.searchParams.get('symbol'));
    if(u.pathname.endsWith('/connect')){await this.ensureConnected(symbol);await this.waitForFresh(500);return json({ok:true,...this.health()});}
    if(u.pathname.endsWith('/snapshot')){if(!this.connected&&!this.connecting)await this.ensureConnected(symbol);await this.waitForFresh(450);return json({ok:true,data:this.snapshot()});}
    if(u.pathname.endsWith('/universe-tickers')){if(symbol!==DEFAULT_SYMBOL)return json({ok:false,error:'UNIVERSE_TICKERS_REQUIRE_BTC_ANCHOR'},409);if(!this.connected&&!this.connecting)await this.ensureConnected(symbol);await this.waitForFresh(450);return json({ok:true,data:this.universeTickers()});}
    if(u.pathname.endsWith('/health'))return json({ok:true,...this.health()});
    if(u.pathname.endsWith('/disconnect')){try{this.ws?.close(1000,'operator_disconnect');}catch{}this.ws=null;this.connected=false;this.connecting=false;return json({ok:true,...this.health()});}
    return json({ok:false,error:'BYBIT_CLOUD_STREAM_ENDPOINT_NOT_FOUND'},404);
  }

  async alarm(){
    const symbol=await this.resolveSymbol(null);
    if(!this.connected&&!this.connecting)await this.ensureConnected(symbol);
    await this.state.storage.setAlarm(Date.now()+30000);
  }

  health(){
    const symbol=this.symbol||DEFAULT_SYMBOL,topics=topicsForSymbol(symbol);
    return {version:VERSION,symbol,url:WS_URL,connected:this.connected,connecting:this.connecting,lastConnectAt:this.lastConnectAt||null,lastMessageAt:this.lastMessageAt||null,lastDisconnectAt:this.lastDisconnectAt||null,messageAgeMs:this.lastMessageAt?Date.now()-this.lastMessageAt:null,lastError:this.lastError,topics,tickerSymbolCount:this.tickers.size,coreTickerTargetCount:symbol===DEFAULT_SYMBOL?CORE_TICKER_SYMBOLS.length:1,decisionTrigger:'CLOUD_BYBIT_WS_STATE_CHANGE',vpsRequired:false,perSymbolDirect:true};
  }

  snapshot(){
    const now=Date.now(),symbol=this.symbol||DEFAULT_SYMBOL;this.trades=trimByTime(this.trades,60000,now);this.liquidations=trimByTime(this.liquidations,60000,now);const bids=sortedBook(this.bids,'bid'),asks=sortedBook(this.asks,'ask');
    return {symbol,at:this.lastMessageAt||now,source:'CLOUDFLARE_BYBIT_WS',book:{...bookMetrics(bids,asks),b:bids,a:asks,updateTime:this.lastMessageAt||0},trades:tradesMetrics(this.trades),liquidations:liquidationMetrics(this.liquidations),ticker:this.ticker,klines:this.klines,health:this.health()};
  }

  universeTickers(){
    const now=Date.now(),rows=[];for(const [symbol,ticker] of this.tickers.entries()){const ts=num(ticker?.ts||ticker?.timestamp||0),ageMs=ts>0?now-ts:null;if(ageMs!==null&&ageMs>15000)continue;rows.push({...ticker,symbol,ts,ageMs});}
    return {source:'CLOUDFLARE_BYBIT_WS_TICKERS',at:now,rows,requestedSymbols:CORE_TICKER_SYMBOLS,freshCount:rows.length,targetCount:CORE_TICKER_SYMBOLS.length};
  }

  async waitForFresh(maxMs=450){
    const deadline=Date.now()+Math.max(0,maxMs);
    while(Date.now()<deadline){
      const snap=this.snapshot();
      if(this.connected&&snap.book?.mid>0&&snap.trades?.updateTime>0&&num(this.ticker?.lastPrice||this.ticker?.markPrice)>0)return;
      await sleep(15);
    }
  }

  async ensureConnected(symbolArg=null){
    const symbol=await this.resolveSymbol(symbolArg);if(this.connected||this.connecting)return;this.connecting=true;
    try{for(const interval of ['5','15','60']){const stored=await this.state.storage.get('klines:'+interval);if(Array.isArray(stored)&&stored.length)this.klines[interval]=stored.slice(-220);}}catch{}
    this.lastError=null;
    try{
      const response=await fetch(FETCH_URL,{headers:{Upgrade:'websocket'}}),ws=response.webSocket;if(!ws)throw new Error('WEBSOCKET_UPGRADE_REJECTED_'+response.status);ws.accept();this.ws=ws;this.connected=true;this.connecting=false;this.lastConnectAt=Date.now();this.lastError=null;
      ws.addEventListener('message',event=>{this.lastMessageAt=Date.now();try{this.onMessage(JSON.parse(String(event.data||'{}')));}catch(error){this.lastError='MESSAGE_PARSE:'+String(error?.message||error).slice(0,180);}});
      ws.addEventListener('close',event=>{this.connected=false;this.connecting=false;this.lastDisconnectAt=Date.now();this.ws=null;this.lastError=`WS_CLOSE_${event.code||0}_${String(event.reason||'').slice(0,80)}`;this.state.storage.setAlarm(Date.now()+1500).catch(()=>{});});
      ws.addEventListener('error',()=>{this.connected=false;this.connecting=false;this.lastError='WS_ERROR';this.state.storage.setAlarm(Date.now()+1500).catch(()=>{});});
      const topics=topicsForSymbol(symbol);for(let i=0;i<topics.length;i+=10)ws.send(JSON.stringify({op:'subscribe',args:topics.slice(i,i+10)}));
      await this.state.storage.setAlarm(Date.now()+30000);
    }catch(error){this.connecting=false;this.connected=false;this.ws=null;this.lastError='CONNECT_FAILED:'+String(error?.message||error).slice(0,180);await this.state.storage.setAlarm(Date.now()+3000);}
  }

  onMessage(msg={}){
    const topic=String(msg.topic||'');if(topic.startsWith('orderbook.50.'))this.onBook(msg);else if(topic.startsWith('publicTrade.'))this.onTrades(msg);else if(topic.startsWith('allLiquidation.'))this.onLiquidations(msg);else if(topic.startsWith('kline.'))this.onKline(msg);else if(topic.startsWith('tickers.'))this.onTicker(msg);
  }
  onBook(msg){const d=msg?.data||{};if(String(msg.type||'')==='snapshot'){this.bids.clear();this.asks.clear();}for(const [p,q] of d.b||[]){if(num(q)<=0)this.bids.delete(String(p));else this.bids.set(String(p),String(q));}for(const [p,q] of d.a||[]){if(num(q)<=0)this.asks.delete(String(p));else this.asks.set(String(p),String(q));}this.maybeEvaluate('ORDERBOOK');}
  onTrades(msg){for(const x of Array.isArray(msg?.data)?msg.data:[]){const row={t:num(x.T),side:String(x.S||''),q:num(x.v),p:num(x.p)};if(row.t>0&&row.q>0&&row.p>0)this.trades.push(row);}this.trades=trimByTime(this.trades);this.maybeEvaluate('TRADE');}
  onLiquidations(msg){for(const x of Array.isArray(msg?.data)?msg.data:[]){const row={t:num(x.T),side:String(x.S||''),q:num(x.v),p:num(x.p)};if(row.t>0&&row.q>0&&row.p>0)this.liquidations.push(row);}this.liquidations=trimByTime(this.liquidations);this.maybeEvaluate('LIQUIDATION',true);}
  onTicker(msg){const d=Array.isArray(msg?.data)?msg.data[0]:(msg?.data||{}),topic=String(msg.topic||''),symbol=validSymbol(d.symbol||topic.split('.').at(-1)||'')||'',next={...(this.tickers.get(symbol)||{}),...d,symbol,ts:num(msg.ts)||Date.now()};if(symbol)this.tickers.set(symbol,next);if(symbol===(this.symbol||DEFAULT_SYMBOL))this.ticker=next;}
  onKline(msg){const topic=String(msg.topic||''),parts=topic.split('.'),interval=String(parts[1]||''),rows=Array.isArray(msg?.data)?msg.data:[msg?.data].filter(Boolean);if(!this.klines[interval])return;for(const x of rows){const row={t:num(x.start),o:num(x.open),h:num(x.high),l:num(x.low),c:num(x.close),v:num(x.volume),turnover:num(x.turnover),confirm:x.confirm===true};if(!(row.t>0&&row.c>0))continue;const arr=this.klines[interval],i=arr.findIndex(z=>z.t===row.t);if(i>=0)arr[i]=row;else arr.push(row);arr.sort((a,b)=>a.t-b.t);this.klines[interval]=arr.slice(-220);const persist=this.state.storage.put('klines:'+interval,this.klines[interval]).catch(()=>{});if(typeof this.state.waitUntil==='function')this.state.waitUntil(persist);}}

  maybeEvaluate(reason,force=false){
    if(!on(this.env.BYBIT_AUTO_ENABLED))return;const now=Date.now(),minGap=Math.max(75,Math.min(2000,num(this.env.BYBIT_CLOUD_EVAL_MIN_GAP_MS)||150));if(this.evalInFlight){this.evalPending=true;this.evalPendingReason=reason;return;}if(!force&&now-this.lastEvalAt<minGap)return;
    const snap=this.snapshot(),flow=Math.abs(num(snap.trades?.window3s?.imbalance)),move=Math.abs(num(snap.trades?.window3s?.priceChangeBps)),book=Math.abs(num(snap.book?.imbalance5)),meaningful=force||flow>=.10||move>=1.2||book>=.22;if(!meaningful)return;
    this.lastEvalAt=now;this.evalInFlight=true;const symbol=this.symbol||DEFAULT_SYMBOL;
    const task=Promise.resolve(runBybitMultiAssetControlled(this.env,{symbol,trigger:'CLOUD_BYBIT_WS_STATE_CHANGE',triggerReason:reason,ctx:this.state})).catch(error=>recordBybitAutoSchedulerError(this.env,error)).finally(()=>{this.evalInFlight=false;if(this.evalPending){const pendingReason=this.evalPendingReason||'COALESCED_STATE_CHANGE';this.evalPending=false;this.evalPendingReason=null;this.maybeEvaluate(pendingReason,true);}});
    if(typeof this.state.waitUntil==='function')this.state.waitUntil(task);
  }
}

export const BYBIT_CLOUD_MARKET_STREAM_VERSION=VERSION;
