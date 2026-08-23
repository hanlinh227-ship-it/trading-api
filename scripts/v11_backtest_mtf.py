#!/usr/bin/env python3
'''V11 hierarchical multi-timeframe research/backtest engine (research-only).'''
from __future__ import annotations

import bisect
import concurrent.futures as cf
import json
import lzma
import math
import os
import re
import statistics
import struct
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'cloudflare-worker/v11/symbol-catalog.js'
OUT = ROOT / 'data/v11_mtf_backtest_4m.json'
GATE = ROOT / 'data/v11_mtf_backtest_gate.json'
REGISTRY = ROOT / 'data/v11_mtf_learning_registry.json'

VERSION = 'V11-MTF-ENGINE-R4'
REQUIRED_WR = 80.0
ALLOWED_RR = (1.0, 2.0)
MAX_HOLD_BARS = 36
RETEST_BARS = 4
COOLDOWN_BARS = 6
COST_R = 0.05
EVAL_DAYS = int(os.environ.get('V11_EVAL_DAYS', '122'))
VAL_DAYS = int(os.environ.get('V11_VAL_DAYS', '31'))
DEV_DAYS = int(os.environ.get('V11_DEV_DAYS', '61'))
HISTORY_DAYS = int(os.environ.get('V11_HISTORY_DAYS', '420'))
MAX_WORKERS = int(os.environ.get('V11_FETCH_WORKERS', '8'))

ENTRY_MODES = ('CLOSE', 'RETEST', 'LIMIT_FVG')
STOP_MODES = ('STRUCTURE', 'STRUCTURE_ATR')
RULES = ('BOTH', 'ALIGNED2', 'ALIGNED3', 'RS', 'BREADTH', 'REGIME')
WEIGHT_SETS = ({'align': 1.0, 'rs': 0.25, 'breadth': 0.2, 'smt': 0.1, 'session': 0.15, 'trend': 0.5, 'location': 0.1},)

INDEX_Y = {'NAS100': '^NDX', 'US30': '^DJI', 'US500': '^GSPC', 'DEX': '^GDAXI', 'JP225': '^N225'}
METAL_Y = {'XAUUSD': 'XAUUSD=X', 'XAGUSD': 'XAGUSD=X'}
DUKAS_INSTRUMENT = {'XAUUSD': 'XAUUSD', 'XAGUSD': 'XAGUSD', 'NAS100': 'USATECHIDXUSD', 'US30': 'USA30IDXUSD', 'US500': 'USA500IDXUSD', 'DEX': 'DEUIDXEUR', 'JP225': 'JPNIDXJPY'}
DUKAS_BOUNDS = {'XAUUSD': (10.0, 100000.0), 'XAGUSD': (0.1, 10000.0), 'NAS100': (100.0, 1000000.0), 'US30': (100.0, 1000000.0), 'US500': (100.0, 1000000.0), 'DEX': (100.0, 1000000.0), 'JP225': (100.0, 1000000.0)}


def utcnow():
    return datetime.now(timezone.utc)


def iso_dt(dt):
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def norm(s):
    return re.sub(r'[^A-Z0-9]', '', str(s).upper())


def safe_float(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def get_json(url, timeout=45, retries=4):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 TradingResearch/1.1', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(0.6 * (n + 1))
    raise RuntimeError(f'HTTP_FAIL {last}')


def rawget(url, timeout=40, retries=3):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'trading-api-v11-backtest/2.0', 'Accept': 'application/octet-stream,*/*'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except HTTPError as e:
            if e.code == 404:
                return b''
            last = e
        except Exception as e:
            last = e
        time.sleep(0.45 * (n + 1))
    raise RuntimeError(f'HTTP_FAIL {last}')


def yahoo_ticker(symbol, market):
    s = norm(symbol)
    if market == 'forex':
        return s + '=X'
    if market == 'metal':
        return METAL_Y[s]
    if market == 'index':
        return INDEX_Y[s]
    raise KeyError((s, market))


def _month_floor(dt):
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)


def _next_month(dt):
    return (dt.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _bounds(symbol, market):
    s = norm(symbol)
    if market in ('metal', 'index'):
        return DUKAS_BOUNDS[s]
    return (1e-6, 1e9)


def dukascopy_m5(symbol, market, start_ts, end_ts):
    s = norm(symbol)
    inst = DUKAS_INSTRUMENT.get(s, s)
    cur = _month_floor(datetime.fromtimestamp(start_ts, tz=timezone.utc))
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)
    out = []
    lo, hi = _bounds(s, market)
    while cur <= end_dt:
        month0 = cur.month - 1
        url = f'https://datafeed.dukascopy.com/datafeed/{inst}/{cur.year}/{month0:02d}/BID_candles_min_5.bi5'
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
                off, p1, p2, p3, p4, vol = rec
                o = p1 / 1000.0
                for oo, hh, ll, cc in ((o, p4 / 1000.0, p3 / 1000.0, p2 / 1000.0), (o, p2 / 1000.0, p3 / 1000.0, p4 / 1000.0)):
                    vals = (oo, hh, ll, cc)
                    if not all(math.isfinite(v) and lo <= v <= hi for v in vals):
                        continue
                    if ll <= min(oo, cc) <= max(oo, cc) <= hh and hh >= ll:
                        t = int(base_ts + int(off))
                        out.append([t, oo, hh, ll, cc, float(vol) if math.isfinite(float(vol)) else 0.0])
                        break
        cur = _next_month(cur)
    d = {r[0]: r for r in out}
    rows = [d[k] for k in sorted(d) if start_ts <= k <= end_ts]
    if len(rows) < 2000:
        raise RuntimeError(f'DUKAS_INSUFFICIENT_M5={len(rows)}')
    return rows, f'Dukascopy {inst} BID M5', True


def binance_m5(symbol, start_ts, end_ts):
    out = []
    cur = start_ts * 1000
    end = end_ts * 1000
    while cur <= end:
        q = urllib.parse.urlencode({'symbol': symbol, 'interval': '5m', 'startTime': cur, 'endTime': end, 'limit': 1000})
        j = get_json('https://api.binance.com/api/v3/klines?' + q, 30, 2)
        if not isinstance(j, list) or not j:
            break
        for x in j:
            out.append([int(x[0]) // 1000, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
        nxt = int(j[-1][0]) + 300000
        if nxt <= cur:
            break
        cur = nxt
        if len(j) < 1000:
            break
        time.sleep(0.02)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError('BINANCE_EMPTY')
    return [d[k] for k in sorted(d)], 'Binance Spot M5', True


def bybit_m5(symbol, start_ts, end_ts):
    out = []
    cursor = end_ts * 1000
    start = start_ts * 1000
    guard = 0
    while cursor >= start and guard < 40:
        guard += 1
        q = urllib.parse.urlencode({'category': 'spot', 'symbol': symbol, 'interval': '5', 'start': start, 'end': cursor, 'limit': 1000})
        j = get_json('https://api.bybit.com/v5/market/kline?' + q, 30, 2)
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
        raise RuntimeError('BYBIT_EMPTY')
    return [d[k] for k in sorted(d)], 'Bybit Spot M5', True


def yahoo_m5(symbol, market, start_ts, end_ts):
    ticker = yahoo_ticker(symbol, market)
    q = urllib.parse.urlencode({'period1': start_ts - 300, 'period2': end_ts + 300, 'interval': '5m', 'includePrePost': 'false', 'events': 'div,splits'})
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
    if len(rows) < 2000:
        raise RuntimeError(f'YAHOO_M5_INSUFFICIENT={len(rows)}')
    return rows, f'Yahoo Finance M5 {ticker}', True


def fetch_m5(symbol, market, start_ts, end_ts):
    errors = []
    if market == 'crypto':
        for fn in (binance_m5, bybit_m5):
            try:
                rows, src, exact = fn(symbol, start_ts, end_ts)
                if len(rows) < 5000:
                    raise RuntimeError('insufficient ' + src)
                return symbol, rows, src, exact, None
            except Exception as e:
                errors.append(f'{fn.__name__}:{e}')
        return symbol, [], None, False, ' | '.join(errors)[:1200]
    try:
        rows, src, exact = dukascopy_m5(symbol, market, start_ts, end_ts)
        return symbol, rows, src, exact, None
    except Exception as e:
        errors.append(f'dukascopy:{e}')
    try:
        rows, src, exact = yahoo_m5(symbol, market, start_ts, end_ts)
        return symbol, rows, src, exact, None
    except Exception as e:
        errors.append(f'yahoo:{e}')
    return symbol, [], None, False, ' | '.join(errors)[:1200]


def load_catalog():
    text = CATALOG.read_text(encoding='utf-8')
    out = {}
    for m in ('forex', 'crypto', 'metal', 'index'):
        z = re.search(rf'{m}:Object\.freeze\(\[(.*?)\]\)', text, re.S)
        if not z:
            raise RuntimeError('catalog parse ' + m)
        out[m] = re.findall(r"'([^']+)'", z.group(1))
    return out


def fetch_all(items, start_ts, end_ts):
    fetched = {}
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_m5, s, m, start_ts, end_ts): (s, m) for s, m in items}
        for fut in cf.as_completed(futs):
            s, m = futs[fut]
            ss, rows, src, exact, err = fut.result()
            fetched[ss] = (m, rows, src, exact, err)
            print('FETCH', m, ss, len(rows), src or err, flush=True)
    return fetched


def ema_series(vals, p):
    out = [None] * len(vals)
    if len(vals) < p:
        return out
    e = sum(vals[:p]) / p
    out[p - 1] = e
    k = 2 / (p + 1)
    for i in range(p, len(vals)):
        e = vals[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi_series(vals, p=14):
    out = [None] * len(vals)
    if len(vals) <= p:
        return out
    ag = al = 0.0
    for i in range(1, p + 1):
        d = vals[i] - vals[i - 1]
        ag += max(d, 0)
        al += max(-d, 0)
    ag /= p
    al /= p
    out[p] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(p + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        ag = (ag * (p - 1) + max(d, 0)) / p
        al = (al * (p - 1) + max(-d, 0)) / p
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def atr_series(rows, p=14):
    out = [None] * len(rows)
    if len(rows) <= p:
        return out
    tr = [max(rows[i][2] - rows[i][3], abs(rows[i][2] - rows[i - 1][4]), abs(rows[i][3] - rows[i - 1][4])) for i in range(1, len(rows))]
    a = sum(tr[:p]) / p
    out[p] = a
    for i in range(p + 1, len(rows)):
        a = (a * (p - 1) + tr[i - 1]) / p
        out[i] = a
    return out


@dataclass
class TF:
    rows: list
    end_ts: list
    ema20: list
    ema50: list
    ema200: list
    rsi14: list
    atr14: list


def resample_fixed(rows, seconds):
    b = {}
    for r in rows:
        k = (r[0] // seconds) * seconds
        if k not in b:
            b[k] = [k, r[1], r[2], r[3], r[4], r[5] or 0.0]
        else:
            z = b[k]
            z[2] = max(z[2], r[2])
            z[3] = min(z[3], r[3])
            z[4] = r[4]
            z[5] += (r[5] or 0.0)
    return [b[k] for k in sorted(b)]


def calendar_resample(rows, unit):
    buckets = {}
    for r in rows:
        dt = datetime.fromtimestamp(r[0], tz=timezone.utc)
        if unit == 'W':
            start = dt - timedelta(days=dt.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        k = int(start.timestamp())
        if k not in buckets:
            buckets[k] = [k, r[1], r[2], r[3], r[4], r[5] or 0.0]
        else:
            z = buckets[k]
            z[2] = max(z[2], r[2])
            z[3] = min(z[3], r[3])
            z[4] = r[4]
            z[5] += (r[5] or 0.0)
    return [buckets[k] for k in sorted(buckets)]


def enrich(raw, seconds=None, unit=None):
    if unit is not None:
        rows = calendar_resample(raw, unit)
        if seconds is None:
            seconds = 86400 if unit == 'D' else 604800
    else:
        rows = resample_fixed(raw, seconds)
    closes = [r[4] for r in rows]
    return TF(rows, [r[0] + seconds for r in rows], ema_series(closes, 20), ema_series(closes, 50), ema_series(closes, 200), rsi_series(closes), atr_series(rows))


def build_timeframes(raw_m5):
    return {
        'M5': enrich(raw_m5, 300),
        'M15': enrich(raw_m5, 900),
        'M30': enrich(raw_m5, 1800),
        'H1': enrich(raw_m5, 3600),
        'H4': enrich(raw_m5, 14400),
        'D1': enrich(raw_m5, unit='D'),
        'W1': enrich(raw_m5, unit='W'),
    }


def tf_idx(tf, ts):
    return bisect.bisect_right(tf.end_ts, ts) - 1


def trend(tf, i):
    if i < 0 or i >= len(tf.rows):
        return 'NEUTRAL'
    c = tf.rows[i][4]
    a = tf.ema20[i]
    b = tf.ema50[i]
    if a is None or b is None:
        return 'NEUTRAL'
    return 'LONG' if c > a > b else 'SHORT' if c < a < b else 'NEUTRAL'


def session_label(market, ts):
    if market == 'crypto':
        return 'CRYPTO'
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    h = dt.hour
    wd = dt.weekday()
    if wd >= 5:
        return 'WEEKEND'
    if 7 <= h < 12:
        return 'LONDON'
    if 12 <= h < 16:
        return 'OVERLAP'
    if 13 <= h < 21:
        return 'NEW_YORK'
    if h < 7:
        return 'ASIA'
    return 'OFF'


def market_open(market, dt):
    if market == 'crypto':
        return True
    return dt.weekday() < 5


def vol_regime(tf, i):
    if i < 30 or tf.atr14[i] is None:
        return 'UNKNOWN'
    vals = [x for x in tf.atr14[max(0, i - 30):i + 1] if x is not None]
    if len(vals) < 10:
        return 'UNKNOWN'
    med = statistics.median(vals)
    a = tf.atr14[i]
    return 'HIGH' if a > 1.25 * med else 'LOW' if a < 0.8 * med else 'NORMAL'


def htf_alignment(side, d1, di, h4, h4i, h1, h1i):
    states = [trend(d1, di), trend(h4, h4i), trend(h1, h1i)]
    same = sum(x == side for x in states)
    opp = sum(x not in (side, 'NEUTRAL') for x in states)
    return 'ALIGNED_3' if same == 3 else 'ALIGNED_2' if same == 2 and not opp else 'CONFLICT' if opp else 'MIXED'


def m15_sweeps(tf, j):
    if j < 8 or tf.atr14[j] is None:
        return []
    prev = tf.rows[j - 8:j]
    cur = tf.rows[j]
    lo = min(x[3] for x in prev)
    hi = max(x[2] for x in prev)
    out = []
    if cur[3] < lo and cur[4] > lo:
        out.append(('LONG', lo, cur[3]))
    if cur[2] > hi and cur[4] < hi:
        out.append(('SHORT', hi, cur[2]))
    return out


def displacement(m5, i, side):
    if i < 5 or m5.atr14[i] is None:
        return None
    cur = m5.rows[i]
    prev = m5.rows[i - 5:i]
    a = m5.atr14[i]
    if abs(cur[4] - cur[1]) < 0.5 * a:
        return None
    lv = max(x[2] for x in prev) if side == 'LONG' else min(x[3] for x in prev)
    ok = cur[4] > lv and cur[4] > cur[1] if side == 'LONG' else cur[4] < lv and cur[4] < cur[1]
    return lv if ok else None


def fvg_at(m5, i, side):
    if i < 2 or m5.atr14[i] is None:
        return None
    a = m5.atr14[i]
    x = m5.rows[i - 2]
    c = m5.rows[i]
    if side == 'LONG' and c[3] > x[2] and c[3] - x[2] >= 0.05 * a:
        return [x[2], c[3]]
    if side == 'SHORT' and c[2] < x[3] and x[3] - c[2] >= 0.05 * a:
        return [c[2], x[3]]
    return None


def opposite_gap(m5, i, side):
    opp = 'SHORT' if side == 'LONG' else 'LONG'
    for k in range(i - 1, max(1, i - 12) - 1, -1):
        z = fvg_at(m5, k, opp)
        if z:
            return z
    return None


class CrossContext:
    def __init__(self, raw_by_symbol):
        self.h1_rows = {}
        self.h1_ret = {}
        for s, rows in raw_by_symbol.items():
            if not rows:
                continue
            h1 = resample_fixed(rows, 3600)
            if len(h1) < 50:
                continue
            self.h1_rows[s] = h1
            opens = [r[0] for r in h1]
            rets = {}
            for i, r in enumerate(h1):
                p = bisect.bisect_right(opens, r[0] - 86400) - 1
                if p >= 0 and r[4] > 0 and h1[p][4] > 0:
                    rets[r[0]] = math.log(r[4] / h1[p][4])
            self.h1_ret[s] = rets

    def features(self, symbol, ts, side, market):
        default = {'rs': 0.0, 'breadth': 0.5, 'median': 0.0, 'disp': 1.0}
        h1 = self.h1_rows.get(symbol)
        if h1 is None:
            return default
        idx = tf_idx(h1, ts)
        if idx < 0:
            return default
        vals = []
        rets = {}
        for s, hh in self.h1_rows.items():
            i2 = tf_idx(hh, ts)
            if i2 < 0:
                continue
            o2 = hh.rows[i2][0]
            r = self.h1_ret.get(s, {}).get(o2)
            if r is not None:
                vals.append(r)
                rets[s] = r
        if not vals:
            return default
        med = statistics.median(vals)
        breadth = sum(v > 0 for v in vals) / len(vals)
        sd = statistics.pstdev(vals) or 1e-9
        my = rets.get(symbol, 0.0)
        rs = (my - med) / sd
        return {'rs': rs, 'breadth': breadth, 'median': med, 'disp': sd}


def generate_signals(symbol, market, tfs, ctx):
    m5 = tfs['M5']
    m15 = tfs['M15']
    m30 = tfs['M30']
    h1 = tfs['H1']
    h4 = tfs['H4']
    d1 = tfs['D1']
    w1 = tfs['W1']
    out = []
    last = defaultdict(lambda: -9999)
    sweeps = {'LONG': None, 'SHORT': None}
    breaks = {'LONG': None, 'SHORT': None}
    fails = {'LONG': None, 'SHORT': None}
    prev15 = -1
    seen = set()
    for i in range(100, len(m5.rows) - MAX_HOLD_BARS - RETEST_BARS - 2):
        ts = m5.rows[i][0] + 300
        j15 = tf_idx(m15, ts)
        j30 = tf_idx(m30, ts)
        j1 = tf_idx(h1, ts)
        j4 = tf_idx(h4, ts)
        jd = tf_idx(d1, ts)
        jw = tf_idx(w1, ts)
        if min(j15, j30, j1, j4, jd, jw) < 0:
            continue
        if j15 != prev15:
            prev15 = j15
            for side, lv, ext in m15_sweeps(m15, j15):
                sweeps[side] = (ts, lv, ext)
            if j15 >= 12 and m15.atr14[j15] is not None:
                cur = m15.rows[j15]
                prev = m15.rows[j15 - 12:j15]
                hi = max(x[2] for x in prev)
                lo = min(x[3] for x in prev)
                a = m15.atr14[j15]
                mid = (hi + lo) / 2
                if cur[4] > hi + 0.05 * a:
                    breaks['LONG'] = (ts, hi)
                if cur[4] < lo - 0.05 * a:
                    breaks['SHORT'] = (ts, lo)
                if cur[2] > hi + 0.15 * a and cur[4] < hi and cur[4] < mid:
                    fails['SHORT'] = (ts, hi, cur[2])
                if cur[3] < lo - 0.15 * a and cur[4] > lo and cur[4] > mid:
                    fails['LONG'] = (ts, lo, cur[3])
        for side in ('LONG', 'SHORT'):
            disp = displacement(m5, i, side)
            gap = fvg_at(m5, i, side)
            h1side = trend(h1, j1)
            ctxf = ctx.features(symbol, ts, side, market) if ctx else {'rs': 0.0, 'breadth': 0.5, 'median': 0.0, 'disp': 1.0}
            states = [trend(w1, jw), trend(d1, jd), trend(h4, j4), trend(h1, j1)]
            alignScore = sum(x == side for x in states)
            regimeMatch = 1 if all(x in (side, 'NEUTRAL') for x in states[:2]) and side in states[:2] else 0
            smt = 0
            if j4 >= 1 and j1 >= 1:
                lb = max(0, j4 - 4)
                rng_h4 = tfs['H4'].rows[lb:j4 + 1]
                hi4 = max(x[2] for x in rng_h4)
                lo4 = min(x[3] for x in rng_h4)
                h1c = tfs['H1'].rows[j1][4]
                if side == 'LONG' and h1c > hi4:
                    smt = 1
                if side == 'SHORT' and h1c < lo4:
                    smt = 1
            m30loc = 0
            if j30 >= 0 and m30.ema20[j30] is not None:
                m30r = m30.rows[j30]
                if side == 'LONG' and m30r[4] > m30.ema20[j30]:
                    m30loc = 1
                if side == 'SHORT' and m30r[4] < m30.ema20[j30]:
                    m30loc = 1

            def emit(a, lv, st, z=None):
                key = (i, side, a)
                if key in seen:
                    return
                seen.add(key)
                if i - last[(a, side)] < COOLDOWN_BARS:
                    return
                out.append({
                    'symbol': symbol, 'market': market, 'i': i, 'ts': ts, 'arch': a,
                    'side': side, 'level': lv, 'structure': st, 'fvg': z,
                    'session': session_label(market, ts), 'htfAl': htf_alignment(side, d1, jd, h4, j4, h1, j1),
                    'vol': vol_regime(h1, j1), 'alignScore': alignScore, 'regimeMatch': regimeMatch,
                    'smt': smt, 'rs': ctxf['rs'], 'breadthSide': ctxf['breadth'] if side == 'LONG' else 1.0 - ctxf['breadth'],
                    'm30loc': m30loc,
                })
                last[(a, side)] = i

            sw = sweeps[side]
            if sw and ts - sw[0] <= 1800:
                if disp is not None:
                    emit('A_SWEEP_MSS', disp, sw[2], gap)
                if gap is not None:
                    emit('C_SWEEP_FVG', sum(gap) / 2, sw[2], gap)
            if h1side == side and m15.ema20[j15] is not None and disp is not None:
                r = m15.rows[j15]
                e = m15.ema20[j15]
                ok = (side == 'LONG' and r[3] <= e < r[4]) or (side == 'SHORT' and r[2] >= e > r[4])
                if ok:
                    emit('B_H1_PULLBACK_RECLAIM', disp, min(x[3] for x in m5.rows[i - 10:i + 1]) if side == 'LONG' else max(x[2] for x in m5.rows[i - 10:i + 1]), gap)
            br = breaks[side]
            if br and 0 < ts - br[0] <= 3600 and h1side == side and disp is not None:
                r = m15.rows[j15]
                lv = br[1]
                ok = (side == 'LONG' and r[3] <= lv < r[4]) or (side == 'SHORT' and r[2] >= lv > r[4])
                if ok:
                    emit('D_BREAK_RETEST_CONT', lv, min(x[3] for x in m5.rows[i - 12:i + 1]) if side == 'LONG' else max(x[2] for x in m5.rows[i - 12:i + 1]), gap)
            fb = fails[side]
            if fb and ts - fb[0] <= 1800 and disp is not None:
                emit('E_FAILED_BREAK_REV', disp, fb[2], gap)
            zg = opposite_gap(m5, i, side)
            if zg and disp is not None and ((side == 'LONG' and m5.rows[i][4] > zg[1]) or (side == 'SHORT' and m5.rows[i][4] < zg[0])):
                emit('F_IFVG_RECLAIM', sum(zg) / 2, min(x[3] for x in m5.rows[i - 10:i + 1]) if side == 'LONG' else max(x[2] for x in m5.rows[i - 10:i + 1]), zg)
            if h1side == side and alignScore >= 2 and disp is not None and m15.ema20[j15] is not None:
                r = m15.rows[j15]
                e = m15.ema20[j15]
                ok = (side == 'LONG' and r[3] <= e) or (side == 'SHORT' and r[2] >= e)
                if ok:
                    emit('TREND_PULLBACK', disp, min(x[3] for x in m5.rows[i - 10:i + 1]) if side == 'LONG' else max(x[2] for x in m5.rows[i - 10:i + 1]), gap)
    return out


def find_entry(c, tfs):
    m5 = tfs['M5']
    i = c['i']
    side = c['side']
    atr = m5.atr14[i]
    if atr is None:
        return None
    if c['entryMode'] == 'CLOSE':
        ei = i + 1
        if ei >= len(m5.rows):
            return None
        return ei, m5.rows[ei][1]
    if c['entryMode'] == 'RETEST':
        lv = float(c['level'])
        for k in range(i + 1, min(len(m5.rows), i + RETEST_BARS + 1)):
            r = m5.rows[k]
            touch = (r[3] <= lv + 0.15 * atr and r[2] >= lv - 0.15 * atr)
            ok = r[4] >= lv if side == 'LONG' else r[4] <= lv
            if touch and ok:
                if k + 1 >= len(m5.rows):
                    return None
                return k + 1, m5.rows[k + 1][1]
        return None
    z = c.get('fvg')
    if not z:
        return None
    mid = sum(z) / 2
    for k in range(i + 1, min(len(m5.rows), i + RETEST_BARS + 1)):
        if m5.rows[k][3] <= mid <= m5.rows[k][2]:
            return k, mid
    return None


def exec_day(c, tfs):
    m5 = tfs['M5']
    ei = c['ei']
    if ei >= len(m5.rows):
        return None
    return datetime.fromtimestamp(m5.rows[ei][0], tz=timezone.utc).date().isoformat()


def build_candidates(symbol, market, tfs, ctx):
    sigs = generate_signals(symbol, market, tfs, ctx)
    out = []
    seen = set()
    for sig in sigs:
        for rule in RULES:
            if rule == 'ALIGNED2' and sig['alignScore'] < 2:
                continue
            if rule == 'ALIGNED3' and sig['alignScore'] < 3:
                continue
            if rule == 'RS' and sig['rs'] <= 0:
                continue
            if rule == 'BREADTH' and sig['breadthSide'] < 0.5:
                continue
            if rule == 'REGIME' and sig['regimeMatch'] != 1:
                continue
            for entry in ENTRY_MODES:
                if entry == 'LIMIT_FVG' and sig.get('fvg') is None:
                    continue
                for stop in STOP_MODES:
                    for rr in ALLOWED_RR:
                        key = (sig['i'], sig['side'], sig['arch'], rule, entry, stop, rr)
                        if key in seen:
                            continue
                        seen.add(key)
                        c = dict(sig)
                        c.update({'entryMode': entry, 'stopMode': stop, 'rr': rr, 'rule': rule, 'variant': f'{rule}|{entry}|{stop}|RR{int(rr)}'})
                        e = find_entry(c, tfs)
                        if e is None:
                            continue
                        c['ei'], c['entry'] = e
                        d = exec_day(c, tfs)
                        if d is None:
                            continue
                        c['execDay'] = d
                        out.append(c)
    return out


def execute_trade(c, tfs, market):
    m5 = tfs['M5']
    ei = c['ei']
    side = c['side']
    atr = m5.atr14[c['i']]
    if atr is None or ei >= len(m5.rows):
        return None
    entry = c['entry']
    st = float(c['structure'])
    raw = st - 0.05 * atr if side == 'LONG' else st + 0.05 * atr
    dist = entry - raw if side == 'LONG' else raw - entry
    if dist <= 0:
        return None
    if c['stopMode'] == 'STRUCTURE_ATR' and dist < 0.8 * atr:
        dist = 0.8 * atr
    sl = entry - dist if side == 'LONG' else entry + dist
    tp = entry + c['rr'] * dist if side == 'LONG' else entry - c['rr'] * dist
    result = None
    outcome = 'TIMEOUT'
    xi = min(len(m5.rows) - 1, ei + MAX_HOLD_BARS - 1)
    for k in range(ei, min(len(m5.rows), ei + MAX_HOLD_BARS)):
        r = m5.rows[k]
        hit_sl = r[3] <= sl if side == 'LONG' else r[2] >= sl
        hit_tp = r[2] >= tp if side == 'LONG' else r[3] <= tp
        if hit_sl and hit_tp:
            result = -1 - COST_R
            outcome = 'SL'
            xi = k
            break
        if hit_sl:
            result = -1 - COST_R
            outcome = 'SL'
            xi = k
            break
        if hit_tp:
            result = c['rr'] - COST_R
            outcome = 'TP'
            xi = k
            break
    if result is None:
        result = -COST_R
    return {'r': round(result, 4), 'outcome': outcome, 'entryI': ei, 'exitI': xi, 'day': c['execDay']}


def candidate_quality(c, w):
    q = 0.0
    q += w.get('align', 1.0) * (1.0 if c['alignScore'] >= 3 else 0.6 if c['alignScore'] == 2 else 0.2)
    q += w.get('rs', 0.25) * max(0.0, c['rs']) / 3.0
    q += w.get('breadth', 0.2) * c['breadthSide']
    q += w.get('smt', 0.1) * c['smt']
    q += w.get('session', 0.15) * (1.0 if c['session'] in ('LONDON', 'NEW_YORK', 'OVERLAP', 'CRYPTO') else 0.4 if c['session'] == 'ASIA' else 0.0)
    q += w.get('trend', 0.5) * (c['alignScore'] / 4.0)
    q += w.get('location', 0.1) * c.get('m30loc', 0)
    return round(q, 6)


def profile_matches(c, p):
    if p['arch'] != 'ALL' and c['arch'] != p['arch']:
        return False
    if c['rule'] != p['rule']:
        return False
    if c['entryMode'] != p['entry']:
        return False
    if c['stopMode'] != p['stop']:
        return False
    if c['rr'] != p['rr']:
        return False
    if p['session'] == 'LONDON_NY':
        if c['session'] not in ('LONDON', 'NEW_YORK', 'OVERLAP'):
            return False
    elif p['session'] != 'ALL' and c['session'] != p['session']:
        return False
    return True


def eval_profile(cands, days, profile, market, tfs):
    byday = defaultdict(list)
    for c in cands:
        byday[c['execDay']].append(c)
    trades = []
    covered = set()
    day_counts = defaultdict(int)
    for day in days:
        day_cands = [c for c in byday.get(day, []) if profile_matches(c, profile)]
        ranked = sorted(day_cands, key=lambda c: candidate_quality(c, profile['weights']), reverse=True)[:profile['maxTrades']]
        for c in ranked:
            t = execute_trade(c, tfs, market)
            if t:
                trades.append(t)
                covered.add(day)
                day_counts[day] += 1
    n = len(trades)
    tp = sum(t['outcome'] == 'TP' for t in trades)
    sl = sum(t['outcome'] == 'SL' for t in trades)
    to = sum(t['outcome'] == 'TIMEOUT' for t in trades)
    return {
        'trades': n,
        'daysTraded': len(covered),
        'expectedDays': len(days),
        'coveragePct': round(100 * len(covered) / len(days), 2) if days else 0,
        'tp': tp,
        'sl': sl,
        'timeout': to,
        'winRate': round(100 * tp / n, 2) if n else 0,
        'meanR': round((tp * profile['rr'] - sl - COST_R * n) / n, 4) if n else 0,
        'maxTradesInDay': max(day_counts.values(), default=0),
        'dayCounts': dict(day_counts),
    }


def clean_stats(s):
    return {k: v for k, v in s.items() if k != 'dayCounts'}


def make_profiles():
    out = []
    for rule in RULES:
        for entry in ENTRY_MODES:
            for stop in STOP_MODES:
                for rr in ALLOWED_RR:
                    for mt in (1, 2, 3):
                        for session in ('ALL', 'LONDON_NY'):
                            for w in WEIGHT_SETS:
                                out.append({'arch': 'ALL', 'rule': rule, 'entry': entry, 'stop': stop, 'rr': rr, 'maxTrades': mt, 'session': session, 'weights': w})
    return out


def profile_rank(dev, val):
    return (
        1 if dev.get('coveragePct', 0) >= 90 else 0,
        1 if dev.get('meanR', -9) > 0 else 0,
        dev.get('winRate', 0),
        dev.get('meanR', -9),
        1 if val.get('coveragePct', 0) >= 80 else 0,
        1 if val.get('meanR', -9) > 0 else 0,
        val.get('winRate', 0),
        val.get('meanR', -9),
        -dev.get('timeout', 999),
    )


def eligible_days(rows, market, start_dt, end_dt):
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    counts = defaultdict(int)
    for r in rows:
        if not (start_ts <= r[0] < end_ts):
            continue
        dt = datetime.fromtimestamp(r[0], tz=timezone.utc)
        if not market_open(market, dt):
            continue
        counts[dt.date().isoformat()] += 1
    return sorted(d for d, c in counts.items() if c >= 12)


def optimize_symbol(symbol, market, rows, tfs, ctx, dev_start, val_start, final_start, final_end, history_start, src, exact, err):
    result = {'symbol': symbol, 'market': market, 'source': src, 'sourceExactInstrument': bool(exact), 'dataError': err, 'rows': len(rows)}
    if len(rows) < 20000:
        result.update({'pass': False, 'reasons': ['INSUFFICIENT_HISTORY']})
        return result
    train_days = eligible_days(rows, market, history_start, dev_start)
    dev_days = eligible_days(rows, market, dev_start, val_start)
    val_days = eligible_days(rows, market, val_start, final_start)
    final_days = eligible_days(rows, market, final_start, final_end)
    if not dev_days or not val_days or not final_days:
        result.update({'pass': False, 'reasons': ['NO_DEV_OR_VALIDATION_OR_FINAL_DAYS']})
        return result
    cands = build_candidates(symbol, market, tfs, ctx)
    if len(cands) < 100:
        result.update({'pass': False, 'reasons': ['INSUFFICIENT_CANDIDATES']})
        return result
    best = None
    best_rank = None
    for profile in make_profiles():
        dev = eval_profile(cands, dev_days, profile, market, tfs)
        if dev['trades'] < max(8, int(len(dev_days) * 0.5)):
            continue
        val = eval_profile(cands, val_days, profile, market, tfs)
        rk = profile_rank(dev, val)
        if best_rank is None or rk > best_rank:
            best_rank = rk
            best = (profile, dev, val)
    if best is None:
        result.update({'pass': False, 'reasons': ['NO_PRE_EVAL_PROFILE']})
        return result
    profile, dev, val = best
    train_stats = eval_profile(cands, train_days, profile, market, tfs) if train_days else None
    final = eval_profile(cands, final_days, profile, market, tfs)
    reasons = []
    if not bool(exact):
        reasons.append('NON_EXACT_DATA')
    if final['expectedDays'] <= 0:
        reasons.append('NO_ELIGIBLE_FINAL_DAYS')
    else:
        if final['trades'] < final['expectedDays'] or final['trades'] > 3 * final['expectedDays']:
            reasons.append('FINAL_TRADE_COUNT_OUT_OF_BOUNDS')
        if final['daysTraded'] < final['expectedDays']:
            reasons.append('ZERO_TRADE_ELIGIBLE_DAY')
        if final['maxTradesInDay'] > 3:
            reasons.append('MAX3_BREACH')
        if final['winRate'] < REQUIRED_WR:
            reasons.append('WIN_RATE_BELOW_80')
        if final['meanR'] <= 0:
            reasons.append('MEAN_R_NONPOSITIVE')
        for d, cnt in final.get('dayCounts', {}).items():
            if not (1 <= cnt <= 3):
                reasons.append('DAILY_COUNT_OUT_OF_RANGE')
    if profile['rr'] not in ALLOWED_RR:
        reasons.append('RR_INVALID')
    result.update({
        'profile': profile,
        'eligibleDays': {'train': len(train_days), 'dev': len(dev_days), 'validation': len(val_days), 'final': len(final_days)},
        'train': clean_stats(train_stats) if train_stats else None,
        'dev': clean_stats(dev),
        'validation': clean_stats(val),
        'final': clean_stats(final),
        'finalDailyTradeCounts': final.get('dayCounts', {}),
        'validCandidates': len(cands),
        'pass': not reasons,
        'reasons': reasons,
        'selectionData': 'DEV_PLUS_VALIDATION_ONLY',
        'holdoutExcludedFromTuning': True,
    })
    return result


def main(out_dir='data'):
    os.makedirs(out_dir, exist_ok=True)
    cat = load_catalog()
    items = [(s, m) for m in ('forex', 'crypto', 'metal', 'index') for s in cat[m]]
    end_dt = utcnow().replace(minute=0, second=0, microsecond=0)
    final_start = end_dt - timedelta(days=EVAL_DAYS)
    val_start = final_start - timedelta(days=VAL_DAYS)
    dev_start = val_start - timedelta(days=DEV_DAYS)
    history_start = end_dt - timedelta(days=HISTORY_DAYS)
    start_ts = int(history_start.timestamp())
    end_ts = int(end_dt.timestamp())
    fetched = fetch_all(items, start_ts, end_ts)
    raw = {s: rows for s, (_m, rows, _src, _exact, _err) in fetched.items()}
    ctx = CrossContext(raw) if raw else None
    tfs_all = {}
    for s, m in items:
        rows = fetched[s][1]
        if rows:
            try:
                tfs_all[s] = build_timeframes(rows)
                print('TF_BUILD', m, s, len(rows), flush=True)
            except Exception as e:
                tfs_all[s] = None
                print('TF_BUILD_ERROR', m, s, e, flush=True)
        else:
            tfs_all[s] = None
    results = {}
    for idx, (s, m) in enumerate(items):
        rows, src, exact, err = fetched[s][1], fetched[s][2], fetched[s][3], fetched[s][4]
        if not rows or tfs_all[s] is None:
            results[s] = {'symbol': s, 'market': m, 'source': src, 'sourceExactInstrument': bool(exact), 'dataError': err, 'pass': False, 'reasons': ['DATA_UNAVAILABLE']}
            print('RESULT', s, 'FAIL', results[s]['reasons'], flush=True)
            continue
        print('FEATURES', m, s, len(rows), flush=True)
        r = optimize_symbol(s, m, rows, tfs_all[s], ctx, dev_start, val_start, final_start, end_dt, history_start, src, exact, err)
        results[s] = r
        print('RESULT', s, 'PASS' if r.get('pass') else 'FAIL', (r.get('final') or {}).get('winRate'), r.get('reasons'), flush=True)
        if 'final' in r:
            print('dailyTradeCount', s, json.dumps(r['final'].get('dayCounts', {}), separators=(',', ':')), flush=True)
    results = {s: results[s] for s, _ in items}
    passed = [s for s, x in results.items() if x.get('pass')]
    failed = [s for s, x in results.items() if not x.get('pass')]
    meta_out = {
        'version': VERSION,
        'generatedAt': iso_dt(utcnow()),
        'historyStart': iso_dt(history_start),
        'devStart': iso_dt(dev_start),
        'validationStart': iso_dt(val_start),
        'finalStart': iso_dt(final_start),
        'finalEnd': iso_dt(end_dt),
        'evaluationDays': EVAL_DAYS,
        'requiredWinRateInclusive': REQUIRED_WR,
        'allowedRR': [1, 2],
        'maxEntriesPerEligibleDay': 3,
        'totalSymbols': len(items),
        'passCount': len(passed),
        'allPassed': len(passed) == len(items),
        'method': 'hierarchical MTF V11; DEV/VALIDATION-only profile selection; untouched final holdout',
        'sameBarRule': 'SL conservative',
        'timeoutRule': 'non-win',
    }
    out_obj = {'meta': meta_out, 'markets': {k: len(v) for k, v in cat.items()}, 'symbols': results}
    OUT.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding='utf-8')
    gate = {'meta': meta_out, 'passingSymbols': passed, 'failingSymbols': failed}
    GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps({'passCount': len(passed), 'totalSymbols': len(items), 'allPassed': not failed, 'failedCount': len(failed)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
