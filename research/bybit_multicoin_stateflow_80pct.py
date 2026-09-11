#!/usr/bin/env python3
"""
Bybit multi-coin StateFlow calibration backtest (research only).

Calibrates one independent profile per Bybit core symbol using reproducible
historical OHLCV. Historical candles are NOT treated as L2/taker-flow/
liquidation/OI replay; those live StateFlow layers require separate replay or
forward-paper validation.

Rules:
- fully closed 15m signal bar; entry at next-bar open
- no position overlap within a symbol
- same-bar TP+SL ambiguity => SL first
- fees/slippage included
- disjoint DEV and OOS
- OOS = 3 untouched sequential 50-day windows
- PASS requires aggregate OOS WR >=80%, worst window >=70%, >=60 OOS trades,
  >=20 trades/window, positive expectancy and positive net-R in every window
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import itertools
import json
import math
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

UNIVERSE = [
    "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","SOLUSDT","TRXUSDT",
    "DOGEUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT","BCHUSDT",
    "XLMUSDT","DOTUSDT","NEARUSDT","UNIUSDT","AAVEUSDT","HBARUSDT",
]
BASE = "https://data-api.binance.vision/api/v3/klines"
INTERVAL = "15m"
INTERVAL_MS = 15 * 60 * 1000
DAY_MS = 24 * 60 * 60 * 1000
HISTORY_DAYS = 520
OOS_WINDOW_DAYS = 50
OOS_WINDOWS = 3
DEV_DAYS = 300
BASE_COST_BPS = 13.0
MIN_DEV_TRADES = 80
MIN_OOS_TRADES = 60
MIN_WINDOW_TRADES = 20
TARGET_WR = 0.80
WORST_WINDOW_FLOOR = 0.70

@dataclass(frozen=True)
class Bar:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

@dataclass(frozen=True)
class Cfg:
    family: str
    sep_atr: float
    eff_min: float
    vol_min: float
    stop_atr: float
    rr: float
    max_hold: int
    trigger: float

@dataclass
class Stats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    timeouts: int = 0
    net_r: float = 0.0
    gross_r: float = 0.0
    max_dd_r: float = 0.0
    max_consecutive_losses: int = 0
    longs: int = 0
    shorts: int = 0
    long_wins: int = 0
    short_wins: int = 0
    costs_r: float = 0.0

    @property
    def wr(self):
        return self.wins / self.trades if self.trades else 0.0

    @property
    def expectancy(self):
        return self.net_r / self.trades if self.trades else 0.0

def _get_json(url: str, retries: int = 7):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bybit-multicoin-stateflow-calibration/1.0"})
            with urllib.request.urlopen(req, timeout=35) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(min(4.0, 0.3 * (2 ** n)))
    raise RuntimeError(f"fetch failed: {last}")

def iso(ts):
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_symbol(symbol: str, history_days: int = HISTORY_DAYS):
    now = int(time.time() * 1000)
    end = (now // INTERVAL_MS) * INTERVAL_MS - 1
    start = end - history_days * DAY_MS
    rows, cur = [], start
    while cur <= end:
        qs = urllib.parse.urlencode({"symbol": symbol, "interval": INTERVAL, "startTime": cur, "endTime": end, "limit": 1000})
        batch = _get_json(BASE + "?" + qs)
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + INTERVAL_MS
        if nxt <= cur:
            raise RuntimeError("pagination stalled")
        cur = nxt
        time.sleep(0.02)
    uniq = {int(x[0]): x for x in rows if start <= int(x[0]) <= end}
    xs = [uniq[k] for k in sorted(uniq)]
    bars = [Bar(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in xs]
    if len(bars) < 1000:
        raise RuntimeError(f"insufficient data: {len(bars)} bars")
    gaps = []
    for a, b in zip(bars, bars[1:]):
        if b.ts - a.ts != INTERVAL_MS:
            gaps.append((a.ts, b.ts))
    expected = (bars[-1].ts - bars[0].ts) // INTERVAL_MS + 1
    coverage = len(bars) / expected if expected else 0.0
    return bars, {
        "source": "BinanceSpotDataAPI", "symbol": symbol, "interval": INTERVAL,
        "first": iso(bars[0].ts), "last": iso(bars[-1].ts), "bars": len(bars),
        "expected": expected, "coverage": coverage, "gaps": len(gaps),
        "gap_examples": [(iso(a), iso(b)) for a, b in gaps[:8]],
    }

def ema(values, period):
    out = [math.nan] * len(values)
    if not values:
        return out
    alpha = 2.0 / (period + 1.0)
    x = values[0]
    out[0] = x
    for i in range(1, len(values)):
        x = alpha * values[i] + (1 - alpha) * x
        out[i] = x
    return out

def prep(bars):
    n = len(bars)
    closes = [b.c for b in bars]
    volumes = [b.v for b in bars]
    e20 = ema(closes, 20)
    e60 = ema(closes, 60)
    tr = [0.0] * n
    for i, b in enumerate(bars):
        if i == 0:
            tr[i] = b.h - b.l
        else:
            pc = bars[i-1].c
            tr[i] = max(b.h-b.l, abs(b.h-pc), abs(b.l-pc))
    atr = ema(tr, 14)
    vol_sma = [math.nan] * n
    q = deque(); s = 0.0
    for i, v in enumerate(volumes):
        q.append(v); s += v
        if len(q) > 20: s -= q.popleft()
        if len(q) == 20: vol_sma[i] = s / 20.0
    hi20 = [math.nan] * n; lo20 = [math.nan] * n
    for i in range(20, n):
        xs = bars[i-20:i]
        hi20[i] = max(x.h for x in xs); lo20[i] = min(x.l for x in xs)
    eff = [0.0] * n
    for i in range(20, n):
        net = abs(closes[i] - closes[i-20])
        path = sum(abs(closes[j] - closes[j-1]) for j in range(i-19, i+1))
        eff[i] = net / path if path > 0 else 0.0
    return {"e20": e20, "e60": e60, "atr": atr, "vol_sma": vol_sma, "hi20": hi20, "lo20": lo20, "eff": eff}

def signal(i, bars, I, c: Cfg):
    if i < 64 or i >= len(bars) - 1: return 0
    b, p = bars[i], bars[i-1]
    atr = I["atr"][i]
    if not math.isfinite(atr) or atr <= 0: return 0
    e20, e60 = I["e20"][i], I["e60"][i]
    sep = (e20 - e60) / atr
    eff = I["eff"][i]
    vs = I["vol_sma"][i]
    vr = b.v / vs if vs and math.isfinite(vs) and vs > 0 else 0.0
    cr = max(b.h - b.l, 1e-12)
    loc_long = (b.c - b.l) / cr; loc_short = (b.h - b.c) / cr
    if c.family == "TREND_PULLBACK":
        if eff < c.eff_min or vr < c.vol_min: return 0
        if sep >= c.sep_atr:
            touched = min(x.l for x in bars[i-3:i+1]) <= e20 + c.trigger * atr
            if touched and b.c > e20 and b.c > b.o and b.c >= p.c and loc_long >= 0.55: return 1
        if sep <= -c.sep_atr:
            touched = max(x.h for x in bars[i-3:i+1]) >= e20 - c.trigger * atr
            if touched and b.c < e20 and b.c < b.o and b.c <= p.c and loc_short >= 0.55: return -1
    elif c.family == "BREAKOUT":
        if eff < c.eff_min or vr < c.vol_min: return 0
        h20, l20 = I["hi20"][i], I["lo20"][i]
        if not math.isfinite(h20): return 0
        pad = c.trigger * atr
        if sep >= c.sep_atr and b.c > h20 + pad and loc_long >= 0.62: return 1
        if sep <= -c.sep_atr and b.c < l20 - pad and loc_short >= 0.62: return -1
    elif c.family == "MOMENTUM":
        if eff < c.eff_min or vr < c.vol_min: return 0
        mom = (b.c - bars[i-4].c) / atr
        if sep >= c.sep_atr and mom >= c.trigger and b.c > e20 and loc_long >= 0.64: return 1
        if sep <= -c.sep_atr and mom <= -c.trigger and b.c < e20 and loc_short >= 0.64: return -1
    elif c.family == "SWEEP_RECLAIM":
        if vr < c.vol_min: return 0
        h20, l20 = I["hi20"][i], I["lo20"][i]
        if not math.isfinite(h20): return 0
        reclaim = c.trigger * atr
        if b.l < l20 - reclaim and b.c > l20 and b.c > b.o and loc_long >= 0.58: return 1
        if b.h > h20 + reclaim and b.c < h20 and b.c < b.o and loc_short >= 0.58: return -1
    return 0

def _slice_indices(bars, start_ts, end_ts):
    lo = None; hi = None
    for i, b in enumerate(bars):
        if lo is None and b.ts >= start_ts: lo = i
        if b.ts <= end_ts: hi = i
    if lo is None or hi is None or hi <= lo: return None
    return lo, hi

def no_gap_in_range(bars, lo, hi):
    return all(bars[i].ts - bars[i-1].ts == INTERVAL_MS for i in range(lo+1, hi+1))

def run_range(bars, I, c: Cfg, lo: int, hi: int, cost_bps=BASE_COST_BPS, side=0, delay_bars=0):
    st = Stats(); equity = 0.0; peak = 0.0; loss_streak = 0
    i = max(lo, 64)
    while i < hi - 2:
        d = signal(i, bars, I, c)
        if side and d != side: i += 1; continue
        if not d: i += 1; continue
        entry_i = i + 1 + delay_bars
        if entry_i >= hi: break
        entry = bars[entry_i].o; atr = I["atr"][i]; stop_dist = c.stop_atr * atr
        if stop_dist <= 0 or stop_dist / entry < 0.0008: i += 1; continue
        stop = entry - d * stop_dist; tp = entry + d * c.rr * stop_dist
        cost_r = (cost_bps / 10000.0) * entry / stop_dist
        gross_r = None; timed_out = True; last_j = entry_i
        for j in range(entry_i, min(hi + 1, entry_i + c.max_hold + 1)):
            x = bars[j]; last_j = j
            hit_sl = x.l <= stop if d > 0 else x.h >= stop
            hit_tp = x.h >= tp if d > 0 else x.l <= tp
            if hit_sl: gross_r = -1.0; timed_out = False; break
            if hit_tp: gross_r = c.rr; timed_out = False; break
        if gross_r is None:
            x = bars[last_j]; gross_r = d * (x.c - entry) / stop_dist
        net_r = gross_r - cost_r
        st.trades += 1; st.gross_r += gross_r; st.net_r += net_r; st.costs_r += cost_r
        if d > 0: st.longs += 1
        else: st.shorts += 1
        if timed_out: st.timeouts += 1
        if net_r > 0:
            st.wins += 1
            if d > 0: st.long_wins += 1
            else: st.short_wins += 1
            loss_streak = 0
        else:
            st.losses += 1; loss_streak += 1
            st.max_consecutive_losses = max(st.max_consecutive_losses, loss_streak)
        equity += net_r; peak = max(peak, equity); st.max_dd_r = max(st.max_dd_r, peak - equity)
        i = last_j + 1
    return st

def merge(stats):
    out = Stats()
    for s in stats:
        for f in ("trades","wins","losses","timeouts","longs","shorts","long_wins","short_wins"):
            setattr(out, f, getattr(out, f) + getattr(s, f))
        for f in ("net_r","gross_r","costs_r"):
            setattr(out, f, getattr(out, f) + getattr(s, f))
        out.max_dd_r = max(out.max_dd_r, s.max_dd_r)
        out.max_consecutive_losses = max(out.max_consecutive_losses, s.max_consecutive_losses)
    return out

def cfg_dict(c): return dataclasses.asdict(c)
def cfg_hash(c):
    raw = json.dumps(cfg_dict(c), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]

def candidate_grid():
    out = []
    for fam in ("TREND_PULLBACK","BREAKOUT","MOMENTUM","SWEEP_RECLAIM"):
        max_hold = 32 if fam in ("TREND_PULLBACK","SWEEP_RECLAIM") else 24
        triggers = {"TREND_PULLBACK": (0.08,0.20), "BREAKOUT": (0.00,0.08), "MOMENTUM": (0.35,0.65), "SWEEP_RECLAIM": (0.03,0.10)}[fam]
        for sep, eff, vol, stop, rr, trig in itertools.product((0.08,0.18),(0.18,0.30),(0.80,1.10),(0.80,1.10),(1.0,2.0),triggers):
            out.append(Cfg(fam, sep, eff, vol, stop, rr, max_hold, trig))
    return out

def score_dev(s: Stats):
    coverage = min(1.0, s.trades / MIN_DEV_TRADES)
    return (1 if s.trades >= MIN_DEV_TRADES else 0, 1 if s.expectancy > 0 else 0, s.wr * coverage, s.expectancy, -s.max_dd_r, s.trades)

def stats_dict(s):
    return {"trades":s.trades,"wins":s.wins,"losses":s.losses,"timeouts":s.timeouts,"win_rate":round(s.wr,6),"expectancy_r":round(s.expectancy,6),"net_r":round(s.net_r,4),"gross_r":round(s.gross_r,4),"costs_r":round(s.costs_r,4),"max_dd_r":round(s.max_dd_r,4),"max_consecutive_losses":s.max_consecutive_losses,"longs":s.longs,"shorts":s.shorts,"long_win_rate":round(s.long_wins/s.longs,6) if s.longs else None,"short_win_rate":round(s.short_wins/s.shorts,6) if s.shorts else None}

def calibrate_symbol(symbol, bars, manifest):
    I = prep(bars); end_ts = bars[-1].ts
    oos_span = OOS_WINDOWS * OOS_WINDOW_DAYS * DAY_MS
    oos_start = end_ts - oos_span + INTERVAL_MS
    dev_end = oos_start - INTERVAL_MS; dev_start = dev_end - DEV_DAYS * DAY_MS + INTERVAL_MS
    dev_idx = _slice_indices(bars, dev_start, dev_end)
    if not dev_idx: return {"symbol":symbol,"status":"DATA_UNAVAILABLE","reason":"no DEV range","manifest":manifest}
    if not no_gap_in_range(bars,*dev_idx): return {"symbol":symbol,"status":"DATA_GAP","reason":"DEV contains unresolved gap","manifest":manifest}
    windows = []
    for k in range(OOS_WINDOWS):
        st = oos_start + k*OOS_WINDOW_DAYS*DAY_MS; en = st + OOS_WINDOW_DAYS*DAY_MS - INTERVAL_MS
        idx = _slice_indices(bars,st,en)
        if not idx or not no_gap_in_range(bars,*idx): return {"symbol":symbol,"status":"DATA_GAP","reason":f"OOS window {k+1} missing/gapped","manifest":manifest}
        windows.append(idx)
    ranked = []
    for c in candidate_grid():
        s = run_range(bars,I,c,dev_idx[0],dev_idx[1]); ranked.append((score_dev(s),c,s))
    ranked.sort(key=lambda x:x[0],reverse=True)
    _,best,dev = ranked[0]
    oos_stats = [run_range(bars,I,best,lo,hi) for lo,hi in windows]
    agg = merge(oos_stats); worst_wr = min((s.wr for s in oos_stats),default=0.0)
    base_gate = agg.wr>=TARGET_WR and worst_wr>=WORST_WINDOW_FLOOR and agg.trades>=MIN_OOS_TRADES and all(s.trades>=MIN_WINDOW_TRADES for s in oos_stats) and agg.expectancy>0 and all(s.net_r>0 for s in oos_stats)
    stress15 = merge([run_range(bars,I,best,lo,hi,cost_bps=BASE_COST_BPS*1.5) for lo,hi in windows])
    stress20 = merge([run_range(bars,I,best,lo,hi,cost_bps=BASE_COST_BPS*2.0) for lo,hi in windows])
    delay = merge([run_range(bars,I,best,lo,hi,delay_bars=1) for lo,hi in windows])
    long_only = merge([run_range(bars,I,best,lo,hi,side=1) for lo,hi in windows])
    short_only = merge([run_range(bars,I,best,lo,hi,side=-1) for lo,hi in windows])
    stress_pass = stress15.expectancy>0 and stress20.expectancy>0 and delay.expectancy>0
    status = "LOCKED" if base_gate and stress_pass else "RESEARCH"
    reason = "PASS" if status=="LOCKED" else []
    if status!="LOCKED":
        if agg.wr<TARGET_WR: reason.append("OOS_WR_LT_80")
        if worst_wr<WORST_WINDOW_FLOOR: reason.append("WORST_WINDOW_LT_70")
        if agg.trades<MIN_OOS_TRADES: reason.append("OOS_TRADES_LT_60")
        if any(s.trades<MIN_WINDOW_TRADES for s in oos_stats): reason.append("WINDOW_TRADES_LT_20")
        if agg.expectancy<=0: reason.append("NONPOSITIVE_EXPECTANCY")
        if any(s.net_r<=0 for s in oos_stats): reason.append("NEGATIVE_WINDOW_R")
        if not stress_pass: reason.append("STRESS_FAIL")
    return {"symbol":symbol,"status":status,"reason":reason,"profile_version":"stateflow_ohlcv_cal_v1","profile_hash":cfg_hash(best),"method":best.family,"params":cfg_dict(best),"manifest":manifest,"dev_range":[iso(bars[dev_idx[0]].ts),iso(bars[dev_idx[1]].ts)],"dev":stats_dict(dev),"oos_windows":[{"range":[iso(bars[lo].ts),iso(bars[hi].ts)],**stats_dict(s)} for (lo,hi),s in zip(windows,oos_stats)],"oos_aggregate":stats_dict(agg),"worst_window_wr":round(worst_wr,6),"stress":{"cost_1_5x":stats_dict(stress15),"cost_2_0x":stats_dict(stress20),"entry_delay_1bar":stats_dict(delay),"long_only":stats_dict(long_only),"short_only":stats_dict(short_only),"pass":stress_pass},"gate":{"target_wr":TARGET_WR,"worst_window_floor":WORST_WINDOW_FLOOR,"min_oos_trades":MIN_OOS_TRADES,"min_window_trades":MIN_WINDOW_TRADES,"base_pass":base_gate,"locked":status=="LOCKED"},"limitations":["OHLCV baseline only","No historical L2/taker-flow/liquidation/OI replay in this run","Requires separate microstructure replay/forward-paper validation before production promotion"]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--symbols",default=",".join(UNIVERSE)); ap.add_argument("--out",default="research/results/bybit_multicoin_stateflow_80pct.json"); args=ap.parse_args()
    symbols=[x.strip().upper() for x in args.symbols.split(",") if x.strip()]; results=[]
    print("=== BYBIT MULTICOIN STATEFLOW 80% OOS CALIBRATION ===",flush=True)
    print(f"symbols={len(symbols)} interval={INTERVAL} history_days={HISTORY_DAYS} DEV={DEV_DAYS} OOS={OOS_WINDOWS}x{OOS_WINDOW_DAYS}d",flush=True)
    for n,symbol in enumerate(symbols,1):
        print(f"\n[{n}/{len(symbols)}] {symbol} loading...",flush=True)
        try:
            bars,manifest=load_symbol(symbol); print(f"DATA {symbol} bars={manifest['bars']} coverage={manifest['coverage']:.6f} gaps={manifest['gaps']} {manifest['first']}->{manifest['last']}",flush=True); r=calibrate_symbol(symbol,bars,manifest)
        except Exception as e: r={"symbol":symbol,"status":"ERROR","reason":repr(e)}
        results.append(r)
        if r.get("oos_aggregate"):
            a=r["oos_aggregate"]; print(f"RESULT {symbol} status={r['status']} method={r['method']} OOS_WR={100*a['win_rate']:.2f}% trades={a['trades']} ExpR={a['expectancy_r']:.4f} worst={100*r['worst_window_wr']:.2f}% profile={r['profile_hash']} reason={r['reason']}",flush=True)
        else: print(f"RESULT {symbol} status={r['status']} reason={r.get('reason')}",flush=True)
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"engine":"BYBIT_MULTICOIN_STATEFLOW_OHLCV_CAL_V1","research_only":True,"target":{"oos_wr":TARGET_WR,"worst_window_wr":WORST_WINDOW_FLOOR,"min_oos_trades":MIN_OOS_TRADES,"min_window_trades":MIN_WINDOW_TRADES},"universe":symbols,"locked":[r["symbol"] for r in results if r.get("status")=="LOCKED"],"unresolved":[r["symbol"] for r in results if r.get("status")!="LOCKED"],"results":results}
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n=== FINAL SUMMARY ===",flush=True)
    for r in results:
        if r.get("oos_aggregate"):
            a=r["oos_aggregate"]; print(f"{r['symbol']:10s} {r['status']:8s} WR={100*a['win_rate']:6.2f}% N={a['trades']:4d} ExpR={a['expectancy_r']:+.4f} method={r['method']}",flush=True)
        else: print(f"{r['symbol']:10s} {r['status']:8s} {r.get('reason')}",flush=True)
    print(f"LOCKED {len(summary['locked'])}/{len(symbols)} {summary['locked']}",flush=True); print(f"UNRESOLVED {len(summary['unresolved'])}/{len(symbols)} {summary['unresolved']}",flush=True); print(f"REPORT {out}",flush=True)

if __name__=="__main__": main()
