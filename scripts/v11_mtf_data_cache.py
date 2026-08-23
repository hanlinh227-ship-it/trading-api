#!/usr/bin/env python3
# V11 MTF exact historical data cache (isolated research component).
# Fetches exact source candles once and caches them immutably.
# Cache key includes symbol/market/exact instrument/provider/base timeframe/start/end/content hash.
# Stale or mismatched cache entries are rejected and refetched.
from __future__ import annotations
import hashlib
import json
import lzma
import math
import os
import re
import struct
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / 'cloudflare-worker/v11/symbol-catalog.js'
DEFAULT_CACHE_DIR = ROOT / 'data/v11_mtf_cache'
CACHE_VERSION = 'V11-MTF-CACHE-V1'
USER_AGENT = 'Mozilla/5.0 V11-MTF-Cache/1.0'
YAHOO_INDEX = {'NAS100': '^NDX', 'US30': '^DJI', 'US500': '^GSPC', 'DEX': '^GDAXI', 'JP225': '^N225'}
DUKAS_INSTRUMENT = {'XAUUSD': 'XAUUSD', 'XAGUSD': 'XAGUSD'}
DUKAS_BOUNDS = {'XAUUSD': (10.0, 100000.0), 'XAGUSD': (0.1, 10000.0)}
CACHE_TF = {'forex': 'h1', 'crypto': 'm5', 'metal': 'h1', 'index': 'h1'}

def safe_float(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def load_catalog():
    text = CATALOG_PATH.read_text(encoding='utf-8')
    cats = {}
    for m in ('forex', 'crypto', 'metal', 'index'):
        z = re.search(rf'{m}:Object\.freeze\(\[(.*?)\]\)', text, re.S)
        if not z:
            raise RuntimeError('catalog parse ' + m)
        cats[m] = re.findall(r"'([^']+)'", z.group(1))
    total = sum(len(v) for v in cats.values())
    if total != 95:
        raise RuntimeError('catalog count ' + str(total))
    return cats

def market_for_symbol(symbol):
    s = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    for m, rows in load_catalog().items():
        if s in rows:
            return m
    return None

def get_json(url, timeout=45, retries=4):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(0.6 * (n + 1))
    raise RuntimeError('HTTP_FAIL ' + str(last))

def rawget(url, timeout=40, retries=3):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/octet-stream,*/*'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b''
            last = e
        except Exception as e:
            last = e
        time.sleep(0.45 * (n + 1))
    raise RuntimeError('HTTP_FAIL ' + str(last))

def yahoo_h1(symbol, market, start_ts, end_ts):
    s = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    if market == 'forex':
        ticker = {'USDJPY': 'JPY=X', 'USDCHF': 'CHF=X', 'USDCAD': 'CAD=X'}.get(s, s + '=X')
        instrument = 'FOREX:' + s
    elif market == 'metal':
        ticker = s + '=X'
        instrument = 'SPOT:' + s
    elif market == 'index':
        ticker = YAHOO_INDEX[s]
        instrument = 'CASH_IDX:' + s
    else:
        raise RuntimeError('unsupported market ' + market)
    q = urllib.parse.urlencode({'period1': start_ts - 3 * 86400, 'period2': end_ts + 3600, 'interval': '1h', 'includePrePost': 'true', 'events': 'div,splits'})
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + urllib.parse.quote(ticker, safe='^=') + '?' + q
    j = get_json(url)
    res = ((j.get('chart') or {}).get('result') or [])
    if not res:
        raise RuntimeError('YAHOO_EMPTY')
    r = res[0]
    ts = r.get('timestamp') or []
    qd = ((r.get('indicators') or {}).get('quote') or [{}])[0]
    O, H, L, C, V = [qd.get(k) or [] for k in ('open', 'high', 'low', 'close', 'volume')]
    rows = []
    for i, t0 in enumerate(ts):
        t0 = int(t0)
        if not (start_ts <= t0 <= end_ts):
            continue
        vals = [safe_float(a[i]) if i < len(a) else None for a in (O, H, L, C)]
        if None in vals:
            continue
        vol = safe_float(V[i]) if i < len(V) else 0.0
        rows.append([t0, *vals, vol or 0.0])
    if not rows:
        raise RuntimeError('YAHOO_EMPTY')
    return rows, 'Yahoo Finance H1', True, instrument

def binance_m5(symbol, start_ts, end_ts):
    s = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    out = []
    cur = start_ts * 1000
    end = end_ts * 1000
    while cur <= end:
        q = urllib.parse.urlencode({'symbol': s, 'interval': '5m', 'startTime': cur, 'endTime': end, 'limit': 1000})
        j = get_json('https://api.binance.com/api/v3/klines?' + q, timeout=30, retries=3)
        if not isinstance(j, list) or not j:
            break
        for x in j:
            t = int(x[0]) // 1000
            out.append([t, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
        nxt = int(j[-1][0]) + 300000
        if nxt <= cur:
            break
        cur = nxt
        if len(j) < 1000:
            break
        time.sleep(0.02)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError('BINANCE_M5_EMPTY')
    return [d[k] for k in sorted(d)], 'Binance Spot M5', True, 'SPOT:' + s

def bybit_m5(symbol, start_ts, end_ts):
    s = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    out = []
    cursor = end_ts * 1000
    start = start_ts * 1000
    guard = 0
    while cursor >= start and guard < 24:
        guard += 1
        q = urllib.parse.urlencode({'category': 'spot', 'symbol': s, 'interval': '5', 'start': start, 'end': cursor, 'limit': 1000})
        j = get_json('https://api.bybit.com/v5/market/kline?' + q, timeout=30, retries=2)
        arr = ((j.get('result') or {}).get('list') or []) if isinstance(j, dict) else []
        if not arr:
            break
        ts = []
        for x in arr:
            t = int(x[0]) // 1000
            ts.append(t)
            out.append([t, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
        nxt = min(ts) * 1000 - 1
        if nxt >= cursor:
            break
        cursor = nxt
        time.sleep(0.02)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError('BYBIT_M5_EMPTY')
    return [d[k] for k in sorted(d)], 'Bybit Spot M5', True, 'SPOT:' + s

def _month_floor(dt):
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)

def _next_month(dt):
    return (dt.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def _decode_dukas_record(symbol, base_ts, rec):
    off, p1, p2, p3, p4, vol = rec
    scale = 1000.0
    o = p1 / scale
    candidates = [(o, p4 / scale, p3 / scale, p2 / scale), (o, p2 / scale, p3 / scale, p4 / scale)]
    lo, hi = DUKAS_BOUNDS[symbol]
    for oo, hh, ll, cc in candidates:
        if not all(math.isfinite(v) and lo <= v <= hi for v in (oo, hh, ll, cc)):
            continue
        if ll <= min(oo, cc) <= max(oo, cc) <= hh and hh >= ll:
            t = int(base_ts + int(off))
            return [t, oo, hh, ll, cc, float(vol) if math.isfinite(float(vol)) else 0.0]
    return None

def dukascopy_h1(symbol, start_ts, end_ts):
    s = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    inst = DUKAS_INSTRUMENT[s]
    cur = _month_floor(datetime.fromtimestamp(start_ts, timezone.utc))
    end_dt = datetime.fromtimestamp(end_ts, timezone.utc)
    out = []
    while cur <= end_dt:
        month0 = cur.month - 1
        url = f'https://datafeed.dukascopy.com/datafeed/{inst}/{cur.year}/{month0:02d}/BID_candles_hour_1.bi5'
        blob = rawget(url)
        if blob:
            try:
                raw = lzma.decompress(blob)
            except Exception as e:
                raise RuntimeError(f'DUKAS_LZMA {inst} {cur.date()} {e}')
            usable = len(raw) - (len(raw) % 24)
            if usable <= 0:
                raise RuntimeError(f'DUKAS_BAD_RECORD_SIZE {inst} {cur.date()}')
            base_ts = int(cur.timestamp())
            for rec in struct.iter_unpack('>IIIIIf', raw[:usable]):
                row = _decode_dukas_record(s, base_ts, rec)
                if row and start_ts <= row[0] <= end_ts:
                    out.append(row)
        cur = _next_month(cur)
    d = {r[0]: r for r in out}
    rows = [d[k] for k in sorted(d)]
    if not rows:
        raise RuntimeError('DUKAS_EMPTY')
    return rows, f'Dukascopy {inst} BID H1', True, 'BID:' + inst

def provider_spec(symbol, market):
    s = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    if market == 'crypto':
        return {'base_tf': 'm5', 'provider': 'binance_spot_m5', 'instrument': 'SPOT:' + s}
    if market == 'forex':
        return {'base_tf': 'h1', 'provider': 'yahoo_fx_h1', 'instrument': 'FOREX:' + s}
    if market == 'metal':
        return {'base_tf': 'h1', 'provider': 'dukascopy_bid_h1', 'instrument': 'BID:' + s}
    if market == 'index':
        return {'base_tf': 'h1', 'provider': 'yahoo_cash_idx_h1', 'instrument': 'CASH_IDX:' + s}
    raise RuntimeError('unknown market ' + market)

def fetch_raw(symbol, market, start_ts, end_ts):
    if market == 'crypto':
        try:
            rows, src, exact, inst = binance_m5(symbol, start_ts, end_ts)
            return rows, src, exact, inst, provider_spec(symbol, market)
        except Exception:
            rows, src, exact, inst = bybit_m5(symbol, start_ts, end_ts)
            return rows, src, exact, inst, provider_spec(symbol, market)
    if market == 'metal':
        rows, src, exact, inst = dukascopy_h1(symbol, start_ts, end_ts)
        return rows, src, exact, inst, provider_spec(symbol, market)
    rows, src, exact, inst = yahoo_h1(symbol, market, start_ts, end_ts)
    return rows, src, exact, inst, provider_spec(symbol, market)

def compute_data_hash(rows):
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def _req_key(symbol, market, instrument, provider, base_tf, start_ts, end_ts):
    return '|'.join([CACHE_VERSION, str(symbol).upper(), str(market), str(instrument), str(provider), str(base_tf), str(int(start_ts)), str(int(end_ts))])

def _req_key_with_hash(symbol, market, instrument, provider, base_tf, start_ts, end_ts, content_hash):
    return _req_key(symbol, market, instrument, provider, base_tf, start_ts, end_ts) + '|content=' + content_hash

def _cache_path(cache_dir, key):
    return Path(cache_dir) / (hashlib.sha256(key.encode()).hexdigest() + '.json')

def load_cache(cache_dir, symbol, market, start_ts, end_ts):
    spec = provider_spec(symbol, market)
    key = _req_key(symbol, market, spec['instrument'], spec['provider'], spec['base_tf'], start_ts, end_ts)
    p = _cache_path(cache_dir, key)
    if not p.exists():
        return None, spec, key
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
        expected = {
            'cacheVersion': CACHE_VERSION,
            'symbol': str(symbol).upper(),
            'market': market,
            'instrument': spec['instrument'],
            'provider': spec['provider'],
            'baseTimeframe': spec['base_tf'],
            'startTs': int(start_ts),
            'endTs': int(end_ts),
        }
        for f, v in expected.items():
            if obj.get(f) != v:
                raise ValueError(f'CACHE_MISMATCH {f}')
        rows = obj.get('rows')
        if not isinstance(rows, list):
            raise ValueError('CACHE_NO_ROWS')
        h = compute_data_hash(rows)
        if h != obj.get('contentHash'):
            raise ValueError('CACHE_CONTENT_HASH_MISMATCH')
        if obj.get('cacheKey') != _req_key_with_hash(symbol, market, spec['instrument'], spec['provider'], spec['base_tf'], start_ts, end_ts, h):
            raise ValueError('CACHE_KEY_MISMATCH')
        return {'rows': rows, 'source': obj.get('source'), 'exact': bool(obj.get('exact')), 'instrument': spec['instrument'], 'cached': True}, spec, key
    except Exception:
        return None, spec, key

def save_cache(cache_dir, key, symbol, market, spec, rows, source, exact, start_ts, end_ts):
    content_hash = compute_data_hash(rows)
    obj = {
        'cacheVersion': CACHE_VERSION,
        'cacheKey': _req_key_with_hash(symbol, market, spec['instrument'], spec['provider'], spec['base_tf'], start_ts, end_ts, content_hash),
        'symbol': str(symbol).upper(),
        'market': market,
        'instrument': spec['instrument'],
        'provider': spec['provider'],
        'baseTimeframe': spec['base_tf'],
        'startTs': int(start_ts),
        'endTs': int(end_ts),
        'source': source,
        'exact': bool(exact),
        'contentHash': content_hash,
        'rows': rows,
    }
    p = _cache_path(cache_dir, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, separators=(',', ':')), encoding='utf-8')
    os.replace(tmp, p)

def feature_schema_hash(schema):
    return hashlib.sha256(('V11-MTF-FEATURE-SCHEMA|' + schema).encode()).hexdigest()[:16]

def _feature_path(cache_dir, symbol, data_hash, schema_hash):
    key = '|'.join([CACHE_VERSION, 'FEAT', str(symbol).upper(), data_hash, schema_hash])
    return Path(cache_dir) / ('feat_' + hashlib.sha256(key.encode()).hexdigest() + '.json')

def load_feature(cache_dir, symbol, data_hash, schema_hash):
    p = _feature_path(cache_dir, symbol, data_hash, schema_hash)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
        if obj.get('cacheVersion') != CACHE_VERSION or obj.get('symbol') != str(symbol).upper() or obj.get('dataHash') != data_hash or obj.get('schemaHash') != schema_hash:
            return None
        return obj.get('features')
    except Exception:
        return None

def save_feature(cache_dir, symbol, data_hash, schema_hash, features):
    p = _feature_path(cache_dir, symbol, data_hash, schema_hash)
    p.parent.mkdir(parents=True, exist_ok=True)
    obj = {'cacheVersion': CACHE_VERSION, 'symbol': str(symbol).upper(), 'dataHash': data_hash, 'schemaHash': schema_hash, 'features': features}
    p.write_text(json.dumps(obj, separators=(',', ':')), encoding='utf-8')

def parse_dt(v):
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    s = str(v).replace('Z', '+00:00').replace(' ', 'T')
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol')
    ap.add_argument('--market')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--days', type=int, default=400)
    ap.add_argument('--cache-dir', default=str(DEFAULT_CACHE_DIR))
    ap.add_argument('--force-refresh', action='store_true')
    args = ap.parse_args(argv)
    end = parse_dt(args.end) if args.end else datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = parse_dt(args.start) if args.start else end - timedelta(days=args.days)
    start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cats = load_catalog()
    if args.symbol:
        s = re.sub(r'[^A-Z0-9]', '', args.symbol.upper())
        m = args.market or market_for_symbol(s)
        if not m:
            raise SystemExit('UNKNOWN_SYMBOL ' + s)
        items = [(s, m)]
    else:
        items = [(s, m) for m in ('forex', 'crypto', 'metal', 'index') for s in cats[m]]
    counts = {}
    for symbol, market in items:
        entry, spec, key = load_cache(cache_dir, symbol, market, start_ts, end_ts)
        if entry and not args.force_refresh:
            rows = entry['rows']
            counts[symbol] = len(rows)
            print('CACHE_HIT', market, symbol, len(rows), entry['source'], flush=True)
        else:
            try:
                rows, source, exact, instrument, spec = fetch_raw(symbol, market, start_ts, end_ts)
                save_cache(cache_dir, key, symbol, market, spec, rows, source, exact, start_ts, end_ts)
                counts[symbol] = len(rows)
                print('FETCH_CACHE', market, symbol, len(rows), source, flush=True)
            except Exception as e:
                counts[symbol] = 0
                print('FETCH_FAIL', market, symbol, str(e)[:200], flush=True)
    print('SUMMARY', json.dumps({'fetched': sum(1 for v in counts.values() if v), 'failed': sum(1 for v in counts.values() if not v), 'total': len(items)}, separators=(',', ':')), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
