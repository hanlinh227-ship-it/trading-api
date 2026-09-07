const VERSION = 'SIGNALHUB-FOREX-2.1.0';
const SERVICE = 'SignalHub Forex / Metals / Energy Multi-Order Tracker';
const TV_FOREX = 'https://scanner.tradingview.com/forex/scan';
const TV_CFD = 'https://scanner.tradingview.com/cfd/scan';
const SIGNAL_TTL_SECONDS = 60 * 60 * 24 * 90;
const ACTIVE_TTL_SECONDS = 60 * 60 * 36;
const COOLDOWN_MS = 30 * 60 * 1000;
const SIGNAL_EXPIRY_MS = 24 * 60 * 60 * 1000;
const PENDING_EXPIRY_MS = 6 * 60 * 60 * 1000;
const MAX_NEW_PER_SCAN = 3;

const FOREX = [
  'AUDCAD','AUDCHF','AUDJPY','AUDNZD','AUDUSD','CADCHF','CADJPY','CHFJPY',
  'EURAUD','EURCAD','EURCHF','EURGBP','EURJPY','EURNZD','EURUSD',
  'GBPAUD','GBPCAD','GBPCHF','GBPJPY','GBPNZD','GBPUSD',
  'NZDCAD','NZDCHF','NZDJPY','NZDUSD','USDCAD','USDCHF','USDJPY'
];

const GROUPS = {
  forex: { endpoint: TV_FOREX, tickers: FOREX.map(x => `OANDA:${x}`) },
  metal: { endpoint: TV_CFD, tickers: ['OANDA:XAUUSD','TVC:SILVER'] },
  energy: { endpoint: TV_CFD, tickers: ['FX:UKOIL'] },
};

const COLUMNS = [
  'name','close','change','Recommend.All',
  'Recommend.All|5','Recommend.All|15','Recommend.All|60','Recommend.All|240',
  'RSI|15','MACD.macd|15','MACD.signal|15',
  'EMA20|15','EMA50|15','EMA200|15','ATR|15',
  'high|5','low|5','close|5'
];

const json = (body, status=200) => new Response(JSON.stringify(body, null, 2), {
  status,
  headers: {
    'content-type':'application/json; charset=utf-8',
    'cache-control':'no-store, no-cache, must-revalidate',
    'access-control-allow-origin':'*',
  },
});

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const sign = v => v > 0.05 ? 1 : v < -0.05 ? -1 : 0;
const clamp = (x,a,b) => Math.max(a,Math.min(b,x));
const round = (v,d=6) => Number(Number(v).toFixed(d));
const nowIso = () => new Date().toISOString();

function canonical(ticker, name) {
  if (ticker === 'TVC:SILVER') return 'XAGUSD';
  if (ticker === 'FX:UKOIL') return 'UKOIL';
  return String(name || ticker.split(':').pop() || '').toUpperCase();
}

function decimals(symbol) {
  if (symbol.includes('JPY')) return 3;
  if (symbol === 'XAUUSD') return 2;
  if (symbol === 'XAGUSD' || symbol === 'UKOIL') return 3;
  return 5;
}

async function tvScan(group) {
  const cfg = GROUPS[group];
  if (!cfg) throw new Error('INVALID_GROUP');
  const body = {
    symbols: { tickers: cfg.tickers, query: { types: [] } },
    columns: COLUMNS,
  };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort('timeout'), 9000);
  let r;
  try {
    r = await fetch(cfg.endpoint, {
      method:'POST',
      headers:{
        'content-type':'application/json',
        'accept':'application/json',
        'user-agent':'SignalHub-Worker/2.1',
      },
      body:JSON.stringify(body),
      signal:controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) throw new Error(`SOURCE_HTTP_${r.status}`);
  const p = await r.json();
  if (!p || !Array.isArray(p.data)) throw new Error('SOURCE_BAD_JSON');
  return p.data;
}

function quoteFromRow(row) {
  const d = Array.isArray(row?.d) ? row.d : [];
  if (d.length < COLUMNS.length) return null;
  const symbol = canonical(row.s, d[0]);
  const price = num(d[1]);
  if (!(price > 0)) return null;
  return {
    symbol,
    price,
    high5:num(d[15]) ?? price,
    low5:num(d[16]) ?? price,
    close5:num(d[17]) ?? price,
    ticker:String(row.s || ''),
  };
}

function classifyOrder({score, agree, emaAligned, direction, price, atr, ema20, high5, low5}) {
  const e20 = num(ema20);
  const h5 = num(high5) ?? price;
  const l5 = num(low5) ?? price;
  const strongMarket = score >= 90 && agree === 4 && emaAligned;
  if (strongMarket) return { orderType:'MARKET', entry:price, setupReason:'STRONG_MTF_MARKET_ALIGNMENT' };

  const pullbackDistance = atr * 0.35;
  if (emaAligned && e20 !== null) {
    let entry = direction > 0 ? Math.min(price - pullbackDistance, e20) : Math.max(price + pullbackDistance, e20);
    if (direction > 0 && entry < price && price-entry <= atr*0.85) {
      return { orderType:'LIMIT', entry, setupReason:'TREND_PULLBACK_TO_VALUE' };
    }
    if (direction < 0 && entry > price && entry-price <= atr*0.85) {
      return { orderType:'LIMIT', entry, setupReason:'TREND_PULLBACK_TO_VALUE' };
    }
  }

  const buffer = atr * 0.08;
  const entry = direction > 0 ? Math.max(price + buffer, h5 + buffer) : Math.min(price - buffer, l5 - buffer);
  return { orderType:'STOP', entry, setupReason:'BREAKOUT_CONFIRMATION_REQUIRED' };
}

function buildAnalysis(row, group, receivedAt) {
  const d = Array.isArray(row?.d) ? row.d : [];
  if (d.length < COLUMNS.length) return null;
  const [name, close, change, all, r5, r15, r60, r240, rsi15, macd, macdSignal, ema20, ema50, ema200, atr15, high5, low5, close5] = d;
  const price = num(close), atr = num(atr15);
  const vals = [r5,r15,r60,r240].map(v => num(v) ?? 0);
  if (!(price > 0) || !(atr > 0)) return null;

  const weighted = vals[0]*0.15 + vals[1]*0.30 + vals[2]*0.35 + vals[3]*0.20;
  const direction = weighted >= 0 ? 1 : -1;
  const agree = vals.reduce((n,v) => n + (sign(v) === direction ? 1 : 0), 0);
  const macdAligned = (num(macd) !== null && num(macdSignal) !== null)
    ? (direction > 0 ? macd > macdSignal : macd < macdSignal) : false;
  const emaAligned = [ema20,ema50,ema200].every(v => num(v) !== null) &&
    (direction > 0 ? (price > ema20 && ema20 >= ema50) : (price < ema20 && ema20 <= ema50));
  const rsi = num(rsi15);
  const rsiHealthy = rsi === null || (direction > 0 ? rsi < 72 : rsi > 28);

  let score = 45 + Math.abs(weighted)*32 + agree*4;
  if (macdAligned) score += 5;
  if (emaAligned) score += 5;
  if (!rsiHealthy) score -= 8;
  score = Math.round(clamp(score, 0, 99));

  const strong15 = sign(vals[1]) === direction && Math.abs(vals[1]) >= 0.25;
  const strong60 = sign(vals[2]) === direction && Math.abs(vals[2]) >= 0.25;
  const actionable = score >= 82 && agree >= 3 && strong15 && strong60 && rsiHealthy;
  const side = direction > 0 ? 'LONG' : 'SHORT';
  const symbol = canonical(row.s, name);
  const dp = decimals(symbol);

  let order = { orderType:'WATCH', entry:price, setupReason:'WAIT_FOR_STRONGER_ALIGNMENT' };
  if (actionable) {
    order = classifyOrder({score,agree,emaAligned,direction,price,atr,ema20,high5,low5});
  }

  const mult = group === 'forex' ? 1.35 : group === 'metal' ? 1.20 : 1.30;
  const risk = atr * mult;
  const entry = order.entry;
  const sl = direction > 0 ? entry-risk : entry+risk;
  const tp = direction > 0 ? entry+risk*2.2 : entry-risk*2.2;
  const status = actionable ? `${order.orderType}_SIGNAL` : 'WATCH';

  return {
    symbol,
    group,
    side,
    orderType: order.orderType,
    status,
    score,
    reason: actionable ? order.setupReason : 'WAIT_FOR_STRONGER_ALIGNMENT',
    planned: {
      orderType: order.orderType,
      entry: round(entry, dp),
      sl: round(sl, dp),
      tp: round(tp, dp),
      targetRR: 2.2,
      pendingExpiryMinutes: order.orderType === 'MARKET' ? 0 : Math.round(PENDING_EXPIRY_MS/60000),
    },
    analysisQuote: {
      price: round(price, 6),
      source: `TRADINGVIEW:${String(row.s||'').split(':')[0] || 'SCAN'}`,
      fresh: true,
      receivedAt,
      freshnessBasis: 'LIVE_SCAN_RESPONSE_NO_PROVIDER_TIMESTAMP',
      high5:num(high5), low5:num(low5), close5:num(close5),
    },
    technical: {
      recommend5m: round(vals[0],3), recommend15m: round(vals[1],3),
      recommend1h: round(vals[2],3), recommend4h: round(vals[3],3),
      rsi15: rsi === null ? null : round(rsi,2),
      macdAligned, emaAligned, atr15: round(atr,6), changePct: num(change),
      agreement:agree,
    },
  };
}

async function kvGetJson(kv, key) {
  if (!kv) return null;
  const raw = await kv.get(key);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

async function kvPutJson(kv, key, value, ttl=SIGNAL_TTL_SECONDS) {
  if (!kv) return;
  await kv.put(key, JSON.stringify(value), { expirationTtl: ttl });
}

function isActiveStatus(status) {
  return status === 'PENDING' || status === 'OPEN';
}

async function getActiveSignal(kv, symbol) {
  const id = await kv.get(`active:${symbol}`);
  if (!id) return null;
  const s = await kvGetJson(kv, `signal:${id}`);
  if (!s || !isActiveStatus(s.status)) {
    await kv.delete(`active:${symbol}`);
    return null;
  }
  return s;
}

async function closeSignal(kv, s, outcome, exitPrice, resultR, checkedAt, resolution) {
  s.status = 'CLOSED';
  s.outcome = outcome;
  s.exitPrice = round(exitPrice, decimals(s.symbol));
  s.resultR = resultR === null ? null : round(resultR, 3);
  s.closedAt = checkedAt;
  s.lastCheckedAt = checkedAt;
  s.resolution = resolution;
  await kvPutJson(kv, `signal:${s.id}`, s);
  await kv.delete(`active:${s.symbol}`);
  await kv.put(`cooldown:${s.symbol}`, String(Date.now()), { expirationTtl: 60*60 });
  return s;
}

function pendingTriggered(s, q) {
  if (s.orderType === 'LIMIT') {
    return s.side === 'LONG' ? q.low5 <= s.entry : q.high5 >= s.entry;
  }
  if (s.orderType === 'STOP') {
    return s.side === 'LONG' ? q.high5 >= s.entry : q.low5 <= s.entry;
  }
  return true;
}

async function updateTrackedSignals(kv, group, rows, checkedAt) {
  const events = [];
  if (!kv) return events;
  const quotes = new Map();
  for (const row of rows) {
    const q = quoteFromRow(row);
    if (q) quotes.set(q.symbol, q);
  }

  for (const [symbol, q] of quotes.entries()) {
    const s = await getActiveSignal(kv, symbol);
    if (!s || s.group !== group) continue;

    s.lastPrice = round(q.price, decimals(symbol));
    s.lastCheckedAt = checkedAt;
    s.lastCandle5 = { high:round(q.high5,decimals(symbol)), low:round(q.low5,decimals(symbol)), close:round(q.close5,decimals(symbol)) };

    if (s.status === 'PENDING') {
      if (Date.now() >= Date.parse(s.pendingExpiresAt || s.expiresAt)) {
        const closed = await closeSignal(kv, s, 'EXPIRED', q.price, null, checkedAt, 'PENDING_ORDER_NOT_TRIGGERED_BEFORE_EXPIRY');
        events.push({ type:'OUTCOME', signal:closed });
        continue;
      }
      if (!pendingTriggered(s, q)) {
        await kvPutJson(kv, `signal:${s.id}`, s);
        continue;
      }
      s.status = 'OPEN';
      s.triggeredAt = checkedAt;
      s.triggerPrice = s.entry;
      s.currentR = 0;
      s.maxFavorableR = 0;
      s.maxAdverseR = 0;
      s.resolution = 'PENDING_ORDER_TRIGGERED_BY_5M_HIGH_LOW';
      await kvPutJson(kv, `signal:${s.id}`, s);
      events.push({ type:'TRIGGERED', signal:s });
      continue;
    }

    const risk = Math.abs(Number(s.entry) - Number(s.sl));
    if (!(risk > 0)) continue;
    const direction = s.side === 'LONG' ? 1 : -1;
    const currentR = direction * (q.price - s.entry) / risk;
    const favorablePx = s.side === 'LONG' ? q.high5 : q.low5;
    const adversePx = s.side === 'LONG' ? q.low5 : q.high5;
    const favorableR = direction * (favorablePx - s.entry) / risk;
    const adverseR = direction * (adversePx - s.entry) / risk;

    s.currentR = round(currentR, 3);
    s.maxFavorableR = round(Math.max(Number(s.maxFavorableR ?? -999), favorableR), 3);
    s.maxAdverseR = round(Math.min(Number(s.maxAdverseR ?? 999), adverseR), 3);

    const tpHit = s.side === 'LONG' ? q.high5 >= s.tp : q.low5 <= s.tp;
    const slHit = s.side === 'LONG' ? q.low5 <= s.sl : q.high5 >= s.sl;
    const activeSince = s.triggeredAt || s.issuedAt;
    const ageMs = Date.now() - Date.parse(activeSince);

    let closed = null;
    if (ageMs > 60_000 && tpHit && slHit) {
      closed = await closeSignal(kv, s, 'AMBIGUOUS', q.price, null, checkedAt, 'TP_AND_SL_TOUCHED_INSIDE_SAME_5M_CANDLE_ORDER_UNKNOWN');
    } else if (ageMs > 60_000 && tpHit) {
      closed = await closeSignal(kv, s, 'TP', s.tp, Number(s.targetRR || 2.2), checkedAt, 'TP_LEVEL_TOUCHED_BY_5M_HIGH_LOW');
    } else if (ageMs > 60_000 && slHit) {
      closed = await closeSignal(kv, s, 'SL', s.sl, -1, checkedAt, 'SL_LEVEL_TOUCHED_BY_5M_HIGH_LOW');
    } else if (Date.now() >= Date.parse(s.expiresAt)) {
      closed = await closeSignal(kv, s, 'EXPIRED', q.price, currentR, checkedAt, 'MAX_TRACKING_AGE_REACHED');
    } else {
      await kvPutJson(kv, `signal:${s.id}`, s);
    }
    if (closed) events.push({ type:'OUTCOME', signal:closed });
  }
  return events;
}

async function maybeCreateSignals(kv, group, actionable, scannedAt) {
  const events = [];
  if (!kv) return events;
  let created = 0;
  for (const a of actionable) {
    if (created >= MAX_NEW_PER_SCAN) break;
    const existing = await getActiveSignal(kv, a.symbol);
    if (existing) {
      a.tracker = {
        signalId:existing.id,
        status:existing.status,
        orderType:existing.orderType,
        currentR:existing.currentR ?? 0,
        outcome:existing.outcome || null,
        duplicateBlocked:true,
      };
      continue;
    }
    const cooldown = Number(await kv.get(`cooldown:${a.symbol}`) || 0);
    if (cooldown && Date.now() - cooldown < COOLDOWN_MS) {
      a.tracker = { status:'COOLDOWN', remainingSec:Math.ceil((COOLDOWN_MS-(Date.now()-cooldown))/1000), duplicateBlocked:true };
      continue;
    }

    const orderType = a.orderType || a.planned?.orderType || 'MARKET';
    const initialStatus = orderType === 'MARKET' ? 'OPEN' : 'PENDING';
    const id = `${a.symbol}-${orderType}-${a.side}-${Date.now()}-${crypto.randomUUID().slice(0,8)}`;
    const risk = Math.abs(a.planned.entry - a.planned.sl);
    const s = {
      id,
      schema:'SIGNALHUB_TRACKED_SIGNAL_V2',
      group,
      symbol:a.symbol,
      side:a.side,
      orderType,
      score:a.score,
      status:initialStatus,
      outcome:null,
      entry:a.planned.entry,
      sl:a.planned.sl,
      tp:a.planned.tp,
      targetRR:a.planned.targetRR,
      riskDistance:round(risk, 8),
      issuedAt:scannedAt,
      triggeredAt:orderType === 'MARKET' ? scannedAt : null,
      pendingExpiresAt:orderType === 'MARKET' ? null : new Date(Date.parse(scannedAt) + PENDING_EXPIRY_MS).toISOString(),
      expiresAt:new Date(Date.parse(scannedAt) + SIGNAL_EXPIRY_MS).toISOString(),
      source:a.analysisQuote?.source || 'TRADINGVIEW_SCANNER',
      sourcePrice:a.analysisQuote?.price ?? a.planned.entry,
      lastPrice:a.analysisQuote?.price ?? a.planned.entry,
      lastCheckedAt:scannedAt,
      currentR:orderType === 'MARKET' ? 0 : null,
      maxFavorableR:orderType === 'MARKET' ? 0 : null,
      maxAdverseR:orderType === 'MARKET' ? 0 : null,
      reason:a.reason,
      technicalAtIssue:a.technical,
    };
    await kvPutJson(kv, `signal:${id}`, s);
    await kv.put(`active:${a.symbol}`, id, { expirationTtl: ACTIVE_TTL_SECONDS });
    a.tracker = { signalId:id, status:initialStatus, orderType, currentR:s.currentR, outcome:null, duplicateBlocked:false };
    events.push({ type:'NEW_SIGNAL', signal:s });
    created++;
  }
  return events;
}

async function annotateAnalyses(kv, analyses) {
  if (!kv) return;
  for (const a of analyses) {
    if (a.tracker) continue;
    const s = await getActiveSignal(kv, a.symbol);
    if (s) {
      a.tracker = {
        signalId:s.id,
        status:s.status,
        orderType:s.orderType,
        currentR:s.currentR ?? 0,
        outcome:s.outcome || null,
        duplicateBlocked:true,
      };
    }
  }
}

async function scan(group, env, options={}) {
  const started = Date.now();
  const scannedAt = nowIso();
  try {
    const rows = await tvScan(group);
    const analyses = rows.map(r => buildAnalysis(r,group,scannedAt)).filter(Boolean)
      .sort((a,b) => b.score-a.score);
    const actionable = analyses.filter(x => x.status.endsWith('_SIGNAL'));
    const trackerEvents = [];
    if (env?.SIGNALS_KV) {
      trackerEvents.push(...await updateTrackedSignals(env.SIGNALS_KV, group, rows, scannedAt));
      if (options.emitSignals !== false) trackerEvents.push(...await maybeCreateSignals(env.SIGNALS_KV, group, actionable, scannedAt));
      await annotateAnalyses(env.SIGNALS_KV, analyses);
    }
    const display = actionable.length ? [...actionable, ...analyses.filter(x=>!x.status.endsWith('_SIGNAL'))].slice(0,8) : analyses.slice(0,8);
    const orderMix = actionable.reduce((o,x)=>{o[x.orderType]=(o[x.orderType]||0)+1;return o;},{});
    return {
      ok:true,
      version:VERSION,
      group,
      status: rows.length === 0 ? 'MARKET_CLOSED_OR_NO_DATA' : 'OK',
      scanId:`${group}-${Date.now()}`,
      scannedAt,
      source:'TRADINGVIEW_SCANNER',
      sourceRows:rows.length,
      requested:GROUPS[group].tickers.length,
      broadOk:rows.length,
      deepOk:analyses.length,
      deepRequested:rows.length,
      elapsedMs:Date.now()-started,
      analyses:display,
      actionableCount:actionable.length,
      orderMix,
      tracker:{ enabled:Boolean(env?.SIGNALS_KV), events:trackerEvents, oneActiveSetupPerSymbol:true },
      note:'One active setup per symbol across MARKET/LIMIT/STOP. LIMIT/STOP remain PENDING until entry is touched, then become OPEN. No second setup is emitted for that symbol until the active setup closes/expires and cooldown passes.',
    };
  } catch (e) {
    return {
      ok:false,
      version:VERSION,
      group,
      status:'SOURCE_UNAVAILABLE',
      scanId:`${group}-${Date.now()}`,
      scannedAt,
      analyses:[],
      tracker:{ enabled:Boolean(env?.SIGNALS_KV), events:[], oneActiveSetupPerSymbol:true },
      error:String(e?.message||e),
      elapsedMs:Date.now()-started,
    };
  }
}

async function listSignals(env, filters={}) {
  if (!env?.SIGNALS_KV) return [];
  const listing = await env.SIGNALS_KV.list({ prefix:'signal:', limit:1000 });
  const items = [];
  const keys = listing.keys || [];
  for (let i=0; i<keys.length; i+=50) {
    const batch = keys.slice(i,i+50);
    const vals = await Promise.all(batch.map(k => kvGetJson(env.SIGNALS_KV, k.name)));
    for (const s of vals) if (s) items.push(s);
  }
  let out = items;
  if (filters.group && GROUPS[filters.group]) out = out.filter(s => s.group === filters.group);
  if (filters.status === 'open') out = out.filter(s => s.status === 'OPEN');
  if (filters.status === 'pending') out = out.filter(s => s.status === 'PENDING');
  if (filters.status === 'active') out = out.filter(s => isActiveStatus(s.status));
  if (filters.status === 'closed') out = out.filter(s => s.status === 'CLOSED');
  if (filters.outcome) out = out.filter(s => String(s.outcome||'').toUpperCase() === filters.outcome.toUpperCase());
  out.sort((a,b) => Date.parse(b.issuedAt||0) - Date.parse(a.issuedAt||0));
  const limit = clamp(Number(filters.limit || 100),1,500);
  return out.slice(0, limit);
}

function performanceFromSignals(signals) {
  const closed = signals.filter(s => s.status === 'CLOSED');
  const open = signals.filter(s => s.status === 'OPEN');
  const pending = signals.filter(s => s.status === 'PENDING');
  const active = [...open,...pending];
  const tp = closed.filter(s => s.outcome === 'TP');
  const sl = closed.filter(s => s.outcome === 'SL');
  const expired = closed.filter(s => s.outcome === 'EXPIRED');
  const ambiguous = closed.filter(s => s.outcome === 'AMBIGUOUS');
  const resolved = [...tp,...sl].sort((a,b)=>Date.parse(a.closedAt||0)-Date.parse(b.closedAt||0));
  const winRate = resolved.length ? tp.length/resolved.length*100 : 0;
  const grossWinR = tp.reduce((n,s)=>n+Number(s.resultR||0),0);
  const grossLossR = Math.abs(sl.reduce((n,s)=>n+Number(s.resultR||0),0));
  const netR = resolved.reduce((n,s)=>n+Number(s.resultR||0),0);
  const avgR = resolved.length ? netR/resolved.length : 0;
  const profitFactor = grossLossR > 0 ? grossWinR/grossLossR : (grossWinR > 0 ? null : 0);

  let currentWinStreak=0,currentLossStreak=0,maxWinStreak=0,maxLossStreak=0;
  for (const s of resolved) {
    if (s.outcome === 'TP') { currentWinStreak++; currentLossStreak=0; maxWinStreak=Math.max(maxWinStreak,currentWinStreak); }
    else { currentLossStreak++; currentWinStreak=0; maxLossStreak=Math.max(maxLossStreak,currentLossStreak); }
  }

  const byOrderType = {};
  for (const type of ['MARKET','LIMIT','STOP']) {
    const arr = signals.filter(s => (s.orderType || 'MARKET') === type);
    const w = arr.filter(s=>s.outcome==='TP').length;
    const l = arr.filter(s=>s.outcome==='SL').length;
    byOrderType[type] = {
      total:arr.length,
      active:arr.filter(s=>isActiveStatus(s.status)).length,
      pending:arr.filter(s=>s.status==='PENDING').length,
      open:arr.filter(s=>s.status==='OPEN').length,
      tp:w,
      sl:l,
      winRate:(w+l)?round(w/(w+l)*100,1):0,
    };
  }

  const byGroup = {};
  for (const g of Object.keys(GROUPS)) {
    const arr = signals.filter(s=>s.group===g);
    const w = arr.filter(s=>s.outcome==='TP').length;
    const l = arr.filter(s=>s.outcome==='SL').length;
    byGroup[g] = {
      total:arr.length,
      active:arr.filter(s=>isActiveStatus(s.status)).length,
      pending:arr.filter(s=>s.status==='PENDING').length,
      open:arr.filter(s=>s.status==='OPEN').length,
      tp:w,
      sl:l,
      winRate:(w+l)?round(w/(w+l)*100,1):0,
    };
  }

  const symbolMap = {};
  for (const s of signals) {
    const x = symbolMap[s.symbol] || {symbol:s.symbol,total:0,tp:0,sl:0,open:0,pending:0,active:0,netR:0};
    x.total++;
    if (s.status==='OPEN') x.open++;
    if (s.status==='PENDING') x.pending++;
    if (isActiveStatus(s.status)) x.active++;
    if (s.outcome==='TP') x.tp++;
    if (s.outcome==='SL') x.sl++;
    if (s.outcome==='TP' || s.outcome==='SL') x.netR += Number(s.resultR||0);
    symbolMap[s.symbol] = x;
  }
  const bySymbol = Object.values(symbolMap).map(x=>({ ...x, netR:round(x.netR,2), winRate:(x.tp+x.sl)?round(x.tp/(x.tp+x.sl)*100,1):0 }))
    .sort((a,b)=>b.total-a.total).slice(0,20);

  return {
    totalSignals:signals.length,
    active:active.length,
    pending:pending.length,
    open:open.length,
    closed:closed.length,
    resolved:resolved.length,
    tp:tp.length,
    sl:sl.length,
    expired:expired.length,
    ambiguous:ambiguous.length,
    winRateResolved:round(winRate,1),
    netRResolved:round(netR,2),
    avgRResolved:round(avgR,2),
    grossWinR:round(grossWinR,2),
    grossLossR:round(grossLossR,2),
    profitFactor:profitFactor===null?null:round(profitFactor,2),
    maxWinStreak,
    maxLossStreak,
    byOrderType,
    byGroup,
    bySymbol,
    methodology:'Win rate = TP / (TP + SL) only after a setup is triggered. PENDING setups do not affect win rate. EXPIRED and AMBIGUOUS are excluded from resolved win rate.',
  };
}

async function handle(req, env) {
  const u = new URL(req.url);
  if (req.method === 'OPTIONS') return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-methods':'GET,OPTIONS'}});
  if (req.method !== 'GET') return json({ok:false,error:'GET_ONLY'},405);

  if (u.pathname === '/' || u.pathname === '/status') {
    const all = env?.SIGNALS_KV ? await listSignals(env,{limit:500}) : [];
    const perf = performanceFromSignals(all);
    return json({
      ok:true, version:VERSION, service:SERVICE,
      independentFromBybit:true,
      dataSource:'TRADINGVIEW_SCANNER',
      trackerStorage:Boolean(env?.SIGNALS_KV),
      trackerCheckInterval:'5m scheduled + manual scans',
      groups:Object.keys(GROUPS),
      symbols:{forex:FOREX,metal:['XAUUSD','XAGUSD'],energy:['UKOIL']},
      supportedOrderTypes:['MARKET','LIMIT','STOP'],
      oneActiveSetupPerSymbol:true,
      pendingExpiry:'6h',
      staleFallback:false,
      trackerSummary:{active:perf.active,pending:perf.pending,open:perf.open,closed:perf.closed,tp:perf.tp,sl:perf.sl,winRateResolved:perf.winRateResolved,netRResolved:perf.netRResolved},
      generatedAt:nowIso(),
    });
  }
  if (u.pathname === '/symbols') {
    const g=u.searchParams.get('group');
    if (!GROUPS[g]) return json({ok:false,error:'INVALID_GROUP'},400);
    const symbols = g==='forex' ? FOREX : g==='metal' ? ['XAUUSD','XAGUSD'] : ['UKOIL'];
    return json({ok:true,group:g,symbols});
  }
  if (u.pathname === '/latest-scan' || u.pathname === '/run-now') {
    const g=u.searchParams.get('group');
    if (!GROUPS[g]) return json({ok:false,error:'INVALID_GROUP'},400);
    const result=await scan(g,env,{emitSignals:true});
    if (u.pathname === '/latest-scan') return json({ok:result.ok,group:g,snapshot:result},result.ok?200:503);
    return json(result,result.ok?200:503);
  }
  if (u.pathname === '/signals') {
    const status=(u.searchParams.get('status')||'all').toLowerCase();
    const group=(u.searchParams.get('group')||'').toLowerCase();
    const outcome=u.searchParams.get('outcome')||'';
    const limit=u.searchParams.get('limit')||'100';
    const signals=await listSignals(env,{status,group,outcome,limit});
    return json({ok:true,version:VERSION,status,group:group||'all',count:signals.length,signals,generatedAt:nowIso()});
  }
  if (u.pathname === '/signal') {
    const id=u.searchParams.get('id');
    if (!id) return json({ok:false,error:'ID_REQUIRED'},400);
    const s=await kvGetJson(env?.SIGNALS_KV,`signal:${id}`);
    return s ? json({ok:true,signal:s}) : json({ok:false,error:'SIGNAL_NOT_FOUND'},404);
  }
  if (u.pathname === '/performance') {
    const signals=await listSignals(env,{limit:500});
    return json({ok:true,version:VERSION,performance:performanceFromSignals(signals),generatedAt:nowIso()});
  }
  if (u.pathname === '/books') {
    const active=await listSignals(env,{status:'active',limit:100});
    return json({ok:true,marketActive:active,activeCount:active.length,note:'Read-only tracked signal book; no broker execution. One active setup per symbol.'});
  }
  if (u.pathname === '/shadow') {
    const closed=await listSignals(env,{status:'closed',limit:100});
    return json({ok:true,rows:closed,closedCount:closed.length,note:'Outcome history for emitted SignalHub signals.'});
  }
  return json({ok:false,error:'NOT_FOUND',endpoints:['/status','/latest-scan?group=forex|metal|energy','/run-now?group=forex|metal|energy','/signals?status=pending|open|active|closed|all','/signal?id=...','/performance','/symbols?group=forex|metal|energy','/books','/shadow']},404);
}

async function scheduled(_event, env, ctx) {
  ctx.waitUntil((async()=>{
    for (const g of ['forex','metal','energy']) {
      try { await scan(g,env,{emitSignals:true}); } catch (_) {}
    }
  })());
}

export default { fetch: handle, scheduled };
