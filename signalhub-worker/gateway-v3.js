import legacy from './gateway.js';

const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.4.0';
const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_05';
const MT5_QUOTE_TTL = 120;
const MT5_HEARTBEAT_TTL = 180;
const SIGNAL_TTL = 60 * 60 * 24 * 90;
const CRYPTO_LASTGOOD_TTL = 60 * 30;
const CRYPTO_CACHE_MS = 1500;
const PROVIDER_TIMEOUT_MS = 7000;
const BYBIT_BASES = ['https://api.bybit.com', 'https://api.bytick.com'];
const FOREX = [
  'AUDCAD','AUDCHF','AUDJPY','AUDNZD','AUDUSD','CADCHF','CADJPY','CHFJPY',
  'EURAUD','EURCAD','EURCHF','EURGBP','EURJPY','EURNZD','EURUSD',
  'GBPAUD','GBPCAD','GBPCHF','GBPJPY','GBPNZD','GBPUSD',
  'NZDCAD','NZDCHF','NZDJPY','NZDUSD','USDCAD','USDCHF','USDJPY'
];
const V31_RELEASE = {
  versionCode: 10,
  versionName: '3.4.0',
  title: 'SignalHub 3.4.0',
  releasedAt: '2026-09-09T00:00:00Z',
  mandatory: false,
  minSupportedVersionCode: 6,
  artifactName: 'SignalHub-Android-v3.4.0',
  notes: [
    'Realtime Durable Object price bus + WebSocket stream for Exness MT5 quotes.',
    'LIMIT and STOP pending orders are displayed separately and become LIVE immediately when trigger price is crossed.',
    'Low-latency Exness patch: 500ms bridge target, heartbeat-aware health, faster Android live refresh.',
    'V3.2 rebuild: hard partition integrity for FOREX/CRYPTO and SCALP/SWING.',
    'Signal payloads expose lifecycle plus ENTRY/SL/TP1/TP2/TP3 without changing the final tracked TP.',
    'New Forex V31 signals refuse cross-style symbol overlap while an existing exposure is active.',
    'Unified FOREX / CRYPTO and SCALP / SWING signal partitions.',
    'Exness MT5 remains execution-price authority for Forex and confirms fills/TP/SL.',
    'Crypto market data uses Bybit first with OKX/Binance public-data fallback and never labels fallback quotes as Bybit live.',
    'Crypto signals use multi-timeframe EMA/RSI/ATR structure, liquidity/spread gates, anti-FOMO extension checks and MARKET/LIMIT/STOP routing.',
    'Signal cards show ENTRY / NOW / TP / SL and live R progress; history and win rate are calculated from resolved TP/SL only.',
    'No score is presented as a guaranteed win probability.'
  ]
};

const json = (body, status = 200, extra = {}) => new Response(JSON.stringify(body, null, 2), {
  status,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store, no-cache, must-revalidate',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'content-type, authorization, x-signalhub-bridge',
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    ...extra,
  },
});
const num = v => { const n = Number(v); return Number.isFinite(n) ? n : null; };
const nowIso = () => new Date().toISOString();
const canonical = s => String(s || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
const isFinitePositive = v => Number.isFinite(Number(v)) && Number(v) > 0;
const sleep = ms => new Promise(r => setTimeout(r, ms));


export class MT5LiveState {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.clients = new Set();
  }
  async fetch(req) {
    const url = new URL(req.url);
    if (req.headers.get('Upgrade') === 'websocket') {
      const pair = new WebSocketPair();
      const client = pair[0], server = pair[1];
      server.accept();
      this.clients.add(server);
      const drop = () => this.clients.delete(server);
      server.addEventListener('close', drop);
      server.addEventListener('error', drop);
      try {
        const quotes = await this.state.storage.get('quotes');
        const heartbeat = await this.state.storage.get('heartbeat');
        if (quotes) server.send(JSON.stringify({type:'quotes', ...quotes, heartbeat:heartbeat||null}));
      } catch {}
      return new Response(null, {status:101, webSocket:client});
    }
    if (req.method === 'POST' && url.pathname === '/prices') {
      const packet = await req.json();
      await this.state.storage.put('quotes', packet);
      const msg = JSON.stringify({type:'quotes', ...packet});
      for (const ws of [...this.clients]) {
        try { ws.send(msg); } catch { this.clients.delete(ws); }
      }
      return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt}), {headers:{'content-type':'application/json'}});
    }
    if (req.method === 'POST' && url.pathname === '/heartbeat') {
      const heartbeat = await req.json();
      await this.state.storage.put('heartbeat', heartbeat);
      const msg = JSON.stringify({type:'heartbeat', heartbeat});
      for (const ws of [...this.clients]) {
        try { ws.send(msg); } catch { this.clients.delete(ws); }
      }
      return new Response(JSON.stringify({ok:true,receivedAt:heartbeat.receivedAt}), {headers:{'content-type':'application/json'}});
    }
    if (url.pathname === '/snapshot') {
      const [quotes,heartbeat] = await Promise.all([this.state.storage.get('quotes'),this.state.storage.get('heartbeat')]);
      return new Response(JSON.stringify({ok:!!quotes,quotes:quotes||null,heartbeat:heartbeat||null}), {headers:{'content-type':'application/json','cache-control':'no-store'}});
    }
    return new Response('not found',{status:404});
  }
}
function mt5LiveStub(env){
  if(!env?.MT5_LIVE)return null;
  return env.MT5_LIVE.get(env.MT5_LIVE.idFromName('primary'));
}
async function readMt5Realtime(env){
  const stub=mt5LiveStub(env);
  if(stub){
    try{const r=await stub.fetch('https://mt5-live/snapshot');if(r.ok)return await r.json()}catch{}
  }
  let quotes=null,heartbeat=null;
  try{const raw=await env?.SIGNALS_KV?.get('v3:mt5:quotes:latest');if(raw)quotes=JSON.parse(raw)}catch{}
  try{const raw=await env?.SIGNALS_KV?.get('v3:mt5:heartbeat:latest');if(raw)heartbeat=JSON.parse(raw)}catch{}
  return {ok:!!quotes,quotes,heartbeat};
}

async function fetchJson(url, init = {}, timeoutMs = PROVIDER_TIMEOUT_MS) {
  const c = new AbortController();
  const id = setTimeout(() => c.abort('timeout'), timeoutMs);
  try {
    const r = await fetch(url, {
      ...init,
      signal: c.signal,
      headers: {
        accept: 'application/json',
        'user-agent': 'SignalHub-V3/3.1',
        ...(init.headers || {}),
      },
      cf: { cacheTtl: 0, cacheEverything: false, ...(init.cf || {}) },
    });
    if (!r.ok) throw new Error(`HTTP_${r.status}`);
    return await r.json();
  } finally { clearTimeout(id); }
}

async function readJson(req, maxBytes = 1_000_000) {
  const raw = await req.text();
  if (raw.length > maxBytes) throw new Error('PAYLOAD_TOO_LARGE');
  try { return JSON.parse(raw || '{}'); }
  catch { throw new Error('INVALID_JSON'); }
}
function bridgeAllowed(req, env) {
  const expected = String(env?.MT5_BRIDGE_TOKEN || '').trim();
  if (!expected) return String(req.headers.get('x-signalhub-bridge') || '').startsWith('SIGNALHUB-EXNESS-BRIDGE-');
  return String(req.headers.get('authorization') || '') === `Bearer ${expected}`;
}
function sanitizeQuote(q) {
  const symbol = canonical(q?.symbol), brokerSymbol = String(q?.brokerSymbol || '').trim();
  const bid = num(q?.bid), ask = num(q?.ask), last = num(q?.last), spreadPoints = num(q?.spreadPoints), tickTimeMsc = Number(q?.tickTimeMsc || 0);
  if (!symbol || !isFinitePositive(bid) || !isFinitePositive(ask) || ask < bid) return null;
  return {symbol,brokerSymbol,bid,ask,mid:(bid+ask)/2,last:isFinitePositive(last)?last:null,spreadPoints:Number.isFinite(spreadPoints)?spreadPoints:null,tickTimeMsc:tickTimeMsc>0?tickTimeMsc:null};
}
async function mt5Prices(req, env) {
  if (!bridgeAllowed(req,env)) return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  const body=await readJson(req,2_000_000), quotes=(Array.isArray(body?.quotes)?body.quotes:[]).slice(0,120).map(sanitizeQuote).filter(Boolean), receivedAt=nowIso();
  const packet={ok:true,version:V3_VERSION,source:'EXNESS_MT5',bridgeVersion:String(body?.bridgeVersion||''),server:String(body?.server||''),receivedAt,quotes,count:quotes.length};
  const stub=mt5LiveStub(env);
  if(stub){
    const r=await stub.fetch('https://mt5-live/prices',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(packet)});
    if(r.ok)return json({ok:true,accepted:quotes.length,receivedAt,transport:'DURABLE_OBJECT_REALTIME'});
  }
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_REALTIME_STORE'},503);
  await env.SIGNALS_KV.put('v3:mt5:quotes:latest',JSON.stringify(packet),{expirationTtl:MT5_QUOTE_TTL});
  return json({ok:true,accepted:quotes.length,receivedAt,transport:'KV_FALLBACK'});
}
async function mt5Heartbeat(req,env){
  if(!bridgeAllowed(req,env))return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  const body=await readJson(req),receivedAt=nowIso();
  const heartbeat={bridgeVersion:String(body?.bridgeVersion||''),status:String(body?.status||''),server:String(body?.server||''),company:String(body?.company||''),terminalConnected:body?.terminalConnected===true,tradeAllowed:body?.tradeAllowed===true,resolvedSymbols:Number(body?.resolvedSymbols||0),positions:Number(body?.positions||0),orders:Number(body?.orders||0),queuedEvents:Number(body?.queuedEvents||0),receivedAt};
  const stub=mt5LiveStub(env);
  if(stub){
    const r=await stub.fetch('https://mt5-live/heartbeat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(heartbeat)});
    if(r.ok)return json({ok:true,receivedAt,transport:'DURABLE_OBJECT_REALTIME'});
  }
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_REALTIME_STORE'},503);
  await env.SIGNALS_KV.put('v3:mt5:heartbeat:latest',JSON.stringify(heartbeat),{expirationTtl:MT5_HEARTBEAT_TTL});
  return json({ok:true,receivedAt,transport:'KV_FALLBACK'});
}
async function loadSignalById(kv,id){
  for(const key of [`signal:${id}`,`v31:signal:${id}`]){
    const raw=await kv.get(key); if(!raw)continue; try{return {key,signal:JSON.parse(raw)}}catch{}
  }
  return null;
}
async function patchSignalFromBrokerEvent(env,evt,receivedAt){
  const id=String(evt?.signalId||'').trim(); if(!id||!env?.SIGNALS_KV)return {patched:false,reason:'NO_SIGNAL_ID'};
  const found=await loadSignalById(env.SIGNALS_KV,id); if(!found)return {patched:false,reason:'SIGNAL_NOT_FOUND'};
  const s=found.signal,event=String(evt?.event||'').toUpperCase(),price=num(evt?.price);
  if(event==='BROKER_FILL_CONFIRMED'){
    s.status='OPEN';s.triggeredAt=s.triggeredAt||receivedAt;s.brokerFilledAt=receivedAt;s.brokerConfirmed=true;s.executionSource='EXNESS_MT5_DEAL';
    if(isFinitePositive(price)){s.actualEntry=price;s.entry=price;s.lastPrice=price;}
    s.brokerSymbol=String(evt?.brokerSymbol||s.brokerSymbol||'');s.brokerDealTicket=String(evt?.dealTicket||'');s.brokerOrderTicket=String(evt?.orderTicket||'');
  }else if(event==='BROKER_CLOSE_CONFIRMED'){
    const reason=String(evt?.dealReason||'BROKER_CLOSE').toUpperCase();s.brokerClosedAt=receivedAt;s.brokerClosePrice=isFinitePositive(price)?price:null;s.brokerCloseConfirmed=true;s.brokerCloseReason=reason;s.executionSource='EXNESS_MT5_DEAL';
    if((reason==='TP'||reason==='SL')&&isFinitePositive(price)){
      const entry=num(s.actualEntry??s.entry),stop=num(s.sl),risk=isFinitePositive(entry)&&isFinitePositive(stop)?Math.abs(entry-stop):null,dir=String(s.side||'').toUpperCase()==='LONG'?1:-1;
      s.status='CLOSED';s.outcome=reason;s.closedAt=receivedAt;s.exitPrice=price;if(risk&&risk>0)s.resultR=Number((dir*(price-entry)/risk).toFixed(4));s.resolution='BROKER_CONFIRMED_'+reason;
    }
  }else return {patched:false,reason:'EVENT_NOT_PATCHABLE'};
  s.lastCheckedAt=receivedAt;await env.SIGNALS_KV.put(found.key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});
  return {patched:true,status:s.status,outcome:s.outcome||null};
}
async function mt5Event(req,env){
  if(!bridgeAllowed(req,env))return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_KV'},503);
  const evt=await readJson(req),receivedAt=nowIso(),deal=String(evt?.dealTicket||'').trim(),eventId=deal||`${Date.now()}-${Math.random().toString(36).slice(2)}`,record={...evt,receivedAt,eventId,source:'EXNESS_MT5'};
  await env.SIGNALS_KV.put(`v3:mt5:event:${eventId}`,JSON.stringify(record),{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put('v3:mt5:event:latest',JSON.stringify(record),{expirationTtl:SIGNAL_TTL});
  return json({ok:true,eventId,receivedAt,signalPatch:await patchSignalFromBrokerEvent(env,evt,receivedAt)});
}
async function mt5Live(env){
  const snap=await readMt5Realtime(env),quotes=snap?.quotes||null,heartbeat=snap?.heartbeat||null;
  let lastEvent=null;try{const er=await env?.SIGNALS_KV?.get('v3:mt5:event:latest');if(er)lastEvent=JSON.parse(er)}catch{}
  const qAt=Date.parse(quotes?.receivedAt||''),hAt=Date.parse(heartbeat?.receivedAt||''),quoteAgeMs=Number.isFinite(qAt)?Math.max(0,Date.now()-qAt):null,heartbeatAgeMs=Number.isFinite(hAt)?Math.max(0,Date.now()-hAt):null;
  const terminalConnected=heartbeat?.terminalConnected!==false;
  const state=quoteAgeMs===null?'OFFLINE':!terminalConnected?'OFFLINE':heartbeatAgeMs!==null&&heartbeatAgeMs>10000?'OFFLINE':quoteAgeMs<=1800?'LIVE':quoteAgeMs<=4000?'DELAYED':quoteAgeMs<=10000?'STALE':'OFFLINE';
  return json({ok:!!quotes,version:V3_VERSION,market:'FOREX_EXNESS',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME':'KV_FALLBACK',stream:'/v3/forex/stream',state,quoteAgeMs,heartbeatAgeMs,quotes:quotes?.quotes||[],count:quotes?.count||0,heartbeat,lastEvent:lastEvent?{event:lastEvent.event,signalId:lastEvent.signalId||'',brokerSymbol:lastEvent.brokerSymbol||'',price:num(lastEvent.price),dealReason:lastEvent.dealReason||'',receivedAt:lastEvent.receivedAt}:null},quotes?200:503);
}
async function mt5Stream(req,env){
  const stub=mt5LiveStub(env);if(!stub)return new Response('realtime stream unavailable',{status:503});
  const headers=new Headers(req.headers);headers.set('Upgrade','websocket');
  return stub.fetch(new Request('https://mt5-live/stream',{method:'GET',headers}));
}

function cleanBybitTicker(x){
  const bid=num(x?.bid1Price),ask=num(x?.ask1Price),last=num(x?.lastPrice),turn=num(x?.turnover24h),oi=num(x?.openInterestValue),fr=num(x?.fundingRate),ch=num(x?.price24hPcnt),mid=isFinitePositive(bid)&&isFinitePositive(ask)?(bid+ask)/2:last;
  return {symbol:canonical(x?.symbol),lastPrice:last,markPrice:num(x?.markPrice),indexPrice:num(x?.indexPrice),bid,ask,spreadBps:isFinitePositive(mid)&&isFinitePositive(ask)&&Number.isFinite(bid)?(ask-bid)/mid*10000:null,turnover24h:turn,volume24h:num(x?.volume24h),openInterestValue:oi,fundingRate:fr,change24hPct:Number.isFinite(ch)?ch*100:null,nextFundingTime:Number(x?.nextFundingTime||0)||null,exchange:'BYBIT',source:'BYBIT_V5'};
}
async function bybitFetch(path){
  let lastErr=null;for(const base of BYBIT_BASES){try{const data=await fetchJson(base+path);if(Number(data?.retCode||0)!==0)throw new Error(`BYBIT_${data?.retCode}:${data?.retMsg||''}`);return data}catch(e){lastErr=e;}}
  throw lastErr||new Error('BYBIT_UNAVAILABLE');
}
async function bybitTickers(){
  const raw=await bybitFetch('/v5/market/tickers?category=linear');
  const rows=(raw?.result?.list||[]).map(cleanBybitTicker).filter(x=>x.symbol.endsWith('USDT')&&isFinitePositive(x.lastPrice));rows.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));
  return {rows,provider:'BYBIT',exchangeTime:Number(raw?.time||0),receivedAt:nowIso(),live:true};
}
async function okxTickers(){
  const raw=await fetchJson('https://www.okx.com/api/v5/market/tickers?instType=SWAP');if(String(raw?.code||'0')!=='0')throw new Error(`OKX_${raw?.code}:${raw?.msg||''}`);
  const rows=[];for(const x of raw?.data||[]){const inst=String(x?.instId||'');if(!inst.endsWith('-USDT-SWAP'))continue;const last=num(x?.last),bid=num(x?.bidPx),ask=num(x?.askPx),baseVol=num(x?.vol24h),quoteVol=num(x?.volCcy24h),open=num(x?.open24h),mid=isFinitePositive(bid)&&isFinitePositive(ask)?(bid+ask)/2:last;rows.push({symbol:canonical(inst.replace('-SWAP','')),lastPrice:last,bid,ask,spreadBps:isFinitePositive(mid)&&isFinitePositive(ask)&&Number.isFinite(bid)?(ask-bid)/mid*10000:null,turnover24h:isFinitePositive(quoteVol)?quoteVol:(isFinitePositive(baseVol)&&isFinitePositive(last)?baseVol*last:null),volume24h:baseVol,openInterestValue:null,fundingRate:null,change24hPct:isFinitePositive(open)&&isFinitePositive(last)?(last/open-1)*100:null,exchange:'OKX',source:'OKX_V5'});}
  const filtered=rows.filter(x=>x.symbol.endsWith('USDT')&&isFinitePositive(x.lastPrice));filtered.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));return {rows:filtered,provider:'OKX',exchangeTime:Date.now(),receivedAt:nowIso(),live:true};
}
async function binanceTickers(){
  const raw=await fetchJson('https://fapi.binance.com/fapi/v1/ticker/24hr');if(!Array.isArray(raw))throw new Error('BINANCE_BAD_JSON');
  const rows=raw.filter(x=>String(x?.symbol||'').endsWith('USDT')).map(x=>{const last=num(x.lastPrice),bid=num(x.bidPrice),ask=num(x.askPrice),mid=isFinitePositive(bid)&&isFinitePositive(ask)?(bid+ask)/2:last;return {symbol:canonical(x.symbol),lastPrice:last,bid,ask,spreadBps:isFinitePositive(mid)&&isFinitePositive(ask)&&Number.isFinite(bid)?(ask-bid)/mid*10000:null,turnover24h:num(x.quoteVolume),volume24h:num(x.volume),openInterestValue:null,fundingRate:null,change24hPct:num(x.priceChangePercent),exchange:'BINANCE',source:'BINANCE_FAPI'};}).filter(x=>isFinitePositive(x.lastPrice));rows.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));return {rows,provider:'BINANCE',exchangeTime:Date.now(),receivedAt:nowIso(),live:true};
}
async function loadCryptoSnapshot(env){
  const errors=[];for(const fn of [bybitTickers,okxTickers,binanceTickers]){try{const snap=await fn();if(snap.rows.length){if(env?.SIGNALS_KV)await env.SIGNALS_KV.put('v31:crypto:tickers:lastgood',JSON.stringify(snap),{expirationTtl:CRYPTO_LASTGOOD_TTL});return {...snap,errors};}}catch(e){errors.push(String(e?.message||e));}}
  if(env?.SIGNALS_KV){const raw=await env.SIGNALS_KV.get('v31:crypto:tickers:lastgood');if(raw){try{const old=JSON.parse(raw),ageMs=Math.max(0,Date.now()-Date.parse(old.receivedAt||''));return {...old,live:false,staleFallback:true,ageMs,errors};}catch{}}}
  throw new Error('CRYPTO_ALL_PROVIDERS_UNAVAILABLE:'+errors.join('|'));
}
async function cryptoTickers(url,env){
  const snap=await loadCryptoSnapshot(env),limit=Math.min(1000,Math.max(1,Number(url.searchParams.get('limit')||1000)));
  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:snap.live!==false,staleFallback:snap.staleFallback===true,ageMs:snap.ageMs??0,count:snap.rows.length,tickers:snap.rows.slice(0,limit),exchangeTime:snap.exchangeTime,receivedAt:snap.receivedAt,providerErrors:snap.errors||[],note:'Bybit is preferred. Any fallback exchange is explicitly labeled and is never presented as Bybit live.'});
}
function discoveryScore(t,style){
  const turn=Math.max(0,t.turnover24h||0),spread=Math.max(0,t.spreadBps??999),change=Math.abs(t.change24hPct||0),oi=Math.max(0,t.openInterestValue||0),fund=Math.abs((t.fundingRate||0)*100),liq=Math.min(1,Math.log10(Math.max(1,turn))/9),oiScore=oi>0?Math.min(1,Math.log10(Math.max(1,oi))/9):.45,spreadScore=Math.max(0,1-spread/(style==='SCALP'?15:35)),moveScore=Math.min(1,change/(style==='SCALP'?8:18)),fundingPenalty=Math.min(.35,fund/2);
  return 100*Math.max(0,Math.min(1,.40*liq+.22*spreadScore+.17*moveScore+.15*oiScore+.06*(1-fundingPenalty)));
}
async function cryptoDiscovery(url,env){
  const style=String(url.searchParams.get('style')||'scalp').toUpperCase()==='SWING'?'SWING':'SCALP',limit=Math.min(100,Math.max(5,Number(url.searchParams.get('limit')||40))),snap=await loadCryptoSnapshot(env),all=snap.rows,eligible=all.filter(x=>(x.turnover24h||0)>=1_000_000&&(x.spreadBps??999)<=(style==='SCALP'?20:50)),candidates=eligible.map(t=>({...t,discoveryScore:Number(discoveryScore(t,style).toFixed(1))})).sort((a,b)=>b.discoveryScore-a.discoveryScore).slice(0,limit);
  return json({ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,eligible:eligible.length,candidates,classification:'DISCOVERY_ONLY_NOT_TRADE_SIGNAL',note:'This list is only the deep-analysis universe. Trade signals are emitted by /v3/scan after multi-timeframe confirmation.',receivedAt:snap.receivedAt});
}

function ema(values,period){if(!Array.isArray(values)||values.length<period)return null;const k=2/(period+1);let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;for(let i=period;i<values.length;i++)x=values[i]*k+x*(1-k);return x;}
function emaSeries(values,period){if(values.length<period)return[];const out=new Array(values.length).fill(null),k=2/(period+1);let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;out[period-1]=x;for(let i=period;i<values.length;i++){x=values[i]*k+x*(1-k);out[i]=x;}return out;}
function rsi(values,period=14){if(values.length<period+1)return null;let g=0,l=0;for(let i=values.length-period;i<values.length;i++){const d=values[i]-values[i-1];if(d>=0)g+=d;else l-=d;}if(l===0)return 100;const rs=(g/period)/(l/period);return 100-100/(1+rs);}
function atr(rows,period=14){if(rows.length<period+1)return null;const trs=[];for(let i=1;i<rows.length;i++){const p=rows[i-1].c,r=rows[i];trs.push(Math.max(r.h-r.l,Math.abs(r.h-p),Math.abs(r.l-p)));}const a=trs.slice(-period);return a.reduce((x,y)=>x+y,0)/a.length;}
function tfStats(rows){
  if(!rows||rows.length<55)return null;const closes=rows.map(x=>x.c),e20s=emaSeries(closes,20),e50=ema(closes,50),e20=e20s.at(-1),e20Prev=e20s[Math.max(19,e20s.length-6)],rr=rsi(closes,14),aa=atr(rows,14),last=rows.at(-1),prior=rows.slice(-22,-2),priorHigh=Math.max(...prior.map(x=>x.h)),priorLow=Math.min(...prior.map(x=>x.l));
  if(![e20,e50,rr,aa,last?.c].every(Number.isFinite)||aa<=0)return null;const trend=last.c>e20&&e20>e50?1:last.c<e20&&e20<e50?-1:0,slope=e20Prev?((e20-e20Prev)/aa):0,momentum=rr>=52?1:rr<=48?-1:0;
  return {close:last.c,ema20:e20,ema50:e50,rsi:rr,atr:aa,trend,slope,priorHigh,priorLow,extensionAtr:Math.abs(last.c-e20)/aa};
}
const intervalMap={SCALP:['5m','15m','1h'],SWING:['1h','4h','1d']};
async function bybitCandles(symbol,interval,limit=120){const m={"5m":'5',"15m":'15',"1h":'60',"4h":'240',"1d":'D'}[interval],raw=await bybitFetch(`/v5/market/kline?category=linear&symbol=${encodeURIComponent(symbol)}&interval=${m}&limit=${limit}`),rows=(raw?.result?.list||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('BYBIT_CANDLES_SHORT');return rows;}
async function okxCandles(symbol,interval,limit=120){const inst=symbol.replace(/USDT$/,'-USDT-SWAP'),bar={"5m":'5m',"15m":'15m',"1h":'1H',"4h":'4H',"1d":'1D'}[interval],raw=await fetchJson(`https://www.okx.com/api/v5/market/candles?instId=${encodeURIComponent(inst)}&bar=${bar}&limit=${limit}`);if(String(raw?.code||'0')!=='0')throw new Error('OKX_CANDLES_'+raw?.code);const rows=(raw?.data||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('OKX_CANDLES_SHORT');return rows;}
async function binanceCandles(symbol,interval,limit=120){const raw=await fetchJson(`https://fapi.binance.com/fapi/v1/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`);if(!Array.isArray(raw))throw new Error('BINANCE_CANDLES_BAD');const rows=raw.map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c));if(rows.length<55)throw new Error('BINANCE_CANDLES_SHORT');return rows;}
async function providerCandles(symbol,interval,preferred){
  const order=preferred==='OKX'?[okxCandles,bybitCandles,binanceCandles]:preferred==='BINANCE'?[binanceCandles,bybitCandles,okxCandles]:[bybitCandles,okxCandles,binanceCandles];let last=null;for(const fn of order){try{return await fn(symbol,interval)}catch(e){last=e;}}throw last||new Error('NO_CANDLES');
}
function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,dir=(a.trend===b.trend&&a.trend!==0&&c.trend!==-a.trend)?a.trend:0;if(!dir)return null;
  const directionalRsi=dir>0?(a.rsi>=50&&a.rsi<=70&&b.rsi>=50):(a.rsi<=50&&a.rsi>=30&&b.rsi<=50);if(!directionalRsi)return null;
  const antiFomo=a.extensionAtr<=1.55&&!(Math.abs(t.change24hPct||0)>18&&a.extensionAtr>.8);if(!antiFomo)return null;
  const spread=t.spreadBps??999,maxSpread=style==='SCALP'?12:30;if(spread>maxSpread)return null;
  const liq=Math.min(1,Math.log10(Math.max(1,t.turnover24h||0))/9),align=(a.trend===dir?1:0)+(b.trend===dir?1:0)+(c.trend===dir?1:0),slopeOk=dir*a.slope>-.05&&dir*b.slope>-.05,extensionPenalty=Math.min(18,a.extensionAtr*10),fundPenalty=Math.min(8,Math.abs((t.fundingRate||0)*100)*8),score=64+align*6+(slopeOk?5:0)+liq*10-Math.min(12,spread/(style==='SCALP'?1.5:3))-extensionPenalty-fundPenalty;
  const threshold=style==='SCALP'?84:86;if(score<threshold)return null;
  const px=t.lastPrice,atr1=a.atr,nearBreak=dir>0?(a.priorHigh-px)/atr1:(px-a.priorLow)/atr1;let orderType='MARKET',entry=px;
  if(nearBreak>=0&&nearBreak<=.25&&a.extensionAtr<=.75){orderType='STOP';entry=dir>0?a.priorHigh+.08*atr1:a.priorLow-.08*atr1;}
  else if(a.extensionAtr>.42){orderType='LIMIT';entry=a.ema20;}
  const structure=dir>0?Math.min(...[a.priorLow,entry-(style==='SCALP'?1.20:1.55)*atr1]):Math.max(...[a.priorHigh,entry+(style==='SCALP'?1.20:1.55)*atr1]);
  let sl=dir>0?Math.min(entry-.9*atr1,structure-.08*atr1):Math.max(entry+.9*atr1,structure+.08*atr1),risk=Math.abs(entry-sl);if(!(risk>0))return null;const rr=style==='SCALP'?2.2:2.5,tp=entry+dir*risk*rr;
  return {market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp:Number(tp.toPrecision(10)),targetRR:rr,score:Math.round(score),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend]},rationale:[`${intervalMap[style].join('/')} aligned`,dir>0?'EMA structure bullish':'EMA structure bearish',`RSI ${a.rsi.toFixed(1)}`,`spread ${spread.toFixed(2)} bps`,`extension ${a.extensionAtr.toFixed(2)} ATR`,orderType==='LIMIT'?'pullback entry avoids chasing':orderType==='STOP'?'breakout trigger waits for confirmation':'price is inside acceptable execution zone']};
}
async function analyzeCryptoCandidate(t,style){try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildCryptoSetup(t,style,stats)}catch{return null;}}

function v31Prefix(market,style){return `v31:signal:${market}:${style}:`;}
function activePointer(market,style,symbol){return `v31:active:${market}:${style}:${symbol}`;}
async function getV31Signals(env,market,style){
  if(!env?.SIGNALS_KV)return[];const prefix=v31Prefix(market,style),listing=await env.SIGNALS_KV.list({prefix,limit:1000}),out=[];for(let i=0;i<listing.keys.length;i+=50){const raws=await Promise.all(listing.keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));for(const raw of raws){if(!raw)continue;try{out.push(JSON.parse(raw))}catch{}}}out.sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0));return out;
}
async function writeV31Signal(env,s){const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});if(s.status==='PENDING'||s.status==='OPEN')await env.SIGNALS_KV.put(activePointer(s.market,s.style,s.symbol),s.id,{expirationTtl:SIGNAL_TTL});else await env.SIGNALS_KV.delete(activePointer(s.market,s.style,s.symbol));}
async function trackV31Signals(env,market,style,priceMap){
  const all=await getV31Signals(env,market,style),events=[],at=nowIso();for(const s of all){if(s.status!=='PENDING'&&s.status!=='OPEN')continue;const px=Number(priceMap.get(s.symbol));if(!(px>0))continue;const dir=s.side==='LONG'?1:-1,entry=Number(s.entry),sl=Number(s.sl),tp=Number(s.tp);s.lastPrice=px;s.lastCheckedAt=at;
    if(s.status==='PENDING'){
      const trigger=s.orderType==='LIMIT'?(dir>0?px<=entry:px>=entry):(dir>0?px>=entry:px<=entry);if(trigger){s.status='OPEN';s.triggeredAt=at;s.actualEntry=entry;events.push({type:'TRIGGERED',id:s.id,symbol:s.symbol});}
    }
    if(s.status==='OPEN'){
      const hitTp=dir>0?px>=tp:px<=tp,hitSl=dir>0?px<=sl:px>=sl;if(hitTp||hitSl){s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.closedAt=at;s.exitPrice=hitTp?tp:sl;s.resultR=hitTp?Number(s.targetRR||2.2):-1;s.resolution='V31_LIVE_PRICE_TRACKER';events.push({type:s.outcome,id:s.id,symbol:s.symbol});}
    }
    await writeV31Signal(env,s);
  }return events;
}
async function maybeCreateV31(env,market,style,setups,maxNew=1){
  if(!env?.SIGNALS_KV)return[];
  const current=await getV31Signals(env,market,style),active=current.filter(x=>x.status==='PENDING'||x.status==='OPEN');
  if(active.length>=6)return[];
  const lastKey=`v31:lastnew:${market}:${style}`,raw=await env.SIGNALS_KV.get(lastKey),last=raw?Date.parse(raw):0,minGap=style==='SCALP'?10*60*1000:30*60*1000;
  if(Number.isFinite(last)&&Date.now()-last<minGap)return[];
  const made=[];
  for(const setup of setups){
    if(made.length>=maxNew)break;
    if(active.some(x=>x.symbol===setup.symbol))continue;
    const ptr=await env.SIGNALS_KV.get(activePointer(market,style,setup.symbol));
    if(ptr)continue;
    if(market==='FOREX'){
      const legacyPtr=await env.SIGNALS_KV.get(`active:${setup.symbol}`);
      const otherStyle=style==='SCALP'?'SWING':'SCALP';
      const otherStylePtr=await env.SIGNALS_KV.get(activePointer('FOREX',otherStyle,setup.symbol));
      if(legacyPtr||otherStylePtr)continue;
    }
    const issuedAt=nowIso(),id=`V31-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT},market,style);
    await writeV31Signal(env,s);made.push(s);active.push(s);
    await env.SIGNALS_KV.put(lastKey,issuedAt,{expirationTtl:SIGNAL_TTL});
  }
  return made;
}
async function scanCrypto(env,style){
  const snap=await loadCryptoSnapshot(env),all=snap.rows,eligible=all.filter(x=>(x.turnover24h||0)>=2_000_000&&(x.spreadBps??999)<=(style==='SCALP'?15:35)),ranked=eligible.map(t=>({...t,discoveryScore:discoveryScore(t,style)})).sort((a,b)=>b.discoveryScore-a.discoveryScore).slice(0,style==='SCALP'?8:6),priceMap=new Map(all.map(x=>[x.symbol,x.lastPrice])),trackerEvents=await trackV31Signals(env,'CRYPTO',style,priceMap),analyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean).sort((a,b)=>b.score-a.score),created=await maybeCreateV31(env,'CRYPTO',style,analyses,1);
  return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,eligible:eligible.length,deepAnalyzed:ranked.length,qualified:analyses.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,5),note:'Signals require multi-timeframe alignment and anti-FOMO gates. No signal is emitted when the setup does not clear the threshold.'};
}

async function exnessQuoteMap(env){
  const snap=await readMt5Realtime(env),p=snap?.quotes||null;if(!p)return {map:new Map(),state:'OFFLINE',ageMs:null};
  const ageMs=Math.max(0,Date.now()-Date.parse(p.receivedAt||'')),state=ageMs<=1800?'LIVE':ageMs<=4000?'DELAYED':'STALE',map=new Map((p.quotes||[]).map(q=>[canonical(q.symbol),Number(q.mid)]));return {map,state,ageMs};
}
async function tvForexSwing(){
  const body={symbols:{tickers:FOREX.map(s=>`OANDA:${s}`),query:{types:[]}},columns:['name','close','change','Recommend.All|60','Recommend.All|240','Recommend.All|1D','RSI|60','RSI|240','EMA20|60','EMA50|60','EMA20|240','EMA50|240','ATR|60','ATR|240']};
  const raw=await fetchJson('https://scanner.tradingview.com/forex/scan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)},9000);if(!Array.isArray(raw?.data))throw new Error('TV_FOREX_BAD_JSON');return raw.data.map(r=>{const d=r.d||[];return {symbol:canonical(d[0]||String(r.s||'').split(':').pop()),close:num(d[1]),change:num(d[2]),r60:num(d[3]),r240:num(d[4]),r1d:num(d[5]),rsi60:num(d[6]),rsi240:num(d[7]),ema20_60:num(d[8]),ema50_60:num(d[9]),ema20_240:num(d[10]),ema50_240:num(d[11]),atr60:num(d[12]),atr240:num(d[13])};});
}
function forexSwingSetup(r,px){
  if(!(px>0&&r.atr60>0&&r.atr240>0))return null;const dir=r.r60>=.28&&r.r240>=.22&&r.r1d>=-.05?1:r.r60<=-.28&&r.r240<=-.22&&r.r1d<=.05?-1:0;if(!dir)return null;const emaAligned=dir>0?r.ema20_60>r.ema50_60&&r.ema20_240>r.ema50_240:r.ema20_60<r.ema50_60&&r.ema20_240<r.ema50_240;if(!emaAligned)return null;const rsiOk=dir>0?r.rsi60>=50&&r.rsi60<=68&&r.rsi240>=48:r.rsi60<=50&&r.rsi60>=32&&r.rsi240<=52;if(!rsiOk)return null;const atr=Math.max(r.atr60,r.atr240*.45),dist=Math.abs(px-r.ema20_60)/atr;if(dist>1.45)return null;let score=74+Math.min(12,Math.abs(r.r60)*16)+Math.min(10,Math.abs(r.r240)*14)+(Math.abs(r.r1d)>.1?4:0)-Math.min(12,dist*8);if(score<86)return null;let orderType=dist>.42?'LIMIT':'MARKET',entry=orderType==='LIMIT'?r.ema20_60:px,risk=atr*1.55,sl=entry-dir*risk,tp=entry+dir*risk*2.5;return {market:'FOREX',style:'SWING',symbol:r.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry,sl,tp,targetRR:2.5,score:Math.round(score),sourcePrice:px,lastPrice:px,source:'EXNESS_MT5+TRADINGVIEW_FOREX',executionPriceAuthority:'EXNESS_MT5',technicalAtIssue:{recommend1h:r.r60,recommend4h:r.r240,recommend1d:r.r1d,rsi1h:r.rsi60,rsi4h:r.rsi240,atr1h:r.atr60,atr4h:r.atr240,extensionAtr:Number(dist.toFixed(2))},rationale:['1H/4H directional alignment','1D is not materially opposing','EMA20/EMA50 structure aligned','RSI directional and non-extreme',orderType==='LIMIT'?'pullback LIMIT avoids chasing':'Exness price is inside acceptable swing execution zone']};}
async function scanForexSwing(env){
  const ex=await exnessQuoteMap(env);if(ex.state==='OFFLINE'||ex.state==='STALE')return {ok:true,version:V3_VERSION,market:'FOREX',style:'SWING',status:'NO_FRESH_EXNESS',created:0,state:ex.state,ageMs:ex.ageMs,note:'No swing signal is emitted without fresh Exness execution-price data.'};
  const rows=await tvForexSwing(),priceMap=ex.map,trackerEvents=await trackV31Signals(env,'FOREX','SWING',priceMap),setups=rows.map(r=>forexSwingSetup(r,priceMap.get(r.symbol))).filter(Boolean).sort((a,b)=>b.score-a.score),created=await maybeCreateV31(env,'FOREX','SWING',setups,1);return {ok:true,version:V3_VERSION,market:'FOREX',style:'SWING',status:'OK',state:ex.state,scanned:rows.length,qualified:setups.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:setups.slice(0,5)};
}
function normalizeDisplaySignal(input,market,style){
  const s={...(input||{})};
  s.market=String(market||s.market||'FOREX').toUpperCase();
  s.style=String(style||s.style||'SCALP').toUpperCase();
  s.signalId=String(s.signalId||s.id||'');
  const side=String(s.side||'').toUpperCase(),dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  const entry=num(s.actualEntry??s.entry),sl=num(s.sl);
  let finalTp=num(s.tp3??s.tp2??s.tp1??s.tp),rr=num(s.targetRR??s.rr);
  const risk=isFinitePositive(entry)&&isFinitePositive(sl)?Math.abs(entry-sl):null;
  if(risk&&risk>0&&dir){
    if(!(rr>0)&&isFinitePositive(finalTp))rr=Math.abs(finalTp-entry)/risk;
    if(!(rr>0))rr=2.0;
    if(!isFinitePositive(finalTp))finalTp=entry+dir*risk*rr;
    const tp1=num(s.tp1),tp2=num(s.tp2),tp3=num(s.tp3);
    s.tp1=isFinitePositive(tp1)?tp1:entry+dir*risk*Math.min(1.0,rr);
    s.tp2=isFinitePositive(tp2)?tp2:entry+dir*risk*Math.min(1.5,rr);
    s.tp3=isFinitePositive(tp3)?tp3:finalTp;
    s.tp=s.tp3;
    s.targetRR=Number(rr.toFixed(4));
  }
  const st=String(s.status||'').toUpperCase(),out=String(s.outcome||'').toUpperCase();
  s.lifecycle=st==='PENDING'?'PENDING_ENTRY':st==='OPEN'?'ACTIVE':st==='CLOSED'&&out==='TP'?'TP3_HIT':st==='CLOSED'&&out==='SL'?'STOP_LOSS_HIT':st==='CLOSED'&&out==='CANCELLED'?'CANCELLED':st==='CLOSED'?'CLOSED':st||'WATCHING';
  const score=Number(s.score||0);
  s.qualityGrade=score>=95?'A+':score>=90?'A':score>=85?'A-':score>=80?'B+':'B';
  s.scoreMeaning='SETUP_QUALITY_NOT_WIN_PROBABILITY';
  return s;
}

async function legacyScalpSignals(env){
  if(!env?.SIGNALS_KV)return[];
  const listing=await env.SIGNALS_KV.list({prefix:'signal:',limit:1000}),out=[];
  for(let i=0;i<listing.keys.length;i+=50){
    const raws=await Promise.all(listing.keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));
    for(const raw of raws){
      if(!raw)continue;
      try{
        const s=JSON.parse(raw),explicitMarket=String(s.market||'').toUpperCase(),explicitStyle=String(s.style||'').toUpperCase(),group=String(s.group||'').toLowerCase(),id=String(s.id||'');
        if(explicitMarket&&explicitMarket!=='FOREX')continue;
        if(explicitStyle&&explicitStyle!=='SCALP')continue;
        if(group&&!['forex','metal','energy'].includes(group))continue;
        if(id.startsWith('V31-'))continue;
        out.push(normalizeDisplaySignal(s,'FOREX','SCALP'));
      }catch{}
    }
  }
  out.sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0));
  return out;
}

async function unifiedSignals(url,env){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX';
  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const status=String(url.searchParams.get('status')||'active').toLowerCase();
  const limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120)));
  let rows=market==='FOREX'&&style==='SCALP'?await legacyScalpSignals(env):await getV31Signals(env,market,style);
  rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  let dataHealth=null;
  if(market==='FOREX'){
    const ex=await exnessQuoteMap(env);
    dataHealth={provider:'EXNESS_MT5',state:ex.state,quoteAgeMs:ex.ageMs};
  }
  return json({ok:true,version:V3_VERSION,market,style,partitionKey:`${market}:${style}`,status,count:rows.length,dataHealth,signals:rows});
}

async function unifiedPerformance(url,env){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=market==='FOREX'&&style==='SCALP'?await legacyScalpSignals(env):await getV31Signals(env,market,style),active=rows.filter(s=>s.status==='PENDING'||s.status==='OPEN'),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
  return json({ok:true,version:V3_VERSION,market,style,performance:{total:rows.length,active:active.length,pending:active.filter(s=>s.status==='PENDING').length,open:active.filter(s=>s.status==='OPEN').length,resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,winRateLabel:resolved.length?`${wr.toFixed(1)}% (${tp}/${resolved.length})`:'CHƯA CÓ MẪU'}});
}
async function scanRoute(url,env,ctx){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  if(market==='CRYPTO')return json(await scanCrypto(env,style));
  if(style==='SWING')return json(await scanForexSwing(env));
  try{const req=new Request(new URL('/run-now?group=forex',url).toString(),{method:'GET'}),r=await legacy.fetch(req,env,ctx),body=await r.json();return json({ok:r.ok,version:V3_VERSION,market:'FOREX',style:'SCALP',legacy:body},r.status);}catch(e){return json({ok:false,version:V3_VERSION,market:'FOREX',style:'SCALP',error:String(e?.message||e)},503);}
}
async function v3Status(env){
  const snap=await readMt5Realtime(env),mt5=snap?.heartbeat||null;
  return json({ok:true,version:V3_VERSION,service:'SignalHub multi-market gateway',checkpoint:CHECKPOINT,app:V31_RELEASE,forex:{executionPriceAuthority:'EXNESS_MT5',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME_WEBSOCKET':'KV_FALLBACK',scalp:'LEGACY_2.1_QUALITY_ENGINE',swing:'V31_SEPARATE_1H_4H_1D_ENGINE'},crypto:{priceAuthority:'BYBIT_PREFERRED_WITH_LABELED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'V31_MULTI_TF_ENGINE',swing:'V31_MULTI_TF_ENGINE',antiFomo:true},engines:{forexScalp:'ACTIVE',forexSwing:'ACTIVE_REQUIRES_FRESH_EXNESS',cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},mt5Heartbeat:mt5?{bridgeVersion:mt5.bridgeVersion,terminalConnected:mt5.terminalConnected,tradeAllowed:mt5.tradeAllowed,resolvedSymbols:mt5.resolvedSymbols,receivedAt:mt5.receivedAt}:null,winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'});
}
async function handleV3(req,env,ctx){
  const url=new URL(req.url);if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'content-type, authorization, x-signalhub-bridge','access-control-allow-methods':'GET,POST,OPTIONS'}});
  try{
    if(url.pathname==='/v3/status'&&req.method==='GET')return v3Status(env);
    if(url.pathname==='/v3/app-version'&&req.method==='GET')return json({ok:true,version:V3_VERSION,checkpoint:CHECKPOINT,app:V31_RELEASE});
    if(url.pathname==='/v3/mt5/prices'&&req.method==='POST')return mt5Prices(req,env);
    if(url.pathname==='/v3/mt5/heartbeat'&&req.method==='POST')return mt5Heartbeat(req,env);
    if(url.pathname==='/v3/mt5/events'&&req.method==='POST')return mt5Event(req,env);
    if(url.pathname==='/v3/forex/live'&&req.method==='GET')return mt5Live(env);
    if(url.pathname==='/v3/forex/stream'&&req.method==='GET'&&String(req.headers.get('Upgrade')||'').toLowerCase()==='websocket')return mt5Stream(req,env);
    if(url.pathname==='/v3/crypto/tickers'&&req.method==='GET')return cryptoTickers(url,env);
    if(url.pathname==='/v3/crypto/discovery'&&req.method==='GET')return cryptoDiscovery(url,env);
    if(url.pathname==='/v3/scan'&&req.method==='GET')return scanRoute(url,env,ctx);
    if(url.pathname==='/v3/signals'&&req.method==='GET')return unifiedSignals(url,env);
    if(url.pathname==='/v3/performance'&&req.method==='GET')return unifiedPerformance(url,env);
    return null;
  }catch(e){const msg=String(e?.message||e),code=msg==='INVALID_JSON'?400:msg==='PAYLOAD_TOO_LARGE'?413:503;return json({ok:false,version:V3_VERSION,checkpoint:CHECKPOINT,error:msg},code);}
}

export default {
  async fetch(req,env,ctx){const v3=await handleV3(req,env,ctx);if(v3)return v3;return legacy.fetch(req,env,ctx);},
  async scheduled(event,env,ctx){
    if(typeof legacy.scheduled==='function')ctx.waitUntil(Promise.resolve(legacy.scheduled(event,env,ctx)).catch(()=>{}));
    ctx.waitUntil((async()=>{await scanForexSwing(env).catch(()=>{});await sleep(150);await scanCrypto(env,'SCALP').catch(()=>{});await sleep(150);await scanCrypto(env,'SWING').catch(()=>{});})());
  },
};
