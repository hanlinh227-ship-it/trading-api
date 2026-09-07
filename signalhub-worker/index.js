const VERSION = 'SIGNALHUB-FOREX-1.1.0';
const SERVICE = 'SignalHub Forex / Metals / Energy';
const TV_FOREX = 'https://scanner.tradingview.com/forex/scan';
const TV_CFD = 'https://scanner.tradingview.com/cfd/scan';

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
  'EMA20|15','EMA50|15','EMA200|15','ATR|15'
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

function canonical(ticker, name) {
  if (ticker === 'TVC:SILVER') return 'XAGUSD';
  if (ticker === 'FX:UKOIL') return 'UKOIL';
  return String(name || ticker.split(':').pop() || '').toUpperCase();
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
        'user-agent':'SignalHub-Worker/1.1',
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

function buildAnalysis(row, group, receivedAt) {
  const d = Array.isArray(row?.d) ? row.d : [];
  if (d.length < COLUMNS.length) return null;
  const [name, close, change, all, r5, r15, r60, r240, rsi15, macd, macdSignal, ema20, ema50, ema200, atr15] = d;
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

  const mult = group === 'forex' ? 1.35 : group === 'metal' ? 1.20 : 1.30;
  const risk = atr * mult;
  const entry = price;
  const sl = direction > 0 ? entry-risk : entry+risk;
  const tp = direction > 0 ? entry+risk*2.2 : entry-risk*2.2;
  const symbol = canonical(row.s, name);

  return {
    symbol,
    side,
    status: actionable ? 'MARKET_SIGNAL' : 'WATCH',
    score,
    reason: actionable ? 'MTF_ALIGNMENT_CONFIRMED' : 'WAIT_FOR_STRONGER_ALIGNMENT',
    planned: {
      entry: round(entry, symbol.includes('JPY') ? 3 : symbol === 'XAUUSD' ? 2 : symbol === 'XAGUSD' || symbol === 'UKOIL' ? 3 : 5),
      sl: round(sl, symbol.includes('JPY') ? 3 : symbol === 'XAUUSD' ? 2 : symbol === 'XAGUSD' || symbol === 'UKOIL' ? 3 : 5),
      tp: round(tp, symbol.includes('JPY') ? 3 : symbol === 'XAUUSD' ? 2 : symbol === 'XAGUSD' || symbol === 'UKOIL' ? 3 : 5),
      targetRR: 2.2,
    },
    analysisQuote: {
      price: round(price, 6),
      source: `TRADINGVIEW:${String(row.s||'').split(':')[0] || 'SCAN'}`,
      fresh: true,
      receivedAt,
      freshnessBasis: 'LIVE_SCAN_RESPONSE_NO_PROVIDER_TIMESTAMP',
    },
    technical: {
      recommend5m: round(vals[0],3), recommend15m: round(vals[1],3),
      recommend1h: round(vals[2],3), recommend4h: round(vals[3],3),
      rsi15: rsi === null ? null : round(rsi,2),
      macdAligned, emaAligned, atr15: round(atr,6), changePct: num(change),
    },
  };
}

async function scan(group) {
  const started = Date.now();
  const receivedAt = new Date().toISOString();
  try {
    const rows = await tvScan(group);
    const analyses = rows.map(r => buildAnalysis(r,group,receivedAt)).filter(Boolean)
      .sort((a,b) => b.score-a.score);
    const actionable = analyses.filter(x => x.status === 'MARKET_SIGNAL');
    const display = actionable.length ? [...actionable, ...analyses.filter(x=>x.status!=='MARKET_SIGNAL')].slice(0,5) : analyses.slice(0,5);
    const marketClosed = rows.length === 0;
    return {
      ok:true,
      version:VERSION,
      group,
      status: marketClosed ? 'MARKET_CLOSED_OR_NO_DATA' : 'OK',
      scanId:`${group}-${Date.now()}`,
      scannedAt:new Date().toISOString(),
      source:'TRADINGVIEW_SCANNER',
      sourceRows:rows.length,
      requested:GROUPS[group].tickers.length,
      broadOk:rows.length,
      deepOk:analyses.length,
      deepRequested:rows.length,
      elapsedMs:Date.now()-started,
      analyses:display,
      actionableCount:actionable.length,
      note:'Signals are technical setup alerts, not guaranteed outcomes. Broker execution prices can differ.',
    };
  } catch (e) {
    return {
      ok:false,
      version:VERSION,
      group,
      status:'SOURCE_UNAVAILABLE',
      scanId:`${group}-${Date.now()}`,
      scannedAt:new Date().toISOString(),
      analyses:[],
      error:String(e?.message||e),
      elapsedMs:Date.now()-started,
    };
  }
}

async function handle(req) {
  const u = new URL(req.url);
  if (req.method === 'OPTIONS') return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-methods':'GET,OPTIONS'}});
  if (req.method !== 'GET') return json({ok:false,error:'GET_ONLY'},405);

  if (u.pathname === '/' || u.pathname === '/status') {
    return json({
      ok:true, version:VERSION, service:SERVICE,
      independentFromBybit:true,
      dataSource:'TRADINGVIEW_SCANNER',
      groups:Object.keys(GROUPS),
      symbols:{forex:FOREX,metal:['XAUUSD','XAGUSD'],energy:['UKOIL']},
      staleFallback:false,
      generatedAt:new Date().toISOString(),
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
    const result=await scan(g);
    // Keep /latest-scan compatible with the Android parser while still scanning live.
    if (u.pathname === '/latest-scan') return json({ok:result.ok,group:g,snapshot:result},result.ok?200:503);
    return json(result,result.ok?200:503);
  }
  if (u.pathname === '/books') return json({ok:true,forex:{marketActive:[]},metal:{marketActive:[]},energy:{marketActive:[]},note:'Signal-only service; no execution book.'});
  if (u.pathname === '/shadow') return json({ok:true,rows:[],note:'Shadow history not enabled on stateless worker.'});
  return json({ok:false,error:'NOT_FOUND',endpoints:['/status','/latest-scan?group=forex|metal|energy','/run-now?group=forex|metal|energy','/symbols?group=forex|metal|energy','/books','/shadow']},404);
}

export default { fetch: handle };
