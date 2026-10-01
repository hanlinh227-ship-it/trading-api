const ROUTE = '/market/forex/quote';
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
  if (url.pathname !== ROUTE) return null;
  if (request.method !== 'GET') return json({ ok: false, error: 'METHOD_NOT_ALLOWED', readOnly: true }, 405);

  const symbol = normalizeSymbol(url.searchParams.get('symbol'));
  if (!symbol) return json({ ok: false, error: 'UNSUPPORTED_FOREX_SYMBOL', readOnly: true }, 400);
  const apiKey = String(env.TWELVE_DATA_API_KEY || '').trim();
  if (!apiKey) return json({ ok: false, error: 'TWELVE_DATA_CONFIGURATION_MISSING', readOnly: true }, 503);

  const providerSymbol = `${symbol.slice(0, 3)}/${symbol.slice(3)}`;
  const upstreamUrl = new URL('https://api.twelvedata.com/quote');
  upstreamUrl.searchParams.set('symbol', providerSymbol);
  upstreamUrl.searchParams.set('apikey', apiKey);
  upstreamUrl.searchParams.set('format', 'JSON');

  const fetchImpl = options.fetchImpl || fetch;
  const now = options.now || Date.now;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  let response;
  try {
    response = await fetchImpl(upstreamUrl, { method: 'GET', signal: controller.signal, headers: { accept: 'application/json' } });
  } catch {
    return json({ ok: false, error: 'TWELVE_DATA_UNAVAILABLE', readOnly: true }, 503);
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    return json({ ok: false, error: response.status === 429 ? 'TWELVE_DATA_RATE_LIMITED' : 'TWELVE_DATA_UPSTREAM_ERROR', readOnly: true }, 503);
  }

  let data;
  try { data = await response.json(); } catch { return json({ ok: false, error: 'TWELVE_DATA_INVALID_RESPONSE', readOnly: true }, 502); }
  if (!data || data.status === 'error' || normalizeSymbol(data.symbol) !== symbol) {
    return json({ ok: false, error: 'TWELVE_DATA_SYMBOL_OR_RESPONSE_MISMATCH', readOnly: true }, 502);
  }

  const price = Number(data.close);
  const sourceMs = parseTimestamp(data.timestamp);
  if (!(price > 0) || !Number.isFinite(sourceMs)) {
    return json({ ok: false, error: 'TWELVE_DATA_PRICE_OR_TIMESTAMP_MISSING', readOnly: true }, 502);
  }
  const fetchedMs = now();
  const ageMs = fetchedMs - sourceMs;
  if (ageMs < -2_000 || ageMs > MAX_QUOTE_AGE_MS) {
    return json({
      ok: false,
      error: 'DATA_BLOCK',
      readOnly: true,
      source: 'TWELVE_DATA',
      symbol,
      sourceTimestamp: new Date(sourceMs).toISOString(),
      ageMs,
      maxAgeMs: MAX_QUOTE_AGE_MS,
    }, 503);
  }

  return json({
    ok: true,
    readOnly: true,
    source: 'TWELVE_DATA',
    dataType: 'REFERENCE_PRICE',
    executionAuthoritative: false,
    symbol,
    providerSymbol,
    price,
    sourceTimestamp: new Date(sourceMs).toISOString(),
    receivedAt: new Date(fetchedMs).toISOString(),
    ageMs: Math.max(0, ageMs),
  });
}

export const TWELVE_DATA_FOREX_PAIRS = Object.freeze([...FOREX_PAIRS]);
