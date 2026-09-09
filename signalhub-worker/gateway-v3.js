import legacy from './gateway.js';

const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.8.0';
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
  versionCode: 14,
  versionName: '3.8.0',
  title: 'SignalHub 3.8.0',
  releasedAt: '2026-09-09T00:00:00Z',
  mandatory: false,
  minSupportedVersionCode: 6,
  artifactName: 'SignalHub-Android-v3.8.0',
  notes: [
    'V3.8 separates SCALP microstructure execution from SWING higher-timeframe execution and tracks pending triggers continuously.',
    'LIMIT/STOP activation is event-driven from live prices; Forex uses MT5 Ask for BUY triggers and Bid for SELL triggers.',
    'V3.7 Structure-Liquidity Engine retained: entries, stops and targets are derived from live structure, liquidity/rejection and volatility context.',
    'Stops sit beyond the bot-selected invalidation structure with ATR buffer; targets prefer structure/liquidity objectives before expansion.',
    'V3.6 Market Judgment retained: no score gate, no minimum score, no RR admission threshold and no signal cooldown.',
    'Bot classifies regime and actively chooses MARKET / LIMIT / STOP / NO TRADE from current market structure.',
    'Modern LIVE / LIMIT / STOP UI with yellow pending-entry progress gauge.',
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
    'No setup score is generated or displayed; historical win rate remains resolved TP/SL only.'
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


const MARKET_JUDGMENT_POLICY = Object.freeze({
  name:'BOT_MARKET_JUDGMENT',
  scoreGate:false,
  timeGate:false,
  rrGate:false,
  orderRouting:'DYNAMIC_MARKET_LIMIT_STOP',
  historicalWinRateMode:'RESOLVED_TP_SL_ONLY',
  entryModel:'STRUCTURE_LIQUIDITY_CONTEXT',
  stopModel:'INVALIDATION_STRUCTURE_PLUS_VOLATILITY_BUFFER',
  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION',
  styleSeparation:'SCALP_MICROSTRUCTURE_VS_SWING_HTF_STRUCTURE',
  pendingActivation:'PRICE_TOUCH_EVENT_DRIVEN_NO_COOLDOWN'
});

const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'sweep/reclaim, micro pullback, momentum continuation, breakout trigger',stopFocus:'nearest validated microstructure invalidation + volatility/spread buffer',targetFocus:'local liquidity then 15m/1h structure',holdModel:'short-horizon active management'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'H1 pullback/reclaim, HTF continuation, H1 breakout confirmation',stopFocus:'H1/H4 invalidation + wider volatility buffer',targetFocus:'H4/D1 liquidity and structural expansion',holdModel:'multi-session structure hold'})
});

function validSignalStructure(signal){
  if(!signal)return false;
  const entry=Number(signal.entry||0),sl=Number(signal.sl||0),tp=Number(signal.tp3||signal.tp||0);
  if(!(entry>0&&sl>0&&tp>0&&Math.abs(entry-sl)>0))return false;
  const side=String(signal.side||'').toUpperCase();
  const dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  if(!dir)return false;
  if(dir>0&&!(sl<entry&&tp>entry))return false;
  if(dir<0&&!(sl>entry&&tp<entry))return false;
  return ['MARKET','LIMIT','STOP'].includes(String(signal.orderType||'MARKET').toUpperCase());
}
function stampMarketJudgment(signal,market,style){
  signal.decisionMode='BOT_MARKET_JUDGMENT';
  signal.admissionMode='NO_SCORE_NO_TIME_GATE';
  signal.entryState=String(signal.orderType||'MARKET').toUpperCase()==='MARKET'?'LIVE':'PENDING_ENTRY';
  signal.market=String(market||signal.market||'FOREX').toUpperCase();
  signal.style=String(style||signal.style||'SCALP').toUpperCase();
  signal.styleProfile=STYLE_EXECUTION_POLICY[signal.style]||STYLE_EXECUTION_POLICY.SCALP;
  delete signal.score;delete signal.qualityGrade;delete signal.scoreMeaning;
  delete signal.admissionGate;
  return signal;
}


export class MT5LiveState {
  constructor(state, env) {
    this.state=state;this.env=env;this.clients=new Set();this.signalRegistry=null;
  }
  async registry(){if(this.signalRegistry===null)this.signalRegistry=(await this.state.storage.get('signalRegistry'))||{};return this.signalRegistry;}
  async persistRegistry(){await this.state.storage.put('signalRegistry',this.signalRegistry||{});}
  broadcast(obj){const msg=JSON.stringify(obj);for(const ws of [...this.clients]){try{ws.send(msg);}catch{this.clients.delete(ws);}}}
  async registerSignal(payload){
    const s=payload?.signal||payload,id=String(s?.id||s?.signalId||'');if(!id)return {ok:false,error:'NO_SIGNAL_ID'};
    const reg=await this.registry();
    if(s.status==='PENDING'||s.status==='OPEN')reg[id]={...s,kvKey:String(payload?.kvKey||`v31:signal:${s.market}:${s.style}:${id}`)};else delete reg[id];
    await this.persistRegistry();return {ok:true,id,status:s.status};
  }
  async unregisterSignal(payload){const id=String(payload?.id||payload?.signalId||'');if(!id)return {ok:false};const reg=await this.registry();delete reg[id];await this.persistRegistry();return {ok:true,id};}
  async evaluate(market,rows,receivedAt){
    const reg=await this.registry(),by=new Map();
    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);}
    const changed=[],at=receivedAt||nowIso();let dirty=false;
    for(const [id,s] of Object.entries(reg)){
      if(String(s.market||'').toUpperCase()!==String(market||'').toUpperCase())continue;
      if(s.status!=='PENDING'&&s.status!=='OPEN'){delete reg[id];dirty=true;continue;}
      const q=by.get(canonical(s.symbol));if(!q)continue;
      const dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
      let entryPx,exitPx;
      if(String(market).toUpperCase()==='FOREX'){
        const bid=Number(q.bid||q.mid||0),ask=Number(q.ask||q.mid||0);entryPx=dir>0?ask:bid;exitPx=dir>0?bid:ask;
      }else{const last=Number(q.lastPrice||q.last||q.mid||0);entryPx=last;exitPx=last;}
      if(!(entryPx>0&&exitPx>0))continue;
      const entry=Number(s.entry),sl=Number(s.sl),tp=Number(s.tp3||s.tp);let mutated=false,eventType='';
      if(s.status==='PENDING'){
        const type=String(s.orderType||'').toUpperCase();
        const trigger=type==='LIMIT'?(dir>0?entryPx<=entry:entryPx>=entry):type==='STOP'?(dir>0?entryPx>=entry:entryPx<=entry):false;
        if(trigger){s.status='OPEN';s.lifecycle='ACTIVE';s.entryState='LIVE';s.triggeredAt=at;s.triggerPrice=entryPx;s.actualEntry=s.actualEntry||entry;s.executionStatus='PRICE_TRIGGERED_AWAITING_BROKER_CONFIRM';eventType='TRIGGERED';mutated=true;}
      }
      if(s.status==='OPEN'){
        const hitTp=dir>0?exitPx>=tp:exitPx<=tp,hitSl=dir>0?exitPx<=sl:exitPx>=sl;
        if(hitTp||hitSl){s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=hitTp?tp:sl;s.resultR=hitTp?Number(s.targetRR||0):-1;s.resolution='REALTIME_EVENT_TRACKER';eventType=s.outcome;mutated=true;delete reg[id];dirty=true;}
      }
      if(mutated){
        s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`);const clean={...s};delete clean.kvKey;
        if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});if(clean.status==='CLOSED')await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);}
        if(clean.status!=='CLOSED')reg[id]={...clean,kvKey};dirty=true;changed.push({type:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,at});this.broadcast({type:'signal_event',event:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,receivedAt:at});
      }
    }
    if(dirty)await this.persistRegistry();return changed;
  }
  async fetch(req) {
    const url=new URL(req.url);
    if(req.headers.get('Upgrade')==='websocket'){
      const pair=new WebSocketPair(),client=pair[0],server=pair[1];server.accept();this.clients.add(server);const drop=()=>this.clients.delete(server);server.addEventListener('close',drop);server.addEventListener('error',drop);
      try{const quotes=await this.state.storage.get('quotes'),heartbeat=await this.state.storage.get('heartbeat');if(quotes)server.send(JSON.stringify({type:'quotes',...quotes,heartbeat:heartbeat||null}));}catch{}
      return new Response(null,{status:101,webSocket:client});
    }
    if(req.method==='POST'&&url.pathname==='/register-signal'){const p=await req.json();return new Response(JSON.stringify(await this.registerSignal(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/evaluate'){const p=await req.json(),events=await this.evaluate(p.market,p.rows||[],p.receivedAt);return new Response(JSON.stringify({ok:true,events}),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/prices'){
      const packet=await req.json();await this.state.storage.put('quotes',packet);this.broadcast({type:'quotes',...packet});const events=await this.evaluate('FOREX',packet.quotes||[],packet.receivedAt);return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt,events:events.length}),{headers:{'content-type':'application/json'}});
    }
    if(req.method==='POST'&&url.pathname==='/heartbeat'){const heartbeat=await req.json();await this.state.storage.put('heartbeat',heartbeat);this.broadcast({type:'heartbeat',heartbeat});return new Response(JSON.stringify({ok:true,receivedAt:heartbeat.receivedAt}),{headers:{'content-type':'application/json'}});}
    if(url.pathname==='/snapshot'){const [quotes,heartbeat]=await Promise.all([this.state.storage.get('quotes'),this.state.storage.get('heartbeat')]);return new Response(JSON.stringify({ok:!!quotes,quotes:quotes||null,heartbeat:heartbeat||null}),{headers:{'content-type':'application/json','cache-control':'no-store'}});}
    return new Response('not found',{status:404});
  }
}
function mt5LiveStub(env){
  if(!env?.MT5_LIVE)return null;
  return env.MT5_LIVE.get(env.MT5_LIVE.idFromName('primary'));
}

async function syncRealtimeSignal(env,s,kvKey){
  const stub=mt5LiveStub(env);if(!stub||!s)return;
  try{
    if(s.status==='PENDING'||s.status==='OPEN')await stub.fetch('https://mt5-live/register-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({signal:s,kvKey})});
    else await stub.fetch('https://mt5-live/unregister-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:s.id||s.signalId})});
  }catch{}
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
  const parts=String(id||'').split('-'),partition=(parts.length>3&&/^V3\d+$/.test(parts[0]))?`v31:signal:${parts[1]}:${parts[2]}:${id}`:null;
  for(const key of [`signal:${id}`,`v31:signal:${id}`,partition].filter(Boolean)){
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
  s.lastCheckedAt=receivedAt;await env.SIGNALS_KV.put(found.key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});await syncRealtimeSignal(env,s,found.key);
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
  if(snap.live!==false){const stub=mt5LiveStub(env);if(stub){try{await stub.fetch('https://mt5-live/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market:'CRYPTO',rows:snap.rows,receivedAt:snap.receivedAt})});}catch{}}}
  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:snap.live!==false,staleFallback:snap.staleFallback===true,ageMs:snap.ageMs??0,count:snap.rows.length,tickers:snap.rows.slice(0,limit),exchangeTime:snap.exchangeTime,receivedAt:snap.receivedAt,providerErrors:snap.errors||[],note:'Bybit is preferred. Live snapshots also drive pending-order activation; fallback exchange is explicitly labeled.'});
}
async function cryptoDiscovery(url,env){
  const style=String(url.searchParams.get('style')||'scalp').toUpperCase()==='SWING'?'SWING':'SCALP';
  const limit=Math.min(100,Math.max(5,Number(url.searchParams.get('limit')||40))),snap=await loadCryptoSnapshot(env),all=snap.rows;
  const candidates=all.filter(t=>Number(t.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,limit).map(t=>({...t,marketRead:'DISCOVERY_FOR_BOT_JUDGMENT'}));
  return json({ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,candidates,classification:'DISCOVERY_ONLY_NOT_TRADE_SIGNAL',decisionMode:'BOT_MARKET_JUDGMENT',note:'No composite score is used. Candidates are handed to the market-judgment engine for regime classification and entry routing.',receivedAt:snap.receivedAt});
}

function ema(values,period){if(!Array.isArray(values)||values.length<period)return null;const k=2/(period+1);let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;for(let i=period;i<values.length;i++)x=values[i]*k+x*(1-k);return x;}
function emaSeries(values,period){if(values.length<period)return[];const out=new Array(values.length).fill(null),k=2/(period+1);let x=values.slice(0,period).reduce((a,b)=>a+b,0)/period;out[period-1]=x;for(let i=period;i<values.length;i++){x=values[i]*k+x*(1-k);out[i]=x;}return out;}
function rsi(values,period=14){if(values.length<period+1)return null;let g=0,l=0;for(let i=values.length-period;i<values.length;i++){const d=values[i]-values[i-1];if(d>=0)g+=d;else l-=d;}if(l===0)return 100;const rs=(g/period)/(l/period);return 100-100/(1+rs);}
function atr(rows,period=14){if(rows.length<period+1)return null;const trs=[];for(let i=1;i<rows.length;i++){const p=rows[i-1].c,r=rows[i];trs.push(Math.max(r.h-r.l,Math.abs(r.h-p),Math.abs(r.l-p)));}const a=trs.slice(-period);return a.reduce((x,y)=>x+y,0)/a.length;}
function tfStats(rows){
  if(!rows||rows.length<55)return null;
  const closes=rows.map(x=>x.c),e20s=emaSeries(closes,20),e50=ema(closes,50),e20=e20s.at(-1),e20Prev=e20s[Math.max(19,e20s.length-6)],rr=rsi(closes,14),aa=atr(rows,14),last=rows.at(-1),prev=rows.at(-2);
  const prior=rows.slice(-34,-2),recent=rows.slice(-9,-1);
  const priorHigh=Math.max(...prior.map(x=>x.h)),priorLow=Math.min(...prior.map(x=>x.l)),recentHigh=Math.max(...recent.map(x=>x.h)),recentLow=Math.min(...recent.map(x=>x.l));
  if(![e20,e50,rr,aa,last?.c,priorHigh,priorLow,recentHigh,recentLow].every(Number.isFinite)||aa<=0)return null;
  const trend=last.c>e20&&e20>e50?1:last.c<e20&&e20<e50?-1:0,slope=e20Prev?((e20-e20Prev)/aa):0,momentum=rr>=52?1:rr<=48?-1:0;
  const body=Math.max(Math.abs(last.c-last.o),aa*.04),upperWick=Math.max(0,last.h-Math.max(last.o,last.c)),lowerWick=Math.max(0,Math.min(last.o,last.c)-last.l);
  const sweepHigh=last.h>priorHigh&&last.c<priorHigh&&upperWick>body*.65,sweepLow=last.l<priorLow&&last.c>priorLow&&lowerWick>body*.65;
  const bosUp=last.c>priorHigh,bosDown=last.c<priorLow,range=Math.max(priorHigh-priorLow,aa*.25),rangePosition=Math.max(0,Math.min(1,(last.c-priorLow)/range));
  const impulse=Math.abs(last.c-last.o)/aa,extensionAtr=Math.abs(last.c-e20)/aa;
  return {close:last.c,open:last.o,high:last.h,low:last.l,prevClose:prev?.c,ema20:e20,ema50:e50,rsi:rr,atr:aa,trend,slope,priorHigh,priorLow,recentHigh,recentLow,extensionAtr,momentum,sweepHigh,sweepLow,bosUp,bosDown,rangePosition,impulse,upperWickAtr:upperWick/aa,lowerWickAtr:lowerWick/aa};
}
const intervalMap={SCALP:['5m','15m','1h'],SWING:['1h','4h','1d']};
async function bybitCandles(symbol,interval,limit=120){const m={"5m":'5',"15m":'15',"1h":'60',"4h":'240',"1d":'D'}[interval],raw=await bybitFetch(`/v5/market/kline?category=linear&symbol=${encodeURIComponent(symbol)}&interval=${m}&limit=${limit}`),rows=(raw?.result?.list||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('BYBIT_CANDLES_SHORT');return rows;}
async function okxCandles(symbol,interval,limit=120){const inst=symbol.replace(/USDT$/,'-USDT-SWAP'),bar={"5m":'5m',"15m":'15m',"1h":'1H',"4h":'4H',"1d":'1D'}[interval],raw=await fetchJson(`https://www.okx.com/api/v5/market/candles?instId=${encodeURIComponent(inst)}&bar=${bar}&limit=${limit}`);if(String(raw?.code||'0')!=='0')throw new Error('OKX_CANDLES_'+raw?.code);const rows=(raw?.data||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('OKX_CANDLES_SHORT');return rows;}
async function binanceCandles(symbol,interval,limit=120){const raw=await fetchJson(`https://fapi.binance.com/fapi/v1/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`);if(!Array.isArray(raw))throw new Error('BINANCE_CANDLES_BAD');const rows=raw.map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c));if(rows.length<55)throw new Error('BINANCE_CANDLES_SHORT');return rows;}
async function providerCandles(symbol,interval,preferred){
  const order=preferred==='OKX'?[okxCandles,bybitCandles,binanceCandles]:preferred==='BINANCE'?[binanceCandles,bybitCandles,okxCandles]:[bybitCandles,okxCandles,binanceCandles];let last=null;for(const fn of order){try{return await fn(symbol,interval)}catch(e){last=e;}}throw last||new Error('NO_CANDLES');
}
function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const sameAB=a.trend!==0&&a.trend===b.trend,sameBC=b.trend!==0&&b.trend===c.trend;
  const nearHigh=(a.priorHigh-px)/a.atr,nearLow=(px-a.priorLow)/a.atr;
  const breakoutUp=(a.bosUp||(nearHigh>=-.12&&nearHigh<=.30))&&(a.momentum>=0||a.slope>0||a.impulse>.45);
  const breakoutDown=(a.bosDown||(nearLow>=-.12&&nearLow<=.30))&&(a.momentum<=0||a.slope<0||a.impulse>.45);
  let dir=0,regime='TRANSITION';
  if(a.sweepLow&&(b.trend>=0||c.trend>=0||b.momentum>=0)){dir=1;regime='LIQUIDITY_SWEEP_RECLAIM';}
  else if(a.sweepHigh&&(b.trend<=0||c.trend<=0||b.momentum<=0)){dir=-1;regime='LIQUIDITY_SWEEP_RECLAIM';}
  else if(sameAB&&(c.trend===0||c.trend===a.trend)){dir=a.trend;regime=a.extensionAtr>.48?'TREND_PULLBACK':'TREND_CONTINUATION';}
  else if(sameBC&&(a.trend===0||a.trend===b.trend)){dir=b.trend;regime='HTF_TREND_REJOIN';}
  else if(breakoutUp&&!breakoutDown){dir=1;regime='BREAKOUT_BUILDUP';}
  else if(breakoutDown&&!breakoutUp){dir=-1;regime='BREAKOUT_BUILDUP';}
  else if(a.trend!==0&&a.momentum===a.trend&&Math.sign(a.slope||0)===a.trend){dir=a.trend;regime='MOMENTUM_CONTINUATION';}
  else return null;

  const spread=Number(t.spreadBps??0),atr1=a.atr,spreadPx=Math.max(0,px*spread/10000),profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,entryBuffer=Math.max(atr1*(style==='SCALP'?.045:.085),spreadPx*(style==='SCALP'?1.8:2.2));
  let orderType='MARKET',entry=px,entryModel='MARKET_AT_ACCEPTABLE_STRUCTURE_LOCATION';
  if(regime==='BREAKOUT_BUILDUP'){
    orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='BREAKOUT_TRIGGER_BEYOND_LIQUIDITY';
  }else if(regime==='TREND_PULLBACK'||a.extensionAtr>.42||((dir>0&&px<a.ema20)||(dir<0&&px>a.ema20))){
    const raw=dir>0?Math.max(a.ema20,a.recentLow+.30*atr1):Math.min(a.ema20,a.recentHigh-.30*atr1);
    if((dir>0&&raw<px-entryBuffer*.35)||(dir<0&&raw>px+entryBuffer*.35)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_DYNAMIC_STRUCTURE';}
  }else if(regime==='MOMENTUM_CONTINUATION'&&a.impulse>.72){
    orderType='STOP';entry=px+dir*entryBuffer;entryModel='MOMENTUM_CONTINUATION_TRIGGER';
  }else if(regime==='LIQUIDITY_SWEEP_RECLAIM')entryModel='SWEEP_RECLAIM_MARKET_ENTRY';

  const stopBuffer=Math.max(atr1*(style==='SCALP'?.11:.22),spreadPx*(style==='SCALP'?2.6:3.2));
  let anchor;
  if(dir>0){
    if(regime==='LIQUIDITY_SWEEP_RECLAIM')anchor=Math.min(a.low,a.priorLow);
    else if(regime==='BREAKOUT_BUILDUP')anchor=Math.min(a.recentLow,a.priorHigh-.38*atr1);
    else anchor=style==='SCALP'?Math.min(a.recentLow,a.ema50-.08*atr1):Math.min(a.recentLow,b.recentLow,b.ema50-.10*b.atr);
  }else{
    if(regime==='LIQUIDITY_SWEEP_RECLAIM')anchor=Math.max(a.high,a.priorHigh);
    else if(regime==='BREAKOUT_BUILDUP')anchor=Math.max(a.recentHigh,a.priorLow+.38*atr1);
    else anchor=style==='SCALP'?Math.max(a.recentHigh,a.ema50+.08*atr1):Math.max(a.recentHigh,b.recentHigh,b.ema50+.10*b.atr);
  }
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer;
  let risk=Math.abs(entry-sl);if(!(risk>atr1*.18)) {risk=atr1*(style==='SCALP'?.82:1.12);sl=entry-dir*risk;}

  const target=(candidate,fallback,dirSign)=>dirSign>0?(Number(candidate)>fallback?Number(candidate):fallback):(Number(candidate)<fallback?Number(candidate):fallback);
  let tp1,tp2,tp3;
  if(dir>0){
    tp1=target(a.priorHigh,entry+risk*.95,1);
    tp2=target(b.priorHigh,Math.max(tp1+risk*.25,entry+risk*1.65),1);
    tp3=target(c.priorHigh,Math.max(tp2+risk*.30,entry+risk*(style==='SCALP'?2.10:2.85)),1);
  }else{
    tp1=target(a.priorLow,entry-risk*.95,-1);
    tp2=target(b.priorLow,Math.min(tp1-risk*.25,entry-risk*1.65),-1);
    tp3=target(c.priorLow,Math.min(tp2-risk*.30,entry-risk*(style==='SCALP'?2.10:2.85)),-1);
  }
  const rr=Math.abs(tp3-entry)/risk,spreadState=spread>(style==='SCALP'?12:30)?'WIDE':'NORMAL';
  const judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STRUCTURE SL/TP`;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,marketRegime:regime,judgment,entryModel,slModel:'INVALIDATION_SWING_LIQUIDITY_PLUS_ATR_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_TARGETS_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:spreadState,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[`${intervalMap[style].join('/')} structure/liquidity context`,dir>0?'bot reads bullish pressure':'bot reads bearish pressure',`regime ${regime}`,`entry ${entryModel}`,`SL beyond invalidation ${Number(anchor.toPrecision(8))} + volatility/spread buffer`,`TPs seek nearby and higher-timeframe liquidity before expansion`,`RSI ${a.rsi.toFixed(1)} • extension ${a.extensionAtr.toFixed(2)} ATR • spread ${spread.toFixed(2)} bps`]},'CRYPTO',style);
}
async function analyzeCryptoCandidate(t,style){try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildCryptoSetup(t,style,stats)}catch{return null;}}

function v31Prefix(market,style){return `v31:signal:${market}:${style}:`;}
function activePointer(market,style,symbol){return `v31:active:${market}:${style}:${symbol}`;}
async function getV31Signals(env,market,style){
  if(!env?.SIGNALS_KV)return[];const prefix=v31Prefix(market,style),listing=await env.SIGNALS_KV.list({prefix,limit:1000}),out=[];for(let i=0;i<listing.keys.length;i+=50){const raws=await Promise.all(listing.keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));for(const raw of raws){if(!raw)continue;try{out.push(JSON.parse(raw))}catch{}}}out.sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0));return out;
}
async function writeV31Signal(env,s){const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});if(s.status==='PENDING'||s.status==='OPEN')await env.SIGNALS_KV.put(activePointer(s.market,s.style,s.symbol),s.id,{expirationTtl:SIGNAL_TTL});else await env.SIGNALS_KV.delete(activePointer(s.market,s.style,s.symbol));await syncRealtimeSignal(env,s,key);}
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
async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];
  const current=await getV31Signals(env,market,style),active=current.filter(x=>x.status==='PENDING'||x.status==='OPEN'),made=[];
  for(const rawSetup of setups){
    const setup=stampMarketJudgment({...rawSetup},market,style);
    if(!validSignalStructure(setup))continue;
    if(active.some(x=>x.symbol===setup.symbol))continue;
    const ptr=await env.SIGNALS_KV.get(activePointer(market,style,setup.symbol));if(ptr)continue;
    const issuedAt=nowIso(),id=`V38-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT},market,style);
    await writeV31Signal(env,s);made.push(s);active.push(s);
  }
  return made;
}
async function scanCrypto(env,style){
  const snap=await loadCryptoSnapshot(env),all=snap.rows;
  const ranked=all.filter(x=>Number(x.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,style==='SCALP'?12:10);
  const priceMap=new Map(all.map(x=>[x.symbol,x.lastPrice])),trackerEvents=await trackV31Signals(env,'CRYPTO',style,priceMap);
  const analyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);
  return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,deepAnalyzed:ranked.length,actionable:analyses.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score gate and no signal cooldown. The bot classifies regime and routes each actionable idea as MARKET, LIMIT or STOP.'};
}

async function exnessQuoteMap(env){
  const snap=await readMt5Realtime(env),p=snap?.quotes||null;if(!p)return {map:new Map(),state:'OFFLINE',ageMs:null};
  const ageMs=Math.max(0,Date.now()-Date.parse(p.receivedAt||'')),state=ageMs<=1800?'LIVE':ageMs<=4000?'DELAYED':'STALE',map=new Map((p.quotes||[]).map(q=>[canonical(q.symbol),Number(q.mid)]));return {map,state,ageMs};
}
async function tvForexFrames(style){
  const f=style==='SCALP'?['5','15','60']:['60','240','1D'];
  const cols=['name','close','change'];for(const x of f)cols.push(`Recommend.All|${x}`);for(const x of f.slice(0,2))cols.push(`RSI|${x}`);for(const x of f.slice(0,2)){cols.push(`EMA20|${x}`);cols.push(`EMA50|${x}`);cols.push(`ATR|${x}`);cols.push(`open|${x}`);cols.push(`high|${x}`);cols.push(`low|${x}`);}
  const body={symbols:{tickers:FOREX.map(s=>`OANDA:${s}`),query:{types:[]}},columns:cols};
  const raw=await fetchJson('https://scanner.tradingview.com/forex/scan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)},9000);if(!Array.isArray(raw?.data))throw new Error('TV_FOREX_BAD_JSON');
  return raw.data.map(r=>{const d=r.d||[];let i=0;const symbol=canonical(d[i++]||String(r.s||'').split(':').pop()),close=num(d[i++]),change=num(d[i++]),recA=num(d[i++]),recB=num(d[i++]),recC=num(d[i++]),rsiA=num(d[i++]),rsiB=num(d[i++]);const a={ema20:num(d[i++]),ema50:num(d[i++]),atr:num(d[i++]),open:num(d[i++]),high:num(d[i++]),low:num(d[i++])},b={ema20:num(d[i++]),ema50:num(d[i++]),atr:num(d[i++]),open:num(d[i++]),high:num(d[i++]),low:num(d[i++])};return {symbol,close,change,recA,recB,recC,rsiA,rsiB,ema20A:a.ema20,ema50A:a.ema50,atrA:a.atr,openA:a.open,highA:a.high,lowA:a.low,ema20B:b.ema20,ema50B:b.ema50,atrB:b.atr,openB:b.open,highB:b.high,lowB:b.low,frames:f};});
}
function forexJudgmentSetup(r,px,style){
  if(!(px>0&&r.atrA>0&&r.atrB>0&&r.ema20A>0&&r.ema50A>0&&r.ema20B>0&&r.ema50B>0))return null;
  const emaA=r.ema20A>r.ema50A?1:r.ema20A<r.ema50A?-1:0,emaB=r.ema20B>r.ema50B?1:r.ema20B<r.ema50B?-1:0;
  const recA=r.recA>0?1:r.recA<0?-1:0,recB=r.recB>0?1:r.recB<0?-1:0,recC=r.recC>0?1:r.recC<0?-1:0;
  const atr=Math.max(r.atrA,r.atrB*(style==='SCALP'?.38:.45)),ext=(px-r.ema20A)/atr;
  const highA=r.highA>0?r.highA:px+.55*atr,lowA=r.lowA>0?r.lowA:px-.55*atr,openA=r.openA>0?r.openA:px;
  const highB=r.highB>0?r.highB:r.ema20B+r.atrB*.8,lowB=r.lowB>0?r.lowB:r.ema20B-r.atrB*.8;
  const body=Math.max(Math.abs(px-openA),atr*.05),lowerWick=Math.max(0,Math.min(px,openA)-lowA),upperWick=Math.max(0,highA-Math.max(px,openA));
  const bullReject=px>=openA&&lowerWick>Math.max(body*.9,atr*.16),bearReject=px<=openA&&upperWick>Math.max(body*.9,atr*.16);
  let dir=0,regime='TRANSITION';
  if(bullReject&&(emaB>=0||recB>=0)){dir=1;regime='LIQUIDITY_REJECTION';}
  else if(bearReject&&(emaB<=0||recB<=0)){dir=-1;regime='LIQUIDITY_REJECTION';}
  else if(emaA!==0&&emaA===emaB&&(recC===0||recC===emaA)){dir=emaA;regime=Math.abs(ext)>.48?'TREND_PULLBACK':'TREND_CONTINUATION';}
  else if(recA!==0&&recA===recB&&(recC===0||recC===recA)){dir=recA;regime='MOMENTUM_CONTINUATION';}
  else if(recA!==0&&((recA>0&&r.rsiA>=50)||(recA<0&&r.rsiA<=50))){dir=recA;regime='TRANSITION_MOMENTUM';}
  else return null;

  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,entryBuffer=atr*(style==='SCALP'?.045:.09),strongImpulse=Math.abs(Number(r.recA||0))>.45&&Math.abs(Number(r.recB||0))>.25;
  let orderType='MARKET',entry=px,entryModel='MARKET_AT_ACCEPTABLE_STRUCTURE_LOCATION';
  if(strongImpulse&&Math.abs(ext)<.38&&regime!=='LIQUIDITY_REJECTION'){orderType='STOP';entry=dir>0?highA+entryBuffer:lowA-entryBuffer;regime='BREAKOUT_CONFIRMATION';entryModel='BREAKOUT_TRIGGER_OUTSIDE_CURRENT_STRUCTURE';}
  else if(regime==='TREND_PULLBACK'||Math.abs(ext)>.42||((dir>0&&px<r.ema20A)||(dir<0&&px>r.ema20A))){const raw=dir>0?Math.max(r.ema20A,lowA+.30*atr):Math.min(r.ema20A,highA-.30*atr);if((dir>0&&raw<px-entryBuffer*.3)||(dir<0&&raw>px+entryBuffer*.3)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_EMA_STRUCTURE';}}
  else if(regime==='LIQUIDITY_REJECTION')entryModel='REJECTION_RECLAIM_MARKET_ENTRY';

  const stopBuffer=atr*(style==='SCALP'?.12:.24);let anchor;
  if(dir>0){anchor=regime==='LIQUIDITY_REJECTION'?lowA:regime==='BREAKOUT_CONFIRMATION'?Math.min(lowA,r.ema20A-.35*atr):Math.min(lowA,r.ema50A-.08*atr);if(style==='SWING'&&lowB<entry)anchor=Math.min(anchor,lowB,r.ema50B-.12*r.atrB);}
  else{anchor=regime==='LIQUIDITY_REJECTION'?highA:regime==='BREAKOUT_CONFIRMATION'?Math.max(highA,r.ema20A+.35*atr):Math.max(highA,r.ema50A+.08*atr);if(style==='SWING'&&highB>entry)anchor=Math.max(anchor,highB,r.ema50B+.12*r.atrB);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl);if(!(risk>atr*.18)){risk=atr*(style==='SCALP'?.88:1.18);sl=entry-dir*risk;}
  const pick=(candidate,fallback,sign)=>sign>0?(Number(candidate)>fallback?Number(candidate):fallback):(Number(candidate)<fallback?Number(candidate):fallback);
  let tp1,tp2,tp3;if(dir>0){tp1=pick(highA,entry+risk*.95,1);tp2=pick(highB,Math.max(tp1+risk*.25,entry+risk*1.65),1);tp3=Math.max(tp2+risk*.30,entry+risk*(style==='SCALP'?2.05:2.90));}else{tp1=pick(lowA,entry-risk*.95,-1);tp2=pick(lowB,Math.min(tp1-risk*.25,entry-risk*1.65),-1);tp3=Math.min(tp2-risk*.30,entry-risk*(style==='SCALP'?2.05:2.90));}
  const rr=Math.abs(tp3-entry)/risk,judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STRUCTURE SL/TP`;
  return stampMarketJudgment({market:'FOREX',style,symbol:r.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry,sl,tp1,tp2,tp3,tp:tp3,targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:'EXNESS_MT5+TRADINGVIEW_FOREX',executionPriceAuthority:'EXNESS_MT5',marketRegime:regime,judgment,entryModel,slModel:'INVALIDATION_STRUCTURE_PLUS_ATR_BUFFER',tpModel:'LOCAL_HTF_STRUCTURE_THEN_EXPANSION',invalidationLevel:anchor,styleExecutionModel:profile.name,executionFrames:profile.frames,technicalAtIssue:{frames:r.frames,recommend:[r.recA,r.recB,r.recC],rsi:[r.rsiA,r.rsiB],atr:[r.atrA,r.atrB],ema20:[r.ema20A,r.ema20B],ema50:[r.ema50A,r.ema50B],extensionAtr:Number(ext.toFixed(2)),localStructure:[lowA,highA],htfStructure:[lowB,highB],bullReject,bearReject},rationale:[`${r.frames.join('/')} context with local/HTF structure`,dir>0?'bot reads bullish pressure':'bot reads bearish pressure',`regime ${regime}`,`entry ${entryModel}`,`SL beyond invalidation ${Number(anchor.toPrecision(8))} + volatility buffer`,`TP1/TP2 use local and HTF structure when available; TP3 extends only after those objectives`,`RSI ${Number(r.rsiA).toFixed(1)} / ${Number(r.rsiB).toFixed(1)}`]},'FOREX',style);
}
async function scanForexJudgment(env,style){
  const ex=await exnessQuoteMap(env);if(ex.state==='OFFLINE'||ex.state==='STALE')return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'NO_CURRENT_EXNESS_QUOTE',created:0,state:ex.state,ageMs:ex.ageMs,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time gate is applied, but stale data is never treated as a current market price.'};
  const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await trackV31Signals(env,'FOREX',style,priceMap),setups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),created=await maybeCreateV31(env,'FOREX',style,setups);
  return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,actionable:setups.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY};
}
async function scanForexScalp(env){return scanForexJudgment(env,'SCALP');}
async function scanForexSwing(env){return scanForexJudgment(env,'SWING');}
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
  s.decisionMode=String(s.decisionMode||'BOT_MARKET_JUDGMENT');
  s.admissionMode=String(s.admissionMode||'NO_SCORE_NO_TIME_GATE');
  delete s.score;delete s.qualityGrade;delete s.scoreMeaning;
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
  let rows=await getV31Signals(env,market,style);rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  let dataHealth=null;if(market==='FOREX'){const ex=await exnessQuoteMap(env);dataHealth={provider:'EXNESS_MT5',state:ex.state,quoteAgeMs:ex.ageMs};}
  return json({ok:true,version:V3_VERSION,market,style,partitionKey:`${market}:${style}`,status,count:rows.length,dataHealth,decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
}

async function unifiedPerformance(url,env){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=await getV31Signals(env,market,style),active=rows.filter(s=>s.status==='PENDING'||s.status==='OPEN'),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
  return json({ok:true,version:V3_VERSION,market,style,performance:{total:rows.length,active:active.length,pending:active.filter(s=>s.status==='PENDING').length,open:active.filter(s=>s.status==='OPEN').length,resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,winRateLabel:resolved.length?`${wr.toFixed(1)}% (${tp}/${resolved.length})`:'CHƯA CÓ MẪU'}});
}
async function scanRoute(url,env,ctx){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  if(market==='CRYPTO')return json(await scanCrypto(env,style));
  return json(await scanForexJudgment(env,style));
}
async function v3Status(env){
  const snap=await readMt5Realtime(env),mt5=snap?.heartbeat||null;
  return json({ok:true,version:V3_VERSION,service:'SignalHub multi-market gateway',checkpoint:CHECKPOINT,app:V31_RELEASE,forex:{executionPriceAuthority:'EXNESS_MT5',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME_WEBSOCKET':'KV_FALLBACK',scalp:'V36_MARKET_JUDGMENT_5M_15M_1H',swing:'V36_MARKET_JUDGMENT_1H_4H_1D'},crypto:{priceAuthority:'BYBIT_PREFERRED_WITH_LABELED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'V36_MARKET_JUDGMENT_MULTI_TF',swing:'V36_MARKET_JUDGMENT_MULTI_TF',antiFomo:false},engines:{forexScalp:'ACTIVE',forexSwing:'ACTIVE_REQUIRES_FRESH_EXNESS',cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},mt5Heartbeat:mt5?{bridgeVersion:mt5.bridgeVersion,terminalConnected:mt5.terminalConnected,tradeAllowed:mt5.tradeAllowed,resolvedSymbols:mt5.resolvedSymbols,receivedAt:mt5.receivedAt}:null,decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'});
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
    ctx.waitUntil((async()=>{await scanForexScalp(env).catch(()=>{});await sleep(100);await scanForexSwing(env).catch(()=>{});await sleep(100);await scanCrypto(env,'SCALP').catch(()=>{});await sleep(100);await scanCrypto(env,'SWING').catch(()=>{});})());
  },
};
