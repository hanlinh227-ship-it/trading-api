#!/usr/bin/env python3
# V11 isolated hierarchical multi-timeframe research engine.
# Chronological past-only DEV/VALIDATION selection; untouched OOS in FINAL mode.
# Higher frames are derived only from closed lower-frame bars.  No lookahead.
from __future__ import annotations
import bisect
import json
import math
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
import v11_mtf_data_cache as dcache

VERSION = 'V11-MTF-ENGINE-R1'
FEATURE_SCHEMA = 'v11-mtf-features-v1'
REQUIRED_WR = 80.0
ALLOWED_RR = (1.0, 2.0)
THRESHOLDS = (0.45, 0.55, 0.65)
MAX_TRADES_OPTIONS = (1, 2, 3)
COST_ATR = {'forex': 0.015, 'crypto': 0.020, 'metal': 0.020, 'index': 0.015}
BASE_TF = {'forex': 'h1', 'crypto': 'm5', 'metal': 'h1', 'index': 'h1'}
TF_SECONDS = {'m1': 60, 'm5': 300, 'm15': 900, 'm30': 1800, 'h1': 3600, 'h4': 14400, 'd1': 86400, 'w1': 604800}
MIN_BARS = {'m5': 4320, 'h1': 1440}
REGISTRY_PATH = _SCRIPT_DIR.parent / 'data/symbol_knowledge_registry.json'

def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return {}

def load_registry_prior(symbol):
    d = _load_json(REGISTRY_PATH)
    node = ((d.get('symbols') or {}).get(re.sub(r'[^A-Z0-9]', '', str(symbol).upper())) or {})
    prior = {}
    for k in ('priorRR', 'riskATR', 'signalHourUTC', 'timeframe'):
        if k in node:
            prior[k] = node[k]
    return prior

def ema_series(vals, p):
    out = [None] * len(vals)
    if len(vals) < p:
        return out
    e = sum(vals[:p]) / p
    out[p - 1] = e
    k = 2.0 / (p + 1)
    for i in range(p, len(vals)):
        e = vals[i] * k + e * (1 - k)
        out[i] = e
    return out

def atr_series(rows, p=14):
    out = [None] * len(rows)
    if len(rows) <= p:
        return out
    tr = []
    for i in range(1, len(rows)):
        hi = rows[i]['high']
        lo = rows[i]['low']
        pc = rows[i - 1]['close']
        tr.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
    a = sum(tr[:p]) / p
    out[p] = a
    for i in range(p + 1, len(rows)):
        a = (a * (p - 1) + tr[i - 1]) / p
        out[i] = a
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

class Frame:
    def __init__(self, name, seconds, bars):
        self.name = name
        self.seconds = seconds
        self.rows = []
        self.end_ts = []
        for r in bars:
            row = {'ts': int(r[0]), 'open': float(r[1]), 'high': float(r[2]), 'low': float(r[3]), 'close': float(r[4]), 'volume': float(r[5] or 0.0)}
            self.rows.append(row)
            self.end_ts.append(row['ts'] + seconds)
        self.ema20 = []
        self.ema50 = []
        self.atr = []
        self.rsi = []
        self._indicators()
    def _indicators(self):
        closes = [r['close'] for r in self.rows]
        self.ema20 = ema_series(closes, 20)
        self.ema50 = ema_series(closes, 50)
        self.atr = atr_series(self.rows, 14)
        self.rsi = rsi_series(closes, 14)
    def idx_at(self, ts):
        return bisect.bisect_right(self.end_ts, ts) - 1
    def trend(self, idx):
        if idx < 0 or idx >= len(self.rows):
            return 0
        c = self.rows[idx]['close']
        a = self.ema20[idx]
        b = self.ema50[idx]
        if a is None or b is None:
            return 0
        if c > a > b:
            return 1
        if c < a < b:
            return -1
        return 1 if c > a else -1 if c < a else 0

def daykey(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()

def is_market_day(ts, market):
    dt = datetime.fromtimestamp(int(ts), timezone.utc)
    return market == 'crypto' or dt.weekday() < 5

def _floor_time(ts, seconds):
    if seconds == 604800:
        return ts - ((ts - 3 * 86400) % 604800)
    if seconds == 86400:
        return (ts // 86400) * 86400
    return (ts // seconds) * seconds

def resample_bars(rows, seconds):
    buckets = {}
    for r in rows:
        k = _floor_time(int(r[0]), seconds)
        if k not in buckets:
            buckets[k] = [k, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5] or 0.0)]
        else:
            b = buckets[k]
            b[2] = max(b[2], float(r[2]))
            b[3] = min(b[3], float(r[3]))
            b[4] = float(r[4])
            b[5] += float(r[5] or 0.0)
    return [buckets[k] for k in sorted(buckets)]

def build_frames(market, rows):
    base_tf = BASE_TF[market]
    base_sec = TF_SECONDS[base_tf]
    base = Frame(base_tf, base_sec, rows)
    frames = {base_tf: base}
    if base_tf == 'm5':
        for name, sec in (('m15', 900), ('m30', 1800), ('h1', 3600), ('h4', 14400), ('d1', 86400), ('w1', 604800)):
            frames[name] = Frame(name, sec, resample_bars(rows, sec))
    else:
        for name, sec in (('h4', 14400), ('d1', 86400), ('w1', 604800)):
            frames[name] = Frame(name, sec, resample_bars(rows, sec))
    return frames, base_tf, base_sec

def build_candidates(market, rows):
    frames, base_tf, base_sec = build_frames(market, rows)
    base = frames[base_tf]
    loc_name = 'm15' if base_tf == 'm5' else 'h1'
    loc_f = frames[loc_name]
    hi_names = ['w1', 'd1', 'h4', 'h1']
    candidates = []
    for i in range(60, len(base.rows) - 1):
        signal_ts = base.rows[i]['ts'] + base_sec
        if not is_market_day(signal_ts, market):
            continue
        for side in (1, -1):
            align = 0.0
            for tf in hi_names:
                if tf in frames:
                    idx = frames[tf].idx_at(signal_ts)
                    t = frames[tf].trend(idx)
                    align += 1.0 if t == side else -1.0 if t == -side else 0.0
            align_norm = max(0.0, align / len(hi_names)) if align > 0 else 0.0
            lidx = loc_f.idx_at(signal_ts)
            loc_score = 0.0
            if lidx >= 0:
                lt = loc_f.trend(lidx)
                e20 = loc_f.ema20[lidx]
                a = loc_f.atr[lidx]
                if lt == side and e20 is not None and a and a > 0:
                    dev = (loc_f.rows[lidx]['close'] - e20) / a
                    if side == 1 and -1.0 <= dev <= 0.8:
                        loc_score = max(0.0, 1.0 - abs(dev))
                    elif side == -1 and -0.8 <= dev <= 1.0:
                        loc_score = max(0.0, 1.0 - abs(dev))
            trig_score = 0.0
            n = 5
            if i >= n:
                highs = [base.rows[j]['high'] for j in range(i - n, i)]
                lows = [base.rows[j]['low'] for j in range(i - n, i)]
                if side == 1 and base.rows[i]['close'] > max(highs):
                    trig_score = 1.0
                if side == -1 and base.rows[i]['close'] < min(lows):
                    trig_score = 1.0
            rsi_score = 0.0
            rsi = base.rsi[i]
            if rsi is not None:
                if side == 1 and 45 <= rsi <= 75:
                    rsi_score = 1.0
                if side == -1 and 25 <= rsi <= 55:
                    rsi_score = 1.0
            score = 0.35 * align_norm + 0.30 * loc_score + 0.25 * trig_score + 0.10 * rsi_score
            if trig_score > 0 and align_norm > 0 and loc_score > 0.2:
                atr = base.atr[i]
                if atr is None or atr <= 0:
                    continue
                recent_low = min(base.rows[j]['low'] for j in range(max(0, i - 8), i + 1))
                recent_high = max(base.rows[j]['high'] for j in range(max(0, i - 8), i + 1))
                struct_dist = base.rows[i]['close'] - recent_low if side == 1 else recent_high - base.rows[i]['close']
                stop_dist = max(0.8 * atr, struct_dist)
                if stop_dist <= 0:
                    continue
                candidates.append({'i': i, 'ts': signal_ts, 'day': daykey(signal_ts), 'side': side, 'score': round(score, 6), 'stop_dist': round(stop_dist, 8), 'atr': round(atr, 8)})
    return candidates

def build_or_load_candidates(symbol, market, rows, cache_dir):
    if cache_dir is None:
        print('FEATURES', symbol, 'build', len(rows), flush=True)
        return build_candidates(market, rows)
    data_hash = dcache.compute_data_hash(rows)
    schema_hash = dcache.feature_schema_hash(FEATURE_SCHEMA)
    cached = dcache.load_feature(cache_dir, symbol, data_hash, schema_hash)
    if cached is not None:
        print('CACHE_HIT FEATURES', symbol, len(cached), flush=True)
        return cached
    cands = build_candidates(market, rows)
    dcache.save_feature(cache_dir, symbol, data_hash, schema_hash, cands)
    print('FEATURES', symbol, len(cands), flush=True)
    return cands

def simulate_trade(base_frame, cand, rr, market):
    i = cand['i']
    side = cand['side']
    stop_dist = cand['stop_dist']
    atr = base_frame.atr[i] or cand['atr']
    if i + 1 >= len(base_frame.rows):
        return None
    entry = base_frame.rows[i + 1]['open'] + side * COST_ATR[market] * atr
    sl = entry - side * stop_dist
    tp = entry + side * rr * stop_dist
    max_hold = max(6, int(12 * 3600 / base_frame.seconds))
    last_j = None
    for j in range(i + 1, min(len(base_frame.rows), i + 1 + max_hold)):
        last_j = j
        bar = base_frame.rows[j]
        if side == 1:
            hs = bar['low'] <= sl
            ht = bar['high'] >= tp
        else:
            hs = bar['high'] >= sl
            ht = bar['low'] <= tp
        if hs and ht:
            return {'outcome': 'SL', 'r': -1.0}
        if hs:
            return {'outcome': 'SL', 'r': -1.0}
        if ht:
            return {'outcome': 'TP', 'r': rr}
    return {'outcome': 'TIMEOUT', 'r': 0.0}

def evaluate_candidates(candidates, base_frame, rr, threshold, max_trades, market, start_ts, end_ts):
    eligible_days = set()
    traded_days = set()
    trades = []
    day_counts = defaultdict(int)
    cands_by_day = defaultdict(list)
    for c in candidates:
        if not (start_ts <= c['ts'] < end_ts):
            continue
        if c['score'] < threshold:
            continue
        day = c['day']
        eligible_days.add(day)
        cands_by_day[day].append(c)
    for day in sorted(eligible_days):
        day_cands = sorted(cands_by_day[day], key=lambda x: x['score'], reverse=True)
        count = 0
        for c in day_cands:
            if count >= max_trades:
                break
            res = simulate_trade(base_frame, c, rr, market)
            if res:
                trades.append({**c, **res})
                count += 1
                day_counts[day] += 1
        if count > 0:
            traded_days.add(day)
    n = len(trades)
    tp = sum(1 for t in trades if t['outcome'] == 'TP')
    sl = sum(1 for t in trades if t['outcome'] == 'SL')
    to = sum(1 for t in trades if t['outcome'] == 'TIMEOUT')
    wr = 100.0 * tp / n if n else 0.0
    mean_r = statistics.mean([t['r'] for t in trades]) if n else -9.0
    return {'trades': n, 'daysTraded': len(traded_days), 'eligibleDays': len(eligible_days), 'coveragePct': round(100.0 * len(traded_days) / len(eligible_days), 2) if eligible_days else 0.0, 'tp': tp, 'sl': sl, 'timeout': to, 'winRate': round(wr, 2), 'meanR': round(mean_r, 4), 'maxTradesInDay': max(day_counts.values(), default=0)}

def stats_ok(s):
    return bool(s) and s.get('trades', 0) > 0 and s.get('coveragePct', 0) == 100.0 and s.get('maxTradesInDay', 99) <= 3 and s.get('winRate', 0) >= REQUIRED_WR and s.get('meanR', -9) > 0

def select_profile(symbol, market, candidates, base_frame, prior, dev_start, dev_end, val_start, val_end):
    best = None
    best_rank = None
    best_train = None
    for rr in ALLOWED_RR:
        for mt in MAX_TRADES_OPTIONS:
            for th in THRESHOLDS:
                st = evaluate_candidates(candidates, base_frame, rr, th, mt, market, dev_start, dev_end)
                if not stats_ok(st):
                    continue
                penalty = 0.0
                prr = prior.get('priorRR')
                if prr is not None:
                    try:
                        penalty = abs(rr - float(prr)) * 0.01
                    except Exception:
                        pass
                rank = (st['winRate'], st['meanR'], st['trades'], -th, -penalty)
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best = {'rr': rr, 'maxTradesPerDay': mt, 'threshold': th, 'market': market, 'baseTimeframe': BASE_TF[market]}
                    if prr is not None:
                        best['priorRR'] = prr
                    best_train = st
    if best is None:
        return None, None, None, False
    val_stats = evaluate_candidates(candidates, base_frame, best['rr'], best['threshold'], best['maxTradesPerDay'], market, val_start, val_end)
    return best, best_train, val_stats, stats_ok(val_stats)

def _run(symbol, market, rows, cache_dir, mode, profile=None):
    symbol = re.sub(r'[^A-Z0-9]', '', str(symbol).upper())
    if not rows:
        return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['DATA_UNAVAILABLE'], 'mode': mode}
    rows = sorted(rows, key=lambda r: int(r[0]))
    base_tf = BASE_TF.get(market)
    if base_tf is None:
        return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['UNKNOWN_MARKET'], 'mode': mode}
    base_sec = TF_SECONDS[base_tf]
    if len(rows) < MIN_BARS.get(base_tf, 1440):
        return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['INSUFFICIENT_DATA', 'bars=' + str(len(rows))], 'mode': mode}
    print('TF_BUILD', market, symbol, base_tf, len(rows), flush=True)
    candidates = build_or_load_candidates(symbol, market, rows, cache_dir)
    base_frame = Frame(base_tf, base_sec, rows)
    if not candidates:
        return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['NO_CANDIDATES'], 'mode': mode}
    t0 = int(rows[0][0])
    t1 = int(rows[-1][0]) + base_sec
    span = t1 - t0
    if span >= 240 * 86400:
        dev_end = t0 + 180 * 86400
        val_end = dev_end + 60 * 86400
    else:
        dev_end = t0 + int(span * 0.6)
        val_end = t0 + int(span * 0.8)
    if mode == 'fast':
        prior = load_registry_prior(symbol)
        print('TRAIN', symbol, flush=True)
        profile, train_stats, val_stats, pass_flag = select_profile(symbol, market, candidates, base_frame, prior, t0, dev_end, dev_end, val_end)
        if profile is None:
            return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['NO_DEV_PROFILE'], 'mode': mode}
        reasons = []
        if not pass_flag:
            reasons.append('VALIDATION_FAILED')
            if val_stats:
                if val_stats.get('winRate', 0) < REQUIRED_WR:
                    reasons.append('VALIDATION_WR_BELOW_80')
                if val_stats.get('coveragePct', 0) != 100:
                    reasons.append('VALIDATION_COVERAGE')
                if val_stats.get('meanR', -9) <= 0:
                    reasons.append('VALIDATION_NONPOSITIVE_EXPECTANCY')
        print('VALIDATE', symbol, json.dumps(val_stats, separators=(',', ':')), flush=True)
        result = {'symbol': symbol, 'market': market, 'pass': pass_flag, 'reasons': reasons, 'profile': profile, 'train': train_stats, 'validation': val_stats, 'mode': mode, 'dataHash': dcache.compute_data_hash(rows)}
        print('RESULT', symbol, 'PASS' if pass_flag else 'FAIL', val_stats.get('winRate') if val_stats else None, reasons, flush=True)
        return result
    if mode == 'final':
        if not profile:
            return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['NO_PROFILE'], 'mode': mode}
        print('OOS_TEST', symbol, flush=True)
        oos_stats = evaluate_candidates(candidates, base_frame, profile['rr'], profile['threshold'], profile['maxTradesPerDay'], market, val_end, t1)
        pass_flag = stats_ok(oos_stats)
        reasons = [] if pass_flag else ['OOS_FAILED']
        if oos_stats and not pass_flag:
            if oos_stats.get('winRate', 0) < REQUIRED_WR:
                reasons.append('OOS_WR_BELOW_80')
            if oos_stats.get('meanR', -9) <= 0:
                reasons.append('OOS_NONPOSITIVE_EXPECTANCY')
        result = {'symbol': symbol, 'market': market, 'pass': pass_flag, 'reasons': reasons, 'profile': profile, 'oos': oos_stats, 'mode': mode, 'dataHash': dcache.compute_data_hash(rows)}
        print('RESULT', symbol, 'PASS' if pass_flag else 'FAIL', oos_stats.get('winRate') if oos_stats else None, reasons, flush=True)
        return result
    return {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['UNKNOWN_MODE'], 'mode': mode}

def run_fast(symbol, market, rows, cache_dir=None):
    return _run(symbol, market, rows, cache_dir, 'fast')

def run_final(symbol, market, rows, cache_dir=None, profile=None):
    return _run(symbol, market, rows, cache_dir, 'final', profile)
