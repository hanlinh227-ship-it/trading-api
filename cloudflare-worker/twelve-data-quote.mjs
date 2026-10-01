const ROUTES = new Set(['/market/forex/quote', '/market/forex/quotes']);
const MAX_QUOTE_AGE_MS = 65_000;
const FOREX_PAIRS = new Set([
  'EURUSD','GBPUSD','AUDUSD','NZDUSD','USDJPY','USDCHF','USDCAD',
  'EURGBP','EURJPY','EURCHF','EURAUD','EURCAD','EURNZD',
  'GBPJPY','GBPCHF','GBPAUD','GBPCAD','GBPNZD',
  'AUDJPY','AUDCHF','AUDCAD','AUDNZD',
  'NZDJPY','NZDCHF','NZDCAD','CADJPY','CADCHF','CHFJPY',
]);

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
});

function normalizeSymbol(value) {
  const symbol = String(value || '').trim().toUpperCase().replace(/[\s/]/g, '');
  return FOREX_PAIRS.has(symbol) ? symbol : '';
}

function parseTimestamp(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value < 1e12 ? value * 1000 : value;
  if (typeof value === 'string' && value.trim()) {
    const numeric = Number(value);
    if (Number.isFinite(numeric) && numeric > 0) return numeric < 1e12 ? numeric * 1000 : numeric;
  }
  return NaN;
}

export async function handleTwelveDataReferenceQuote(request, env = {}, options = {}) {
  const url = new URL(request.url);
  if (!ROUTES.has(url.pathname)) return null;
  if (request.method !== 'GET') return json({ ok: false, error: 'METHOD_NOT_ALLOWED', readOnly: true }, 405);

  const apiKey = String(env.TWELVE_DATA_API_KEY || '').trim();
  if (!apiKey) return json({ ok: false, error: 'TWELVE_DATA_CONFIGURATION_MISSING', readOnly: true }, 503);
  const fetchImpl = options.fetchImpl || fetch;
  const now = options.now || Date.now;
  const readQuote = async symbol => {
    const providerSymbol = `${symbol.slice(0, 3)}/${symbol.slice(3)}`;
    const upstreamUrl = new URL('https://api.twelvedata.com/quote');
    upstreamUrl.searchParams.set('symbol', providerSymbol);
    upstreamUrl.searchParams.set('apikey', apiKey);
    upstreamUrl.searchParams.set('format', 'JSON');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8_000);
    let response;
    try {
      response = await fetchImpl(upstreamUrl, { method: 'GET', signal: controller.signal, headers: { accept: 'application/json' } });
    } catch {
      return {ok:false,symbol,error:'TWELVE_DATA_UNAVAILABLE'};
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) return {ok:false,symbol,error:response.status===429?'TWELVE_DATA_RATE_LIMITED':'TWELVE_DATA_UPSTREAM_ERROR'};
    let data;
    try { data = await response.json(); } catch { return {ok:false,symbol,error:'TWELVE_DATA_INVALID_RESPONSE'}; }
    if (!data || data.status === 'error' || normalizeSymbol(data.symbol) !== symbol) return {ok:false,symbol,error:'TWELVE_DATA_SYMBOL_OR_RESPONSE_MISMATCH'};
    const price = Number(data.close), sourceMs = parseTimestamp(data.timestamp), fetchedMs = now();
    if (!(price > 0) || !Number.isFinite(sourceMs)) return {ok:false,symbol,error:'TWELVE_DATA_PRICE_OR_TIMESTAMP_MISSING'};
    const ageMs = fetchedMs - sourceMs;
    if (ageMs < -2_000 || ageMs > MAX_QUOTE_AGE_MS) {
      return {ok:false,symbol,error:'DATA_BLOCK',sourceTimestamp:new Date(sourceMs).toISOString(),ageMs,maxAgeMs:MAX_QUOTE_AGE_MS};
    }
    return {ok:true,symbol,providerSymbol,price,sourceTimestamp:new Date(sourceMs).toISOString(),receivedAt:new Date(fetchedMs).toISOString(),ageMs:Math.max(0,ageMs)};
  };

  if (url.pathname === '/market/forex/quotes') {
    const results = await Promise.all(TWELVE_DATA_FOREX_PAIRS.map(readQuote));
    const quotes = results.filter(result => result.ok).map(({ok,...quote})=>quote);
    const blocked = results.filter(result => !result.ok).map(({ok,...item})=>item);
    return json({ok:blocked.length===0,readOnly:true,source:'TWELVE_DATA',dataType:'REFERENCE_PRICE_BATCH',executionAuthoritative:false,requested:TWELVE_DATA_FOREX_PAIRS.length,received:quotes.length,complete:blocked.length===0,quotes,blocked});
  }

  const symbol = normalizeSymbol(url.searchParams.get('symbol'));
  if (!symbol) return json({ ok: false, error: 'UNSUPPORTED_FOREX_SYMBOL', readOnly: true }, 400);
  const result = await readQuote(symbol);
  if (!result.ok) return json({ok:false,readOnly:true,source:'TWELVE_DATA',...Object.fromEntries(Object.entries(result).filter(([key])=>key!=='ok'))},result.error==='DATA_BLOCK'?503:502);
  return json({ok:true,readOnly:true,source:'TWELVE_DATA',dataType:'REFERENCE_PRICE',executionAuthoritative:false,...Object.fromEntries(Object.entries(result).filter(([key])=>key!=='ok'))});
}

export const TWELVE_DATA_FOREX_PAIRS = Object.freeze([...FOREX_PAIRS]);
