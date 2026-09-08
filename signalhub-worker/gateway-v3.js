import legacy from './gateway.js';

const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.0.0';
const MT5_QUOTE_TTL = 120;
const MT5_HEARTBEAT_TTL = 180;
const MT5_EVENT_TTL = 60 * 60 * 24 * 90;
const CRYPTO_CACHE_MS = 1200;
const UNIVERSE_CACHE_MS = 5 * 60 * 1000;
const BYBIT_BASES = ['https://api.bybit.com', 'https://api.bytick.com'];

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

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const nowIso = () => new Date().toISOString();
const canonical = s => String(s || '').trim().toUpperCase();
const isFinitePositive = v => Number.isFinite(Number(v)) && Number(v) > 0;

async function readJson(req, maxBytes = 1_000_000) {
  const raw = await req.text();
  if (raw.length > maxBytes) throw new Error('PAYLOAD_TOO_LARGE');
  try { return JSON.parse(raw || '{}'); }
  catch { throw new Error('INVALID_JSON'); }
}

function bridgeAllowed(req, env) {
  const expected = String(env?.MT5_BRIDGE_TOKEN || '').trim();
  if (!expected) {
    return String(req.headers.get('x-signalhub-bridge') || '').startsWith('SIGNALHUB-EXNESS-BRIDGE-');
  }
  const auth = String(req.headers.get('authorization') || '');
  return auth === `Bearer ${expected}`;
}

function sanitizeQuote(q) {
  const symbol = canonical(q?.symbol);
  const brokerSymbol = String(q?.brokerSymbol || '').trim();
  const bid = num(q?.bid), ask = num(q?.ask), last = num(q?.last);
  const spreadPoints = num(q?.spreadPoints);
  const tickTimeMsc = Number(q?.tickTimeMsc || 0);
  if (!symbol || !isFinitePositive(bid) || !isFinitePositive(ask) || ask < bid) return null;
  return {
    symbol, brokerSymbol,
    bid, ask,
    mid: (bid + ask) / 2,
    last: isFinitePositive(last) ? last : null,
    spreadPoints: Number.isFinite(spreadPoints) ? spreadPoints : null,
    tickTimeMsc: Number.isFinite(tickTimeMsc) && tickTimeMsc > 0 ? tickTimeMsc : null,
  };
}

async function mt5Prices(req, env) {
  if (!bridgeAllowed(req, env)) return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'}, 401);
  if (!env?.SIGNALS_KV) return json({ok:false,error:'NO_KV'}, 503);
  const body = await readJson(req, 2_000_000);
  const input = Array.isArray(body?.quotes) ? body.quotes : [];
  const quotes = input.slice(0, 100).map(sanitizeQuote).filter(Boolean);
  const receivedAt = nowIso();
  const packet = {
    ok:true,
    version:V3_VERSION,
    source:'EXNESS_MT5',
    bridgeVersion:String(body?.bridgeVersion || ''),
    server:String(body?.server || ''),
    receivedAt,
    quotes,
    count:quotes.length,
  };
  await env.SIGNALS_KV.put('v3:mt5:quotes:latest', JSON.stringify(packet), {expirationTtl: MT5_QUOTE_TTL});
  await Promise.all(quotes.map(q => env.SIGNALS_KV.put(`v3:mt5:quote:${q.symbol}`, JSON.stringify({...q,receivedAt,source:'EXNESS_MT5'}), {expirationTtl: MT5_QUOTE_TTL})));
  return json({ok:true,accepted:quotes.length,receivedAt});
}

async function mt5Heartbeat(req, env) {
  if (!bridgeAllowed(req, env)) return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'}, 401);
  if (!env?.SIGNALS_KV) return json({ok:false,error:'NO_KV'}, 503);
  const body = await readJson(req);
  const receivedAt = nowIso();
  const heartbeat = {
    bridgeVersion:String(body?.bridgeVersion || ''),
    status:String(body?.status || ''),
    server:String(body?.server || ''),
    company:String(body?.company || ''),
    terminalConnected:body?.terminalConnected === true,
    tradeAllowed:body?.tradeAllowed === true,
    resolvedSymbols:Number(body?.resolvedSymbols || 0),
    positions:Number(body?.positions || 0),
    orders:Number(body?.orders || 0),
    queuedEvents:Number(body?.queuedEvents || 0),
    receivedAt,
  };
  await env.SIGNALS_KV.put('v3:mt5:heartbeat:latest', JSON.stringify(heartbeat), {expirationTtl: MT5_HEARTBEAT_TTL});
  return json({ok:true,receivedAt});
}

async function patchSignalFromBrokerEvent(env, evt, receivedAt) {
  const id = String(evt?.signalId || '').trim();
  if (!id || !env?.SIGNALS_KV) return {patched:false,reason:'NO_SIGNAL_ID'};
  const key = `signal:${id}`;
  const raw = await env.SIGNALS_KV.get(key);
  if (!raw) return {patched:false,reason:'SIGNAL_NOT_FOUND'};
  let s;
  try { s = JSON.parse(raw); } catch { return {patched:false,reason:'SIGNAL_BAD_JSON'}; }
  const event = String(evt?.event || '').toUpperCase();
  const price = num(evt?.price);
  if (event === 'BROKER_FILL_CONFIRMED') {
    s.status = 'OPEN';
    s.triggeredAt = s.triggeredAt || receivedAt;
    s.brokerFilledAt = receivedAt;
    if (isFinitePositive(price)) {
      s.actualEntry = price;
      s.entry = price;
      s.lastPrice = price;
    }
    s.brokerConfirmed = true;
    s.executionSource = 'EXNESS_MT5_DEAL';
    s.brokerSymbol = String(evt?.brokerSymbol || s.brokerSymbol || '');
    s.brokerDealTicket = String(evt?.dealTicket || '');
    s.brokerOrderTicket = String(evt?.orderTicket || '');
  } else if (event === 'BROKER_CLOSE_CONFIRMED') {
    s.brokerClosedAt = receivedAt;
    s.brokerClosePrice = isFinitePositive(price) ? price : null;
    s.brokerCloseConfirmed = true;
    s.brokerCloseReason = String(evt?.dealReason || 'BROKER_CLOSE');
  } else {
    return {patched:false,reason:'EVENT_NOT_PATCHABLE'};
  }
  s.lastCheckedAt = receivedAt;
  await env.SIGNALS_KV.put(key, JSON.stringify(s), {expirationTtl: MT5_EVENT_TTL});
  return {patched:true,status:s.status};
}

async function mt5Event(req, env) {
  if (!bridgeAllowed(req, env)) return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'}, 401);
  if (!env?.SIGNALS_KV) return json({ok:false,error:'NO_KV'}, 503);
  const evt = await readJson(req);
  const receivedAt = nowIso();
  const deal = String(evt?.dealTicket || '').trim();
  const eventId = deal || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const record = {...evt,receivedAt,eventId,source:'EXNESS_MT5'};
  await env.SIGNALS_KV.put(`v3:mt5:event:${eventId}`, JSON.stringify(record), {expirationTtl: MT5_EVENT_TTL});
  await env.SIGNALS_KV.put('v3:mt5:event:latest', JSON.stringify(record), {expirationTtl: MT5_EVENT_TTL});
  const patch = await patchSignalFromBrokerEvent(env, evt, receivedAt);
  return json({ok:true,eventId,receivedAt,signalPatch:patch});
}

async function mt5Live(env) {
  const [quotesRaw, hbRaw, eventRaw] = await Promise.all([
    env?.SIGNALS_KV?.get('v3:mt5:quotes:latest'),
    env?.SIGNALS_KV?.get('v3:mt5:heartbeat:latest'),
    env?.SIGNALS_KV?.get('v3:mt5:event:latest'),
  ]);
  let quotes=null, heartbeat=null, lastEvent=null;
  try { if (quotesRaw) quotes=JSON.parse(quotesRaw); } catch {}
  try { if (hbRaw) heartbeat=JSON.parse(hbRaw); } catch {}
  try { if (eventRaw) lastEvent=JSON.parse(eventRaw); } catch {}
  const qAt = Date.parse(quotes?.receivedAt || '');
  const hAt = Date.parse(heartbeat?.receivedAt || '');
  const quoteAgeMs = Number.isFinite(qAt) ? Math.max(0, Date.now()-qAt) : null;
  const heartbeatAgeMs = Number.isFinite(hAt) ? Math.max(0, Date.now()-hAt) : null;
  const state = quoteAgeMs === null ? 'OFFLINE' : quoteAgeMs <= 2500 ? 'LIVE' : quoteAgeMs <= 10000 ? 'DELAYED' : 'STALE';
  return json({
    ok:!!quotes,
    version:V3_VERSION,
    market:'FOREX_EXNESS',
    state,
    quoteAgeMs,
    heartbeatAgeMs,
    quotes:quotes?.quotes || [],
    count:quotes?.count || 0,
    heartbeat:heartbeat ? {
      bridgeVersion:heartbeat.bridgeVersion,
      status:heartbeat.status,
      terminalConnected:heartbeat.terminalConnected,
      tradeAllowed:heartbeat.tradeAllowed,
      resolvedSymbols:heartbeat.resolvedSymbols,
      positions:heartbeat.positions,
      orders:heartbeat.orders,
      queuedEvents:heartbeat.queuedEvents,
      receivedAt:heartbeat.receivedAt,
    } : null,
    lastEvent:lastEvent ? {
      event:lastEvent.event,
      signalId:lastEvent.signalId || '',
      brokerSymbol:lastEvent.brokerSymbol || '',
      price:num(lastEvent.price),
      receivedAt:lastEvent.receivedAt,
    } : null,
  }, quotes ? 200 : 503);
}

async function bybitFetch(path) {
  let lastErr = null;
  for (const base of BYBIT_BASES) {
    try {
      const res = await fetch(base + path, {
        headers:{'accept':'application/json','user-agent':'SignalHub-V3/3.0'},
        cf:{cacheTtl:0,cacheEverything:false},
      });
      if (!res.ok) throw new Error(`HTTP_${res.status}`);
      const data = await res.json();
      if (Number(data?.retCode || 0) !== 0) throw new Error(`BYBIT_${data?.retCode}:${data?.retMsg || ''}`);
      return data;
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error('BYBIT_UNAVAILABLE');
}

async function cachedResponse(cacheKey, ttlMs, producer) {
  const cache = caches.default;
  const req = new Request(`https://signalhub-cache.local/${cacheKey}`);
  const hit = await cache.match(req);
  if (hit) return await hit.json();
  const out = await producer();
  const res = new Response(JSON.stringify(out), {headers:{'content-type':'application/json','cache-control':`public,max-age=${Math.max(1,Math.floor(ttlMs/1000))}`}});
  await cache.put(req, res);
  return out;
}

function cleanTicker(x) {
  const bid=num(x?.bid1Price), ask=num(x?.ask1Price), last=num(x?.lastPrice), turn=num(x?.turnover24h), oi=num(x?.openInterestValue), fr=num(x?.fundingRate), ch=num(x?.price24hPcnt);
  const mid = isFinitePositive(bid) && isFinitePositive(ask) ? (bid+ask)/2 : last;
  const spreadBps = isFinitePositive(mid) && isFinitePositive(ask) && Number.isFinite(bid) ? (ask-bid)/mid*10000 : null;
  return {
    symbol:canonical(x?.symbol), lastPrice:last, markPrice:num(x?.markPrice), indexPrice:num(x?.indexPrice),
    bid, ask, spreadBps, turnover24h:turn, volume24h:num(x?.volume24h), openInterestValue:oi,
    fundingRate:fr, change24hPct:Number.isFinite(ch) ? ch*100 : null, nextFundingTime:Number(x?.nextFundingTime || 0) || null,
  };
}

async function cryptoTickers(url) {
  const data = await cachedResponse('bybit-linear-tickers-v3', CRYPTO_CACHE_MS, async () => {
    const raw = await bybitFetch('/v5/market/tickers?category=linear');
    const rows = (raw?.result?.list || []).map(cleanTicker).filter(x => x.symbol.endsWith('USDT') && isFinitePositive(x.lastPrice));
    rows.sort((a,b)=>(b.turnover24h||0)-(a.turnover24h||0));
    return {rows,exchangeTime:Number(raw?.time || 0),receivedAt:nowIso()};
  });
  const limit = Math.min(1000, Math.max(1, Number(url.searchParams.get('limit') || 1000)));
  return json({
    ok:true, version:V3_VERSION, market:'BYBIT_LINEAR_USDT', source:'BYBIT_V5_REST_TICKERS',
    streamingReference:'wss://stream.bybit.com/v5/public/linear',
    count:data.rows.length, tickers:data.rows.slice(0,limit), exchangeTime:data.exchangeTime, receivedAt:data.receivedAt,
    note:'REST broad-scan snapshot. Deep live tracking may use the existing Bybit VPS WebSocket bridge.',
  });
}

async function cryptoUniverse(url) {
  const data = await cachedResponse('bybit-linear-universe-v3', UNIVERSE_CACHE_MS, async () => {
    let cursor=''; const rows=[]; let pages=0;
    do {
      const qs = new URLSearchParams({category:'linear',limit:'1000'});
      if (cursor) qs.set('cursor',cursor);
      const raw = await bybitFetch('/v5/market/instruments-info?' + qs.toString());
      pages++;
      for (const x of raw?.result?.list || []) {
        if (String(x?.quoteCoin || '').toUpperCase() !== 'USDT') continue;
        if (String(x?.contractType || '') !== 'LinearPerpetual') continue;
        rows.push({
          symbol:canonical(x?.symbol), status:String(x?.status || ''), baseCoin:canonical(x?.baseCoin),
          quoteCoin:canonical(x?.quoteCoin), launchTime:Number(x?.launchTime || 0) || null,
          maxLeverage:num(x?.leverageFilter?.maxLeverage), tickSize:num(x?.priceFilter?.tickSize),
          qtyStep:num(x?.lotSizeFilter?.qtyStep), minOrderQty:num(x?.lotSizeFilter?.minOrderQty),
        });
      }
      cursor=String(raw?.result?.nextPageCursor || '');
    } while (cursor && pages < 5);
    rows.sort((a,b)=>a.symbol.localeCompare(b.symbol));
    return {rows,pages,receivedAt:nowIso()};
  });
  const status = canonical(url.searchParams.get('status') || 'TRADING');
  const rows = data.rows.filter(x => status === 'ALL' || canonical(x.status) === status);
  return json({ok:true,version:V3_VERSION,market:'BYBIT_LINEAR_USDT',count:rows.length,pages:data.pages,instruments:rows,receivedAt:data.receivedAt});
}

function discoveryScore(t, style) {
  const turn=Math.max(0,t.turnover24h||0), spread=Math.max(0,t.spreadBps??999), change=Math.abs(t.change24hPct||0), oi=Math.max(0,t.openInterestValue||0), fund=Math.abs((t.fundingRate||0)*100);
  const liq=Math.min(1,Math.log10(Math.max(1,turn))/9);
  const oiScore=Math.min(1,Math.log10(Math.max(1,oi))/9);
  const spreadScore=Math.max(0,1-spread/(style==='scalp'?12:30));
  const moveScore=Math.min(1,change/(style==='scalp'?8:18));
  const fundingPenalty=Math.min(.35,fund/2);
  return 100*Math.max(0,Math.min(1,.38*liq+.22*spreadScore+.18*moveScore+.16*oiScore+.06*(1-fundingPenalty)));
}

async function cryptoDiscovery(url) {
  const style = String(url.searchParams.get('style') || 'scalp').toLowerCase() === 'swing' ? 'swing' : 'scalp';
  const limit = Math.min(100,Math.max(5,Number(url.searchParams.get('limit')||40)));
  const raw = await bybitFetch('/v5/market/tickers?category=linear');
  const all=(raw?.result?.list || []).map(cleanTicker).filter(x=>x.symbol.endsWith('USDT')&&isFinitePositive(x.lastPrice));
  const eligible=all.filter(x=>(x.turnover24h||0)>=1_000_000 && (x.spreadBps??999) <= (style==='scalp'?20:50));
  const candidates=eligible.map(t=>({...t,discoveryScore:Number(discoveryScore(t,style).toFixed(1))})).sort((a,b)=>b.discoveryScore-a.discoveryScore).slice(0,limit);
  return json({
    ok:true,version:V3_VERSION,market:'CRYPTO',style:style.toUpperCase(),scanned:all.length,eligible:eligible.length,candidates,
    classification:'DISCOVERY_ONLY_NOT_TRADE_SIGNAL',
    note:'Ranking only selects symbols for deeper Scalp/Swing analysis. It is intentionally not a BUY/SELL generator.',
    exchangeTime:Number(raw?.time||0),receivedAt:nowIso(),
  });
}

async function v3Status(env) {
  let mt5 = null;
  try { const raw=await env?.SIGNALS_KV?.get('v3:mt5:heartbeat:latest'); if(raw) mt5=JSON.parse(raw); } catch {}
  return json({
    ok:true,version:V3_VERSION,service:'SignalHub multi-market gateway',
    forex:{executionPriceAuthority:'EXNESS_MT5',legacySignalEngine:'SIGNALHUB-FOREX-2.1.0',telemetryRoutes:true},
    crypto:{priceAuthority:'BYBIT_V5',broadUniverse:'ALL_USDT_LINEAR_PERPETUAL',deepLiveBridge:'EXISTING_BYBIT_VPS_WS'},
    engines:{forexScalp:'DESIGN_LOCKED_RESEARCH_REQUIRED',forexSwing:'DESIGN_LOCKED_RESEARCH_REQUIRED',cryptoScalp:'DISCOVERY_READY_DEEP_SIGNAL_ENGINE_PENDING',cryptoSwing:'DISCOVERY_READY_DEEP_SIGNAL_ENGINE_PENDING'},
    mt5Heartbeat:mt5 ? {bridgeVersion:mt5.bridgeVersion,terminalConnected:mt5.terminalConnected,tradeAllowed:mt5.tradeAllowed,resolvedSymbols:mt5.resolvedSymbols,receivedAt:mt5.receivedAt} : null,
    checkpoint:'SIGNALHUB_V3_CHECKPOINT_04',
  });
}

async function handleV3(req, env) {
  const url = new URL(req.url);
  if (req.method === 'OPTIONS') return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'content-type, authorization, x-signalhub-bridge','access-control-allow-methods':'GET,POST,OPTIONS'}});
  try {
    if (url.pathname === '/v3/status' && req.method === 'GET') return v3Status(env);
    if (url.pathname === '/v3/mt5/prices' && req.method === 'POST') return mt5Prices(req,env);
    if (url.pathname === '/v3/mt5/heartbeat' && req.method === 'POST') return mt5Heartbeat(req,env);
    if (url.pathname === '/v3/mt5/events' && req.method === 'POST') return mt5Event(req,env);
    if (url.pathname === '/v3/forex/live' && req.method === 'GET') return mt5Live(env);
    if (url.pathname === '/v3/crypto/tickers' && req.method === 'GET') return cryptoTickers(url);
    if (url.pathname === '/v3/crypto/universe' && req.method === 'GET') return cryptoUniverse(url);
    if (url.pathname === '/v3/crypto/discovery' && req.method === 'GET') return cryptoDiscovery(url);
    return null;
  } catch (e) {
    const msg=String(e?.message || e);
    const code=msg==='INVALID_JSON'?400:msg==='PAYLOAD_TOO_LARGE'?413:503;
    return json({ok:false,version:V3_VERSION,error:msg},code);
  }
}

export default {
  async fetch(req, env, ctx) {
    const v3 = await handleV3(req, env, ctx);
    if (v3) return v3;
    return legacy.fetch(req, env, ctx);
  },
  async scheduled(event, env, ctx) {
    if (typeof legacy.scheduled === 'function') return legacy.scheduled(event, env, ctx);
  },
};
