import tracker from './engine-v21.js';

const GATEWAY_VERSION = 'SIGNALHUB-GATEWAY-2.1.2';
const TV_FOREX = 'https://scanner.tradingview.com/forex/scan';
const TV_CFD = 'https://scanner.tradingview.com/cfd/scan';
const DEDUPE_MARKER = 'migration:active-dedupe-v211';
const SIGNAL_TTL_SECONDS = 60 * 60 * 24 * 90;
const ACTIVE_TTL_SECONDS = 60 * 60 * 36;

// Moderate cadence / quality-first policy. This only controls NEW signal emission.
// Existing PENDING/OPEN signals continue to be tracked on every scan.
const CADENCE_POLICY = {
  minGlobalSpacingMs: 20 * 60 * 1000,
  maxNewPerScan: 1,
  maxActiveTotal: 12,
  maxActiveByGroup: { forex: 8, metal: 2, energy: 2 },
  minScore: { MARKET: 93, LIMIT: 88, STOP: 90 },
};
const LAST_NEW_SIGNAL_KEY = 'cadence:last-new-signal-at-v212';

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
const recSign = v => Number(v) > 0.05 ? 1 : Number(v) < -0.05 ? -1 : 0;

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

async function loadActiveSignals(kv) {
  if (!kv) return [];
  const listing = await kv.list({ prefix:'signal:', limit:1000 });
  const keys = listing.keys || [];
  const out = [];
  for (let i = 0; i < keys.length; i += 50) {
    const batch = keys.slice(i, i + 50);
    const raws = await Promise.all(batch.map(k => kv.get(k.name)));
    for (const raw of raws) {
      if (!raw) continue;
      try {
        const s = JSON.parse(raw);
        if (isActiveSignal(s)) out.push(s);
      } catch (_) {}
    }
  }
  return out;
}

async function reconcileLegacyActiveSignals(env) {
  const kv = env?.SIGNALS_KV;
  if (!kv) return { ran:false, reason:'NO_KV' };
  if (await kv.get(DEDUPE_MARKER)) return { ran:false, reason:'ALREADY_RECONCILED' };

  const signals = await loadActiveSignals(kv);
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

function qualityDecision(signal, state) {
  const type = String(signal.orderType || 'MARKET').toUpperCase();
  const t = signal.technicalAtIssue || {};
  const score = Number(signal.score || 0);
  const dir = signal.side === 'LONG' ? 1 : -1;
  const r5 = Number(t.recommend5m || 0);
  const r15 = Number(t.recommend15m || 0);
  const r60 = Number(t.recommend1h || 0);
  const r240 = Number(t.recommend4h || 0);
  const rsi = Number(t.rsi15);
  const agreement = Number(t.agreement || 0);
  const htfAligned = recSign(r15) === dir && recSign(r60) === dir && recSign(r240) === dir;
  const strong15 = recSign(r15) === dir && Math.abs(r15) >= 0.30;
  const strong60 = recSign(r60) === dir && Math.abs(r60) >= 0.30;
  const meaningful4h = recSign(r240) === dir && Math.abs(r240) >= 0.10;
  const fiveAligned = recSign(r5) === dir;
  const rsiNotExtreme = Number.isFinite(rsi) && rsi >= 30 && rsi <= 70;
  const rsiDirectional = Number.isFinite(rsi) && (dir > 0 ? rsi >= 48 && rsi <= 68 : rsi >= 32 && rsi <= 52);
  const emaAligned = t.emaAligned === true;
  const macdAligned = t.macdAligned === true;

  if (state.activeCount >= CADENCE_POLICY.maxActiveTotal) {
    return { allow:false, reason:'ACTIVE_TOTAL_CAP_REACHED' };
  }
  const groupCap = CADENCE_POLICY.maxActiveByGroup[signal.group] ?? CADENCE_POLICY.maxActiveTotal;
  if ((state.activeByGroup[signal.group] || 0) >= groupCap) {
    return { allow:false, reason:'ACTIVE_GROUP_CAP_REACHED' };
  }
  if (state.localCreated >= CADENCE_POLICY.maxNewPerScan) {
    return { allow:false, reason:'MAX_NEW_PER_SCAN_REACHED' };
  }
  if (state.lastSignalAt && Date.now() - state.lastSignalAt < CADENCE_POLICY.minGlobalSpacingMs) {
    return {
      allow:false,
      reason:'GLOBAL_SIGNAL_SPACING',
      retryAfterSec:Math.ceil((CADENCE_POLICY.minGlobalSpacingMs - (Date.now()-state.lastSignalAt))/1000),
    };
  }
  if (!(type in CADENCE_POLICY.minScore) || score < CADENCE_POLICY.minScore[type]) {
    return { allow:false, reason:`QUALITY_SCORE_BELOW_${CADENCE_POLICY.minScore[type] || 'MIN'}` };
  }
  if (!htfAligned || !strong15 || !strong60 || !meaningful4h) {
    return { allow:false, reason:'WAIT_STRONGER_15M_1H_4H_ALIGNMENT' };
  }
  if (!emaAligned) return { allow:false, reason:'WAIT_EMA_STRUCTURE_ALIGNMENT' };

  if (type === 'MARKET') {
    if (agreement !== 4 || !fiveAligned) return { allow:false, reason:'MARKET_REQUIRES_4TF_ALIGNMENT' };
    if (!macdAligned) return { allow:false, reason:'MARKET_WAIT_MACD_CONFIRMATION' };
    if (!rsiDirectional) return { allow:false, reason:'MARKET_RSI_NOT_IN_DIRECTIONAL_ZONE' };
  } else if (type === 'STOP') {
    if (!fiveAligned) return { allow:false, reason:'STOP_WAIT_5M_BREAKOUT_ALIGNMENT' };
    if (!macdAligned) return { allow:false, reason:'STOP_WAIT_MACD_CONFIRMATION' };
    if (!rsiDirectional) return { allow:false, reason:'STOP_RSI_NOT_IN_DIRECTIONAL_ZONE' };
  } else if (type === 'LIMIT') {
    if (!rsiNotExtreme) return { allow:false, reason:'LIMIT_RSI_EXTREME' };
  }

  const grade = score >= 95 ? 'A+' : score >= 92 ? 'A' : 'A-';
  return {
    allow:true,
    reason:'QUALITY_GATE_PASSED',
    grade,
    evidence:{
      score,
      agreement,
      htfAligned,
      emaAligned,
      macdAligned,
      rsi:Number.isFinite(rsi) ? rsi : null,
      recommend5m:r5,
      recommend15m:r15,
      recommend1h:r60,
      recommend4h:r240,
    },
  };
}

async function createPolicyState(env) {
  const kv = env?.SIGNALS_KV;
  const active = await loadActiveSignals(kv);
  const activeByGroup = { forex:0, metal:0, energy:0 };
  for (const s of active) activeByGroup[s.group] = (activeByGroup[s.group] || 0) + 1;
  return {
    activeCount:active.length,
    activeByGroup,
    localCreated:0,
    lastSignalAt:Number(await kv?.get(LAST_NEW_SIGNAL_KEY) || 0),
    acceptedIds:new Set(),
    acceptedMeta:new Map(),
    rejectedIds:new Map(),
    rejectedSymbols:new Map(),
  };
}

function guardedKv(base, state) {
  if (!base) return base;
  return {
    get: (...args) => base.get(...args),
    list: (...args) => base.list(...args),
    delete: (...args) => base.delete(...args),
    async put(key, value, options) {
      if (String(key).startsWith('signal:')) {
        let s = null;
        try { s = JSON.parse(String(value)); } catch (_) {}
        const isCandidate = isActiveSignal(s) && !state.acceptedIds.has(s.id);
        if (isCandidate) {
          const existing = await base.get(key);
          if (!existing) {
            const decision = qualityDecision(s, state);
            if (!decision.allow) {
              state.rejectedIds.set(s.id, decision);
              state.rejectedSymbols.set(s.symbol, decision);
              return;
            }
            s.qualityGate = {
              version:'QUALITY_GATE_V212',
              grade:decision.grade,
              verdict:'APPROVED',
              reason:decision.reason,
              evidence:decision.evidence,
              cadencePolicy:{
                minGlobalSpacingMinutes:Math.round(CADENCE_POLICY.minGlobalSpacingMs/60000),
                maxNewPerScan:CADENCE_POLICY.maxNewPerScan,
                maxActiveTotal:CADENCE_POLICY.maxActiveTotal,
                maxActiveGroup:CADENCE_POLICY.maxActiveByGroup[s.group],
              },
            };
            value = JSON.stringify(s);
            state.acceptedIds.add(s.id);
            state.acceptedMeta.set(s.id, s.qualityGate);
            state.localCreated += 1;
            state.activeCount += 1;
            state.activeByGroup[s.group] = (state.activeByGroup[s.group] || 0) + 1;
            state.lastSignalAt = Date.now();
          }
        }
      }

      if (String(key).startsWith('active:')) {
        const id = String(value);
        if (state.rejectedIds.has(id)) return;
        if (state.acceptedIds.has(id)) {
          await base.put(LAST_NEW_SIGNAL_KEY, String(state.lastSignalAt), { expirationTtl:7*24*60*60 });
        }
      }
      return base.put(key, value, options);
    },
  };
}

function sanitizeScanResult(result, state) {
  if (!result || typeof result !== 'object') return result;
  const target = result.snapshot && typeof result.snapshot === 'object' ? result.snapshot : result;
  if (Array.isArray(target.analyses)) {
    for (const a of target.analyses) {
      const id = a?.tracker?.signalId;
      const rejected = id ? state.rejectedIds.get(id) : state.rejectedSymbols.get(a?.symbol);
      if (rejected && id && state.rejectedIds.has(id)) {
        a.status = 'WATCH';
        a.orderType = 'WATCH';
        a.reason = rejected.reason;
        a.tracker = {
          status:'QUALITY_FILTERED',
          duplicateBlocked:true,
          qualityReason:rejected.reason,
          retryAfterSec:rejected.retryAfterSec || null,
        };
      }
      if (id && state.acceptedMeta.has(id)) {
        a.qualityGate = state.acceptedMeta.get(id);
      }
    }
  }
  if (target.tracker && Array.isArray(target.tracker.events)) {
    target.tracker.events = target.tracker.events.filter(e => {
      const id = e?.signal?.id;
      return e?.type !== 'NEW_SIGNAL' || !state.rejectedIds.has(id);
    }).map(e => {
      const id = e?.signal?.id;
      if (id && state.acceptedMeta.has(id)) e.signal.qualityGate = state.acceptedMeta.get(id);
      return e;
    });
  }
  target.qualityPolicy = {
    version:'QUALITY_GATE_V212',
    minGlobalSpacingMinutes:Math.round(CADENCE_POLICY.minGlobalSpacingMs/60000),
    maxNewPerScan:CADENCE_POLICY.maxNewPerScan,
    maxActiveTotal:CADENCE_POLICY.maxActiveTotal,
    maxActiveByGroup:CADENCE_POLICY.maxActiveByGroup,
    minScore:CADENCE_POLICY.minScore,
    approvedNewSignals:state.acceptedIds.size,
    filteredCandidates:state.rejectedIds.size,
    note:'Technical score is a setup-quality score, not a win probability. New signals are rate-limited; existing signals keep being tracked every scan.',
  };
  return result;
}

async function trackerFetchWithPolicy(req, env, ctx, sanitize=true) {
  const state = await createPolicyState(env);
  const guardedEnv = { ...env, SIGNALS_KV:guardedKv(env?.SIGNALS_KV, state) };
  const response = await tracker.fetch(req, guardedEnv, ctx);
  if (!sanitize) return response;
  try {
    const body = await response.json();
    sanitizeScanResult(body, state);
    return json(body, response.status);
  } catch (_) {
    return response;
  }
}

async function augmentStatus(req, env, ctx, reconciliation) {
  const response = await tracker.fetch(req, env, ctx);
  try {
    const body = await response.json();
    const lastSignalAt = Number(await env?.SIGNALS_KV?.get(LAST_NEW_SIGNAL_KEY) || 0);
    body.gatewayVersion = GATEWAY_VERSION;
    body.appLatest = APP_RELEASE;
    body.activeSymbolReconciliation = reconciliation;
    body.signalCadencePolicy = {
      mode:'MODERATE_QUALITY_FIRST',
      minGlobalSpacingMinutes:Math.round(CADENCE_POLICY.minGlobalSpacingMs/60000),
      maxNewPerScan:CADENCE_POLICY.maxNewPerScan,
      maxActiveTotal:CADENCE_POLICY.maxActiveTotal,
      maxActiveByGroup:CADENCE_POLICY.maxActiveByGroup,
      minScore:CADENCE_POLICY.minScore,
      lastNewSignalAt:lastSignalAt ? new Date(lastSignalAt).toISOString() : null,
      qualityRules:{
        MARKET:'score>=93, 4TF alignment, 15m/1h/4h strength, EMA+MACD confirmation, directional RSI',
        LIMIT:'score>=88, aligned 15m/1h/4h trend, EMA structure, non-extreme RSI; 5m pullback may differ',
        STOP:'score>=90, 5m+15m+1h+4h direction, EMA+MACD confirmation, directional RSI',
      },
      scoreMeaning:'Technical setup quality only; not win probability.',
    };
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
  if (url.pathname === '/run-now' || url.pathname === '/latest-scan') {
    return trackerFetchWithPolicy(req, env, ctx, true);
  }
  return tracker.fetch(req, env, ctx);
}

async function scheduled(_event, env, ctx) {
  await reconcileLegacyActiveSignals(env);
  const groups = ['forex','metal','energy'];
  const slot = Math.floor(Date.now() / (5*60*1000)) % groups.length;
  const rotated = [...groups.slice(slot), ...groups.slice(0, slot)];
  ctx.waitUntil((async()=>{
    for (const group of rotated) {
      try {
        const req = new Request(`https://signalhub.internal/run-now?group=${group}`);
        await trackerFetchWithPolicy(req, env, ctx, false);
      } catch (_) {}
    }
  })());
}

export default {
  fetch: handle,
  scheduled,
};