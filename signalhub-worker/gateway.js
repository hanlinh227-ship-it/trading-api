import tracker from './engine-v21.js';

const GATEWAY_VERSION = 'SIGNALHUB-GATEWAY-2.1.1';
const TV_FOREX = 'https://scanner.tradingview.com/forex/scan';
const TV_CFD = 'https://scanner.tradingview.com/cfd/scan';
const DEDUPE_MARKER = 'migration:active-dedupe-v211';
const SIGNAL_TTL_SECONDS = 60 * 60 * 24 * 90;
const ACTIVE_TTL_SECONDS = 60 * 60 * 36;

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

const APP_RELEASE = {
  versionCode: 5,
  versionName: '2.1.0',
  title: 'SignalHub FX Tracker 2.1.0',
  releasedAt: '2026-09-07T00:00:00Z',
  mandatory: false,
  minSupportedVersionCode: 4,
  artifactName: 'SignalHub-FX-Tracker-Android-v2.1.0',
  notes: [
    'Redesigned mobile layout with wider two-column navigation and less cramped controls.',
    'Foreground live quote feed with 5-second refresh for price and pip movement display.',
    'Automatic app-version checks and update notifications for future releases.',
    'MARKET, LIMIT and STOP setups with one active setup allowed per symbol.',
    'LIMIT/STOP remain PENDING until entry is touched; only then do TP/SL and R tracking start.',
    'Server-side signal history remains independent from app reinstall/update.'
  ]
};

const json = (body, status = 200) => new Response(JSON.stringify(body, null, 2), {
  status,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store, no-cache, must-revalidate',
    'access-control-allow-origin': '*',
  },
});

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

function canonical(ticker, name) {
  if (ticker === 'TVC:SILVER') return 'XAGUSD';
  if (ticker === 'FX:UKOIL') return 'UKOIL';
  return String(name || ticker.split(':').pop() || '').toUpperCase();
}

function quoteUnit(group, symbol) {
  if (group === 'forex') {
    return { unit: 'pip', pipSize: symbol.includes('JPY') ? 0.01 : 0.0001 };
  }
  return { unit: 'point', pipSize: 0.01 };
}

async function scanQuotes(group) {
  const cfg = GROUPS[group];
  if (!cfg) throw new Error('INVALID_GROUP');
  const receivedAt = new Date().toISOString();
  const body = {
    symbols: { tickers: cfg.tickers, query: { types: [] } },
    columns: ['name','close','change','close|1','close|5'],
  };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort('timeout'), 7000);
  let response;
  try {
    response = await fetch(cfg.endpoint, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'accept': 'application/json',
        'user-agent': 'SignalHub-LiveQuote/2.1',
      },
      body: JSON.stringify(body),
      signal:controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) throw new Error(`SOURCE_HTTP_${response.status}`);
  const payload = await response.json();
  if (!payload || !Array.isArray(payload.data)) throw new Error('SOURCE_BAD_JSON');

  const quotes = [];
  for (const row of payload.data) {
    const d = Array.isArray(row?.d) ? row.d : [];
    const price = num(d[1]);
    if (!(price > 0)) continue;
    const symbol = canonical(String(row?.s || ''), d[0]);
    const unitInfo = quoteUnit(group, symbol);
    quotes.push({
      group,
      symbol,
      ticker: String(row?.s || ''),
      price,
      changePct: num(d[2]),
      close1m: num(d[3]),
      close5m: num(d[4]),
      unit: unitInfo.unit,
      pipSize: unitInfo.pipSize,
      source: `TRADINGVIEW:${String(row?.s || '').split(':')[0] || 'SCAN'}`,
      receivedAt,
      freshnessBasis: 'LIVE_SCAN_RESPONSE_NO_PROVIDER_TIMESTAMP',
    });
  }
  quotes.sort((a, b) => a.symbol.localeCompare(b.symbol));
  return { group, receivedAt, count: quotes.length, quotes };
}

async function handleLiveQuotes(url) {
  const group = String(url.searchParams.get('group') || 'all').toLowerCase();
  const groups = group === 'all' ? ['forex','metal','energy'] : [group];
  if (groups.some(g => !GROUPS[g])) return json({ ok:false, error:'INVALID_GROUP' }, 400);
  const started = Date.now();
  const settled = await Promise.allSettled(groups.map(scanQuotes));
  const quotes = [];
  const errors = [];
  let latestAt = null;
  settled.forEach((result, i) => {
    if (result.status === 'fulfilled') {
      quotes.push(...result.value.quotes);
      latestAt = result.value.receivedAt;
    } else {
      errors.push({ group: groups[i], error: String(result.reason?.message || result.reason) });
    }
  });
  return json({
    ok: quotes.length > 0,
    gatewayVersion: GATEWAY_VERSION,
    group,
    quotes,
    count: quotes.length,
    errors,
    receivedAt: latestAt || new Date().toISOString(),
    elapsedMs: Date.now() - started,
    suggestedRefreshMs: 5000,
    streaming: false,
    note: 'Foreground near-real-time quote refresh. TradingView scanner does not expose an exact provider-origin timestamp, so this is not claimed as tick-streaming data.'
  }, quotes.length > 0 ? 200 : 503);
}

function isActiveSignal(s) {
  return s && (s.status === 'PENDING' || s.status === 'OPEN') && s.symbol;
}

async function reconcileLegacyActiveSignals(env) {
  const kv = env?.SIGNALS_KV;
  if (!kv) return { ran:false, reason:'NO_KV' };
  if (await kv.get(DEDUPE_MARKER)) return { ran:false, reason:'ALREADY_RECONCILED' };

  const listing = await kv.list({ prefix:'signal:', limit:1000 });
  const keys = listing.keys || [];
  const signals = [];
  for (let i = 0; i < keys.length; i += 50) {
    const batch = keys.slice(i, i + 50);
    const raws = await Promise.all(batch.map(k => kv.get(k.name)));
    for (const raw of raws) {
      if (!raw) continue;
      try {
        const s = JSON.parse(raw);
        if (isActiveSignal(s)) signals.push(s);
      } catch (_) {}
    }
  }

  const bySymbol = new Map();
  for (const s of signals) {
    const arr = bySymbol.get(s.symbol) || [];
    arr.push(s);
    bySymbol.set(s.symbol, arr);
  }

  const now = new Date().toISOString();
  let duplicatesClosed = 0;
  let activePointersRepaired = 0;
  for (const [symbol, arr] of bySymbol.entries()) {
    arr.sort((a, b) => Date.parse(a.issuedAt || 0) - Date.parse(b.issuedAt || 0));
    const keeper = arr[0];
    await kv.put(`active:${symbol}`, keeper.id, { expirationTtl: ACTIVE_TTL_SECONDS });
    activePointersRepaired++;

    for (const duplicate of arr.slice(1)) {
      duplicate.status = 'CLOSED';
      duplicate.outcome = 'CANCELLED';
      duplicate.closedAt = now;
      duplicate.lastCheckedAt = now;
      duplicate.exitPrice = duplicate.lastPrice ?? duplicate.sourcePrice ?? duplicate.entry ?? null;
      duplicate.resultR = null;
      duplicate.resolution = 'DUPLICATE_ACTIVE_SYMBOL_RECONCILED_KEEP_OLDEST';
      duplicate.duplicateOf = keeper.id;
      duplicate.orderType = duplicate.orderType || 'MARKET';
      await kv.put(`signal:${duplicate.id}`, JSON.stringify(duplicate), { expirationTtl: SIGNAL_TTL_SECONDS });
      duplicatesClosed++;
    }
  }

  const summary = { at:now, activeSymbols:bySymbol.size, duplicatesClosed, activePointersRepaired };
  await kv.put(DEDUPE_MARKER, JSON.stringify(summary));
  return { ran:true, ...summary };
}

async function augmentStatus(req, env, ctx, reconciliation) {
  const response = await tracker.fetch(req, env, ctx);
  try {
    const body = await response.json();
    body.gatewayVersion = GATEWAY_VERSION;
    body.appLatest = APP_RELEASE;
    body.activeSymbolReconciliation = reconciliation;
    body.liveQuotes = {
      endpoint: '/live-quotes?group=all',
      suggestedRefreshMs: 5000,
      streaming: false,
      freshnessBasis: 'LIVE_SCAN_RESPONSE_NO_PROVIDER_TIMESTAMP'
    };
    return json(body, response.status);
  } catch (_) {
    return response;
  }
}

async function handle(req, env, ctx) {
  const reconciliation = await reconcileLegacyActiveSignals(env);
  const url = new URL(req.url);
  if (req.method === 'OPTIONS') {
    return new Response(null, { status:204, headers:{
      'access-control-allow-origin':'*',
      'access-control-allow-methods':'GET,OPTIONS'
    }});
  }
  if (req.method !== 'GET') return json({ ok:false, error:'GET_ONLY' }, 405);

  if (url.pathname === '/app-version') {
    return json({
      ok:true,
      gatewayVersion:GATEWAY_VERSION,
      app:APP_RELEASE,
      generatedAt:new Date().toISOString()
    });
  }
  if (url.pathname === '/live-quotes') return handleLiveQuotes(url);
  if (url.pathname === '/' || url.pathname === '/status') return augmentStatus(req, env, ctx, reconciliation);
  return tracker.fetch(req, env, ctx);
}

async function scheduled(event, env, ctx) {
  await reconcileLegacyActiveSignals(env);
  return tracker.scheduled(event, env, ctx);
}

export default {
  fetch: handle,
  scheduled,
};