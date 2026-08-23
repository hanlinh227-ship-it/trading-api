#!/usr/bin/env python3
"""V11 per-symbol four-month backtest and calibration.

Safety / validity rules:
- Every symbol in cloudflare-worker/v11/symbol-catalog.js is tested separately.
- Recent window defaults to the latest 122 days (~4 months).
- 5-minute OHLC is used; no future bars are used to create an entry.
- Entry is the NEXT M5 bar open with conservative adverse execution padding.
- Same-bar TP+SL is counted as SL.
- Timeout is counted as a non-win.
- Only RR 1:1 or 1:2 is allowed.
- Model selection uses chronological DEV 60% + VALIDATION 20% only.
- Final OOS 20% is never used to rank candidates.
- PASS requires >80% win rate on VALIDATION, OOS and full 4-month window,
  plus minimum sample counts. This intentionally makes trivial 2-3 trade
  overfit configurations unable to pass.

The script writes:
  data/v11_symbol_backtest_4m.json
  data/v11_backtest_gate.json
  cloudflare-worker/v11/generated-backtest-profiles.js

A failed or unavailable symbol keeps the global gate closed. The script never
unlocks Telegram or deploys production by itself.
"""
from __future__ import annotations

import argparse
import ast
import bisect
import concurrent.futures as cf
import json
import math
import os
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'cloudflare-worker/v11/symbol-catalog.js'
OUT = ROOT / 'data/v11_symbol_backtest_4m.json'
GATE = ROOT / 'data/v11_backtest_gate.json'
GENERATED = ROOT / 'cloudflare-worker/v11/generated-backtest-profiles.js'
VERSION = 'V11-4M-SYMBOL-BACKTEST-R1'
BAR_SEC = 300
TD_PAGE = 5000
TD_PAUSE_SEC = int(os.environ.get('V11_TD_PAUSE_SEC', '62'))
MAX_TD_PAGES = int(os.environ.get('V11_TD_MAX_PAGES', '8'))
MIN_TOTAL_TRADES = int(os.environ.get('V11_MIN_TOTAL_TRADES', '40'))
MIN_DEV_TRADES = int(os.environ.get('V11_MIN_DEV_TRADES', '20'))
MIN_VAL_TRADES = int(os.environ.get('V11_MIN_VAL_TRADES', '8'))
MIN_OOS_TRADES = int(os.environ.get('V11_MIN_OOS_TRADES', '8'))
REQUIRED_WR = float(os.environ.get('V11_REQUIRED_WR', '80'))
ALLOWED_RR = (1.0, 2.0)
STOP_ATR = (0.75, 1.0, 1.25, 1.5)
HORIZON_BARS = (18, 36)
STRENGTH_MIN = (0.0, 0.45)
COST_ATR = {'crypto': 0.015, 'forex': 0.025, 'metal': 0.02, 'index': 0.02}
INDEX_TD = {'NAS100': 'NDX', 'US30': 'DJI', 'US500': 'SPX', 'DEX': 'DAX', 'JP225': 'N225'}


def utcnow():
    return datetime.now(timezone.utc)


def iso_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_dt(v):
    if v is None:
        return None
    s = str(v).strip().replace('Z', '+00:00').replace(' ', 'T')
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp())
    except Exception:
        return None


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def http_json(url, timeout=45, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Trading-V11-Backtest/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(min(4, 0.75 * (attempt + 1)))
    raise RuntimeError(f'HTTP_FAIL {url[:120]} :: {last}')


def load_catalog():
    text = CATALOG.read_text(encoding='utf-8')
    out = {}
    for market in ('forex', 'crypto', 'metal', 'index'):
        m = re.search(rf"{market}:Object\.freeze\(\[(.*?)\]\)", text, re.S)
        if not m:
            raise RuntimeError(f'catalog parse failed for {market}')
        out[market] = re.findall(r"'([^']+)'", m.group(1))
    return out


def norm_symbol(s):
    return re.sub(r'[^A-Z0-9]', '', str(s).upper())


def td_provider(symbol, market):
    s = norm_symbol(symbol)
    if market in ('forex', 'metal'):
        return f'{s[:3]}/{s[3:]}'
    if market == 'index':
        return INDEX_TD[s]
    raise KeyError((symbol, market))


def td_request(symbols, api_key, end_date=None, index_mode=False):
    q = {
        'symbol': ','.join(symbols),
        'interval': '5min',
        'outputsize': str(TD_PAGE),
        'timezone': 'UTC',
        'order': 'ASC',
        'apikey': api_key,
    }
    if end_date:
        q['end_date'] = end_date
    if index_mode:
        q['type'] = 'Index'
    url = 'https://api.twelvedata.com/time_series?' + urllib.parse.urlencode(q, safe=',/')
    return http_json(url, timeout=90, retries=3)


def td_objects(payload):
    if isinstance(payload, dict) and 'meta' in payload and 'values' in payload:
        return [payload]
    if isinstance(payload, dict):
        return [v for v in payload.values() if isinstance(v, dict) and 'values' in v]
    return []


def parse_td_rows(obj):
    rows = []
    for x in obj.get('values') or []:
        ts = parse_dt(x.get('datetime'))
        o, h, l, c = [fnum(x.get(k)) for k in ('open', 'high', 'low', 'close')]
        if ts is None or None in (o, h, l, c):
            continue
        rows.append([ts, o, h, l, c, fnum(x.get('volume')) or 0.0])
    rows.sort(key=lambda r: r[0])
    return rows


def chunks(xs, n):
    return [xs[i:i+n] for i in range(0, len(xs), n)]


def fetch_twelve_universe(catalog, start_ts, end_ts):
    key = os.environ.get('TWELVE_DATA_API_KEY', '').strip()
    targets = []
    for market in ('forex', 'metal'):
        for s in catalog[market]:
            targets.append((s, market, td_provider(s, market), False))
    idx_targets = [(s, 'index', td_provider(s, 'index'), True) for s in catalog['index']]
    by_provider = {norm_symbol(p): (s, m) for s, m, p, _ in targets + idx_targets}
    history = {s: [] for s, _, _, _ in targets + idx_targets}
    sources = {s: 'Twelve Data 5m' for s in history}
    errors = {}
    if not key:
        return history, sources, {s: 'TWELVE_DATA_API_KEY_MISSING' for s in history}
    end_date = None
    for page in range(MAX_TD_PAGES):
        reqs = []
        for group in chunks([x[2] for x in targets], 7):
            reqs.append((group, False))
        if idx_targets:
            reqs.append(([x[2] for x in idx_targets], True))
        objects = []
        with cf.ThreadPoolExecutor(max_workers=min(6, len(reqs))) as ex:
            futs = [ex.submit(td_request, g, key, end_date, idx) for g, idx in reqs]
            for fut in cf.as_completed(futs):
                try:
                    objects.extend(td_objects(fut.result()))
                except Exception as e:
                    objects.append({'_error': str(e)})
        oldest = []
        seen = set()
        for obj in objects:
            if '_error' in obj:
                continue
            meta = obj.get('meta') or {}
            ps = norm_symbol(meta.get('symbol'))
            mapped = by_provider.get(ps)
            if not mapped:
                continue
            s, _market = mapped
            rows = parse_td_rows(obj)
            if rows:
                history[s].extend(rows)
                oldest.append(rows[0][0])
                seen.add(s)
        for s in history:
            if s not in seen and not history[s]:
                errors.setdefault(s, 'TD_SYMBOL_NOT_RETURNED')
        if not oldest or min(oldest) <= start_ts:
            break
        end_date = iso_ts(min(oldest) - BAR_SEC)
        time.sleep(TD_PAUSE_SEC)
    for s, rows in history.items():
        d = {r[0]: r for r in rows if start_ts <= r[0] <= end_ts}
        history[s] = [d[k] for k in sorted(d)]
        if history[s]:
            errors.pop(s, None)
    return history, sources, errors


def binance_history(symbol, start_ts, end_ts):
    start_ms, end_ms = start_ts * 1000, end_ts * 1000
    cur = start_ms
    rows = []
    hosts = ('https://data-api.binance.vision', 'https://api.binance.com')
    while cur < end_ms:
        payload = None
        last = None
        q = urllib.parse.urlencode({'symbol': symbol, 'interval': '5m', 'startTime': cur, 'endTime': end_ms, 'limit': 1000})
        for host in hosts:
            try:
                x = http_json(f'{host}/api/v3/klines?{q}', timeout=30, retries=2)
                if isinstance(x, list):
                    payload = x
                    break
            except Exception as e:
                last = e
        if payload is None:
            raise RuntimeError(f'BINANCE_UNAVAILABLE {last}')
        if not payload:
            break
        for x in payload:
            if len(x) < 6:
                continue
            rows.append([int(x[0] / 1000), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
        nxt = int(payload[-1][0]) + BAR_SEC * 1000
        if nxt <= cur:
            break
        cur = nxt
        if len(payload) < 1000:
            break
        time.sleep(0.04)
    d = {r[0]: r for r in rows if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError('BINANCE_EMPTY')
    return [d[k] for k in sorted(d)]


def bybit_history(symbol, start_ts, end_ts):
    start_ms, cursor_end = start_ts * 1000, end_ts * 1000
    rows = []
    guard = 0
    while cursor_end > start_ms and guard < 80:
        guard += 1
        q = urllib.parse.urlencode({'category': 'spot', 'symbol': symbol, 'interval': '5', 'start': start_ms, 'end': cursor_end, 'limit': 1000})
        j = http_json('https://api.bybit.com/v5/market/kline?' + q, timeout=30, retries=2)
        arr = ((j.get('result') or {}).get('list') or []) if isinstance(j, dict) else []
        if not arr:
            break
        ts_batch = []
        for x in arr:
            if len(x) < 6:
                continue
            ts = int(int(x[0]) / 1000)
            ts_batch.append(ts)
            rows.append([ts, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
        if not ts_batch:
            break
        oldest_ms = min(ts_batch) * 1000
        if oldest_ms >= cursor_end:
            break
        cursor_end = oldest_ms - 1
        time.sleep(0.06)
    d = {r[0]: r for r in rows if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError('BYBIT_EMPTY')
    return [d[k] for k in sorted(d)]


def fetch_crypto_symbol(symbol, start_ts, end_ts):
    errs = []
    for name, fn in (('Binance Spot 5m', binance_history), ('Bybit Spot 5m', bybit_history)):
        try:
            rows = fn(symbol, start_ts, end_ts)
            return symbol, rows, name, None
        except Exception as e:
            errs.append(f'{name}:{e}')
    return symbol, [], None, ' | '.join(errs)


def fetch_crypto_universe(catalog, start_ts, end_ts):
    history, sources, errors = {}, {}, {}
    symbols = catalog['crypto']
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(fetch_crypto_symbol, s, start_ts, end_ts) for s in symbols]
        for fut in cf.as_completed(futs):
            s, rows, source, err = fut.result()
            history[s] = rows
            if source:
                sources[s] = source
            if err:
                errors[s] = err
    return history, sources, errors


def ema(vals, period):
    out = [None] * len(vals)
    if len(vals) < period:
        return out
    e = sum(vals[:period]) / period
    out[period - 1] = e
    k = 2 / (period + 1)
    for i in range(period, len(vals)):
        e = vals[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi(vals, period=14):
    out = [None] * len(vals)
    if len(vals) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = vals[i] - vals[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / period, losses / period
    out[period] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(period + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        out[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def atr(rows, period=14):
    out = [None] * len(rows)
    if len(rows) <= period:
        return out
    trs = []
    for i in range(1, len(rows)):
        trs.append(max(rows[i][2] - rows[i][3], abs(rows[i][2] - rows[i-1][4]), abs(rows[i][3] - rows[i-1][4])))
    a = sum(trs[:period]) / period
    out[period] = a
    for i in range(period + 1, len(rows)):
        a = (a * (period - 1) + trs[i - 1]) / period
        out[i] = a
    return out


def resample(rows, seconds):
    buckets = {}
    for r in rows:
        k = (r[0] // seconds) * seconds
        if k not in buckets:
            buckets[k] = [k, r[1], r[2], r[3], r[4], r[5]]
        else:
            b = buckets[k]
            b[2] = max(b[2], r[2]); b[3] = min(b[3], r[3]); b[4] = r[4]; b[5] += r[5]
    return [buckets[k] for k in sorted(buckets)]


class TF:
    def __init__(self, rows, seconds):
        self.rows = rows
        self.end = [r[0] + seconds for r in rows]
        closes = [r[4] for r in rows]
        self.ema20 = ema(closes, 20)
        self.ema50 = ema(closes, 50)
        self.rsi14 = rsi(closes, 14)
        self.atr14 = atr(rows, 14)


def tf_idx(tf, ts):
    return bisect.bisect_right(tf.end, ts) - 1


def trend(tf, i):
    if i < 0 or tf.ema20[i] is None or tf.ema50[i] is None:
        return 'NEUTRAL'
    c = tf.rows[i][4]
    return 'LONG' if c > tf.ema20[i] > tf.ema50[i] else 'SHORT' if c < tf.ema20[i] < tf.ema50[i] else 'NEUTRAL'


def session(ts, market):
    h = datetime.fromtimestamp(ts, timezone.utc).hour
    if market == 'crypto':
        return 'ASIA' if h < 7 else 'LONDON' if h < 13 else 'NEW_YORK' if h < 21 else 'OFF'
    return 'ASIA' if h < 7 else 'LONDON' if h < 13 else 'NEW_YORK' if h < 20 else 'OFF'


def generate_signals(rows, market):
    if len(rows) < 500:
        return []
    m5 = TF(rows, 300)
    m15 = TF(resample(rows, 900), 900)
    h1 = TF(resample(rows, 3600), 3600)
    out = []
    last = defaultdict(lambda: -9999)
    prev15 = -1

    def emit(i, family, side, strength, aligned):
        if i + 1 >= len(rows) - 36:
            return
        if i - last[(family, side)] < 6:
            return
        a = m5.atr14[i]
        if not a or a <= 0:
            return
        hist = rows[max(0, i-8):i+1]
        structure = min(x[3] for x in hist) if side == 'LONG' else max(x[2] for x in hist)
        out.append({
            'id': len(out), 'trigger_idx': i, 'entry_idx': i+1, 'ts': rows[i][0] + 300,
            'family': family, 'side': side, 'strength': float(max(0, strength)),
            'session': session(rows[i][0] + 300, market), 'aligned': bool(aligned),
            'atr': a, 'structure': structure,
        })
        last[(family, side)] = i

    for i in range(250, len(rows) - 38):
        a = m5.atr14[i]
        e20, e50, rv = m5.ema20[i], m5.ema50[i], m5.rsi14[i]
        if not a or None in (e20, e50, rv):
            continue
        ts = rows[i][0] + 300
        j1, j15 = tf_idx(h1, ts), tf_idx(m15, ts)
        ht = trend(h1, j1)
        cur, prev = rows[i], rows[i-1]
        body = abs(cur[4] - cur[1]) / a
        prev12 = rows[i-12:i]
        hi12, lo12 = max(x[2] for x in prev12), min(x[3] for x in prev12)

        # 1) H1 trend + M5 EMA pullback reclaim.
        if ht == 'LONG' and cur[3] <= e20 <= cur[4] and cur[4] > cur[1] and body >= .18:
            emit(i, 'TREND_PULLBACK', 'LONG', body, True)
        if ht == 'SHORT' and cur[2] >= e20 >= cur[4] and cur[4] < cur[1] and body >= .18:
            emit(i, 'TREND_PULLBACK', 'SHORT', body, True)

        # 2) Breakout continuation with directional context.
        if cur[4] > hi12 + .04*a and cur[4] > cur[1] and body >= .25:
            emit(i, 'BREAKOUT_CONT', 'LONG', body, ht == 'LONG')
        if cur[4] < lo12 - .04*a and cur[4] < cur[1] and body >= .25:
            emit(i, 'BREAKOUT_CONT', 'SHORT', body, ht == 'SHORT')

        # 3) Liquidity sweep and reclaim reversal.
        if cur[3] < lo12 - .04*a and cur[4] > lo12 and cur[4] > cur[1]:
            emit(i, 'SWEEP_RECLAIM', 'LONG', (lo12-cur[3])/a + body, ht != 'SHORT')
        if cur[2] > hi12 + .04*a and cur[4] < hi12 and cur[4] < cur[1]:
            emit(i, 'SWEEP_RECLAIM', 'SHORT', (cur[2]-hi12)/a + body, ht != 'LONG')

        # 4) RSI exhaustion reclaim.
        prv = m5.rsi14[i-1]
        if prv is not None and prv < 31 and rv > 37 and cur[4] > cur[1]:
            emit(i, 'RSI_RECLAIM', 'LONG', (37-prv)/20 + body, ht != 'SHORT')
        if prv is not None and prv > 69 and rv < 63 and cur[4] < cur[1]:
            emit(i, 'RSI_RECLAIM', 'SHORT', (prv-63)/20 + body, ht != 'LONG')

        # 5) EMA momentum displacement.
        prev3 = rows[i-3:i]
        if ht == 'LONG' and 52 <= rv <= 74 and cur[4] > max(x[2] for x in prev3) and body >= .30:
            emit(i, 'EMA_MOMENTUM', 'LONG', body, True)
        if ht == 'SHORT' and 26 <= rv <= 48 and cur[4] < min(x[3] for x in prev3) and body >= .30:
            emit(i, 'EMA_MOMENTUM', 'SHORT', body, True)

        # 6) Mean-reversion fade when H1 is not cleanly trending.
        if ht == 'NEUTRAL' and cur[4] < e20 - .75*a and rv < 30 and cur[4] > cur[1]:
            emit(i, 'MEAN_REVERSION', 'LONG', (e20-cur[4])/a, False)
        if ht == 'NEUTRAL' and cur[4] > e20 + .75*a and rv > 70 and cur[4] < cur[1]:
            emit(i, 'MEAN_REVERSION', 'SHORT', (cur[4]-e20)/a, False)

        # 7) Closed M15 failed-break reversal.
        if j15 >= 9 and j15 != prev15 and m15.atr14[j15] is not None:
            prev15 = j15
            r = m15.rows[j15]; p = m15.rows[j15-8:j15]; aa = m15.atr14[j15]
            hh, ll = max(x[2] for x in p), min(x[3] for x in p)
            if r[2] > hh + .08*aa and r[4] < hh:
                emit(i, 'FAILED_BREAK', 'SHORT', (r[2]-hh)/aa, ht != 'LONG')
            if r[3] < ll - .08*aa and r[4] > ll:
                emit(i, 'FAILED_BREAK', 'LONG', (ll-r[3])/aa, ht != 'SHORT')
    return out


def simulate_signal(rows, sig, market, stop_atr, rr, horizon):
    i = sig['entry_idx']; a = sig['atr']; side = sig['side']; sg = 1 if side == 'LONG' else -1
    raw_entry = rows[i][1]
    entry = raw_entry + sg * COST_ATR[market] * a
    floor = entry - sg * stop_atr * a
    struct = sig['structure'] - sg * .05 * a
    sl = min(struct, floor) if sg > 0 else max(struct, floor)
    risk = abs(entry - sl)
    if not (risk > 0) or risk > 2.5 * a:
        return ('SKIP', i, entry, sl, None)
    tp = entry + sg * rr * risk
    last = min(len(rows) - 1, i + horizon)
    for k in range(i, last + 1):
        h, l = rows[k][2], rows[k][3]
        hit_sl = l <= sl if sg > 0 else h >= sl
        hit_tp = h >= tp if sg > 0 else l <= tp
        if hit_sl and hit_tp:
            return ('LOSS', k, entry, sl, tp)
        if hit_sl:
            return ('LOSS', k, entry, sl, tp)
        if hit_tp:
            return ('WIN', k, entry, sl, tp)
    return ('TIMEOUT', last, entry, sl, tp)


def metric_for(signals, outcomes, key, t0, t1):
    chosen = [s for s in signals if t0 <= s['ts'] < t1]
    chosen.sort(key=lambda s: s['entry_idx'])
    wins = losses = timeouts = 0
    last_exit = -1
    rr = key[1]
    for s in chosen:
        if s['entry_idx'] <= last_exit:
            continue
        o = outcomes[s['id']][key]
        status, exit_idx = o[0], o[1]
        if status == 'SKIP':
            continue
        last_exit = exit_idx
        if status == 'WIN': wins += 1
        elif status == 'LOSS': losses += 1
        else: timeouts += 1
    trades = wins + losses + timeouts
    wr = 100.0 * wins / trades if trades else 0.0
    mean_r = ((wins * rr) - losses - timeouts) / trades if trades else 0.0
    return {'trades': trades, 'wins': wins, 'losses': losses, 'timeouts': timeouts, 'winRate': round(wr, 2), 'meanR': round(mean_r, 4)}


def optimize_symbol(symbol, market, rows, start_ts, end_ts, source, data_error=None):
    result = {'symbol': symbol, 'market': market, 'source': source, 'dataError': data_error}
    if not rows:
        result.update({'pass': False, 'reasons': ['DATA_UNAVAILABLE'], 'rows': 0})
        return result
    first, last = rows[0][0], rows[-1][0]
    coverage_ok = first <= start_ts + 7*86400 and last >= end_ts - 2*86400
    result.update({'rows': len(rows), 'firstBar': iso_ts(first), 'lastBar': iso_ts(last), 'coverageOk': coverage_ok})
    if len(rows) < 1000 or not coverage_ok:
        result.update({'pass': False, 'reasons': ['FOUR_MONTH_DATA_COVERAGE_FAIL']})
        return result
    signals = generate_signals(rows, market)
    result['rawSignals'] = len(signals)
    if len(signals) < MIN_TOTAL_TRADES:
        result.update({'pass': False, 'reasons': ['INSUFFICIENT_RAW_SIGNALS']})
        return result

    exit_keys = [(s, rr, h) for s in STOP_ATR for rr in ALLOWED_RR for h in HORIZON_BARS]
    outcomes = {sig['id']: {} for sig in signals}
    for sig in signals:
        for key in exit_keys:
            outcomes[sig['id']][key] = simulate_signal(rows, sig, market, *key)

    span = end_ts - start_ts
    dev_end = start_ts + int(span * .60)
    val_end = start_ts + int(span * .80)
    families = sorted({s['family'] for s in signals})
    sessions = ['ANY'] + sorted({s['session'] for s in signals})
    candidates = []
    for family in families:
        base = [s for s in signals if s['family'] == family]
        for sess in sessions:
            ss = base if sess == 'ANY' else [s for s in base if s['session'] == sess]
            for aligned in (False, True):
                aa = ss if not aligned else [s for s in ss if s['aligned']]
                for strength in STRENGTH_MIN:
                    ff = aa if strength <= 0 else [s for s in aa if s['strength'] >= strength]
                    if len(ff) < MIN_TOTAL_TRADES:
                        continue
                    for key in exit_keys:
                        dev = metric_for(ff, outcomes, key, start_ts, dev_end)
                        if dev['trades'] < MIN_DEV_TRADES or dev['meanR'] <= 0:
                            continue
                        val = metric_for(ff, outcomes, key, dev_end, val_end)
                        if val['trades'] < MIN_VAL_TRADES:
                            continue
                        robust = min(dev['winRate'], val['winRate'])
                        score = (robust, val['winRate'], val['meanR'], min(val['trades'], 30), dev['winRate'])
                        candidates.append((score, family, sess, aligned, strength, key, ff, dev, val))
    if not candidates:
        result.update({'pass': False, 'reasons': ['NO_DEV_VALIDATION_CANDIDATE']})
        return result
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, family, sess, aligned, strength, key, filtered, dev, val = candidates[0]
    oos = metric_for(filtered, outcomes, key, val_end, end_ts + 1)
    full = metric_for(filtered, outcomes, key, start_ts, end_ts + 1)
    stop_atr, rr_value, horizon = key
    profile = {
        'family': family, 'session': sess, 'requireAlignment': aligned,
        'minStrength': strength, 'stopAtr': stop_atr, 'rr': rr_value,
        'horizonBars': horizon, 'horizonMin': horizon * 5,
    }
    reasons = []
    if full['trades'] < MIN_TOTAL_TRADES: reasons.append('MIN_TOTAL_TRADES')
    if val['trades'] < MIN_VAL_TRADES: reasons.append('MIN_VALIDATION_TRADES')
    if oos['trades'] < MIN_OOS_TRADES: reasons.append('MIN_OOS_TRADES')
    if full['winRate'] <= REQUIRED_WR: reasons.append('FULL_WR_NOT_ABOVE_80')
    if val['winRate'] <= REQUIRED_WR: reasons.append('VALIDATION_WR_NOT_ABOVE_80')
    if oos['winRate'] <= REQUIRED_WR: reasons.append('OOS_WR_NOT_ABOVE_80')
    passed = not reasons
    result.update({
        'pass': passed, 'reasons': reasons, 'profile': profile,
        'dev': dev, 'validation': val, 'oos': oos, 'full4m': full,
        'split': {'devEnd': iso_ts(dev_end), 'validationEnd': iso_ts(val_end)},
        'candidateCount': len(candidates),
    })
    return result


def write_generated(meta, results):
    profiles = {}
    for s, r in results.items():
        p = r.get('profile') or {}
        if not p:
            continue
        profiles[s] = {
            **p,
            'eligible': bool(r.get('pass')),
            'market': r.get('market'),
            'winRate4m': (r.get('full4m') or {}).get('winRate'),
            'validationWinRate': (r.get('validation') or {}).get('winRate'),
            'oosWinRate': (r.get('oos') or {}).get('winRate'),
            'trades4m': (r.get('full4m') or {}).get('trades'),
        }
    js_meta = json.dumps(meta, ensure_ascii=False, separators=(',', ':'))
    js_profiles = json.dumps(profiles, ensure_ascii=False, separators=(',', ':'))
    text = f"""// AUTO-GENERATED by scripts/v11_symbol_backtest_4m.py.\n// Source results: data/v11_symbol_backtest_4m.json\nexport const V11_BACKTEST_META=Object.freeze({js_meta});\nconst RAW={js_profiles};\nfor(const k of Object.keys(RAW))Object.freeze(RAW[k]);\nexport const V11_BACKTEST_PROFILES=Object.freeze(RAW);\nexport function getV11BacktestProfile(symbol){{const s=String(symbol||'').toUpperCase().replace(/[^A-Z0-9]/g,'');return V11_BACKTEST_PROFILES[s]||null;}}\n"""
    GENERATED.write_text(text, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=122)
    args = ap.parse_args()
    end_dt = utcnow().replace(second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=args.days)
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    catalog = load_catalog()

    td_hist, td_sources, td_errors = fetch_twelve_universe(catalog, start_ts, end_ts)
    cr_hist, cr_sources, cr_errors = fetch_crypto_universe(catalog, start_ts, end_ts)
    history = {**td_hist, **cr_hist}
    sources = {**td_sources, **cr_sources}
    errors = {**td_errors, **cr_errors}

    results = {}
    for market in ('forex', 'crypto', 'metal', 'index'):
        for symbol in catalog[market]:
            print(f'BACKTEST {market} {symbol}', flush=True)
            try:
                results[symbol] = optimize_symbol(symbol, market, history.get(symbol, []), start_ts, end_ts, sources.get(symbol), errors.get(symbol))
            except Exception as e:
                results[symbol] = {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['BACKTEST_EXCEPTION'], 'error': str(e)[:1000]}

    total = sum(len(v) for v in catalog.values())
    passed = [s for s, r in results.items() if r.get('pass')]
    failed = [s for s, r in results.items() if not r.get('pass')]
    meta = {
        'version': VERSION, 'generatedAt': utcnow().isoformat(),
        'start': start_dt.isoformat(), 'end': end_dt.isoformat(),
        'requiredWinRate': REQUIRED_WR, 'allowedRR': [1, 2],
        'minTrades': MIN_TOTAL_TRADES, 'totalSymbols': total,
        'passCount': len(passed), 'allPassed': len(passed) == total,
        'selectionProtocol': 'chronological 60% DEV / 20% VALIDATION / 20% untouched OOS; OOS never ranks candidates',
        'sameBarRule': 'SL conservative', 'timeoutRule': 'non-win',
    }
    payload = {'meta': meta, 'markets': {m: len(xs) for m, xs in catalog.items()}, 'symbols': results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    gate = {**meta, 'passingSymbols': passed, 'failingSymbols': failed}
    GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')
    write_generated(meta, results)
    print(json.dumps({'allPassed': meta['allPassed'], 'passCount': len(passed), 'totalSymbols': total, 'failed': failed}, ensure_ascii=False))
    # A non-all-pass research result is a valid workflow result; global gate stays closed.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
