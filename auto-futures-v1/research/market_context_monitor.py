import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/trading/trading-api/auto-futures-v1')
STATE = ROOT / 'state'
SNAPSHOT = STATE / 'market_snapshot.json'
POSITIONS = STATE / 'paper_positions.json'
OUT = STATE / 'market_context.json'
BASE = 'https://fapi.binance.com'
CACHE_SECONDS = 20


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def get(path, params=None):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'AUTO-FUTURES-V6-CONTEXT'})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


def age_seconds(payload):
    try:
        ts = datetime.fromisoformat(str(payload.get('generated_at')).replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return 10**9


def pct(a, b):
    try:
        a, b = float(a), float(b)
        return ((a / b) - 1.0) * 100.0 if b else 0.0
    except Exception:
        return 0.0


def symbol_context(symbol):
    mark = get('/fapi/v1/premiumIndex', {'symbol': symbol})
    oi = get('/fapi/v1/openInterest', {'symbol': symbol})
    ticker = get('/fapi/v1/ticker/24hr', {'symbol': symbol})
    book = get('/fapi/v1/ticker/bookTicker', {'symbol': symbol})
    klines = get('/fapi/v1/klines', {'symbol': symbol, 'interval': '5m', 'limit': 24})

    closes = [float(x[4]) for x in klines]
    vols = [float(x[5]) for x in klines]
    ret_15m = pct(closes[-1], closes[-4]) if len(closes) >= 4 else 0.0
    ret_60m = pct(closes[-1], closes[-13]) if len(closes) >= 13 else 0.0
    avg_vol = sum(vols[:-1]) / max(1, len(vols) - 1) if vols else 0.0
    vol_impulse = (vols[-1] / avg_vol) if avg_vol > 0 and vols else 0.0
    bid = float(book.get('bidPrice', 0) or 0)
    ask = float(book.get('askPrice', 0) or 0)
    mid = (bid + ask) / 2 if bid and ask else 0.0
    spread_bps = ((ask - bid) / mid * 10000.0) if mid > 0 else None

    return {
        'symbol': symbol,
        'mark_price': float(mark.get('markPrice', 0) or 0),
        'index_price': float(mark.get('indexPrice', 0) or 0),
        'funding_rate': float(mark.get('lastFundingRate', 0) or 0),
        'next_funding_time': mark.get('nextFundingTime'),
        'open_interest': float(oi.get('openInterest', 0) or 0),
        'price_change_24h_pct': float(ticker.get('priceChangePercent', 0) or 0),
        'quote_volume_24h': float(ticker.get('quoteVolume', 0) or 0),
        'spread_bps': round(spread_bps, 4) if spread_bps is not None else None,
        'return_15m_pct': round(ret_15m, 5),
        'return_60m_pct': round(ret_60m, 5),
        'volume_impulse_5m': round(vol_impulse, 4),
    }


def main(force=False):
    previous = load(OUT, {})
    if not force and previous and age_seconds(previous) < CACHE_SECONDS:
        print('MARKET CONTEXT CACHE HIT', round(age_seconds(previous), 1), 'sec')
        return

    snapshot = load(SNAPSHOT, {'setups': []})
    positions = load(POSITIONS, {'positions': []})
    symbols = []
    for p in positions.get('positions', []):
        if p.get('status') == 'OPEN' and p.get('symbol'):
            symbols.append(p['symbol'])
    for s in snapshot.get('ai_candidates') or snapshot.get('setups') or []:
        if s.get('symbol'):
            symbols.append(s['symbol'])
    symbols = list(dict.fromkeys(symbols))[:12]

    data, errors = {}, {}
    for symbol in symbols:
        try:
            data[symbol] = symbol_context(symbol)
        except Exception as exc:
            errors[symbol] = repr(exc)

    payload = {
        'generated_at': now_iso(),
        'cache_seconds': CACHE_SECONDS,
        'source': 'BINANCE_USDM_PUBLIC_MARKET_DATA',
        'symbols': data,
        'errors': errors,
        'policy': {
            'refresh_continuously': True,
            'no_ai_token_cost': True,
            'use_for_entry_and_position_reasoning': True,
            'external_news_requires_separate_verified_feed': True,
        },
    }
    STATE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print('MARKET CONTEXT REFRESHED:', len(data), 'symbols | errors:', len(errors))


if __name__ == '__main__':
    main()
