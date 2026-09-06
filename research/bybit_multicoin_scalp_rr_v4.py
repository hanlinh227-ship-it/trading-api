#!/usr/bin/env python3
"""Bybit MultiCoin Scalp RR V4 — research only.

Hard target:
- Bybit USDT linear perpetual native 5m candles.
- Per-symbol, per-direction profiles.
- Initial TP/SL RR is EXACTLY 1:1 or 1:2.
- Scalp frequency gate: large DEV/SHADOW/FINAL samples required.
- Closed-bar signal, next-bar entry, no overlap, same-bar SL/TP ambiguity => SL.
- Timeouts are NOT counted as wins even when their mark-to-market PnL is positive.
- DEV + SHADOW are used for method/parameter search; FINAL is evaluated once after
  the profile is frozen. FINAL is never used to mutate a profile inside this run.
- Historical OHLCV is not treated as L2/taker-flow/liquidation/OI replay.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
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
BASE = "https://api.bybit.com/v5/market/kline"
INTERVAL = "5"
INTERVAL_MS = 300_000
DAY_MS = 86_400_000
HISTORY_DAYS = 620
BASE_COST_BPS = 13.0
TARGET_WR = 0.80
WORST_FINAL_WR = 0.70
MIN_DEV_TRADES = 320
MIN_SHADOW_TRADES = 150
MIN_FINAL_TRADES = 220
MIN_FINAL_WINDOW_TRADES = 45
DEV_DAYS = 240
SHADOW_DAYS = 120
FINAL_WINDOW_DAYS = 45
FINAL_WINDOWS = 4
GAP_DAYS = 10

@dataclass(frozen=True)
class Bar:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

@dataclass(frozen=True)
class Profile:
    family: str
    side: int
    rr: int
    stop_atr: float
    p1: float
    p2: float
    vol_min: float
    trigger: float
    hold: int

@dataclass
class Stats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    timeouts: int = 0
    net_r: float = 0.0
    gross_r: float = 0.0
    costs_r: float = 0.0
    max_dd_r: float = 0.0
    max_consecutive_losses: int = 0
    longs: int = 0
    shorts: int = 0
    long_wins: int = 0
    short_wins: int = 0
    @property
    def wr(self):
        return self.wins / self.trades if self.trades else 0.0
    @property
    def exp(self):
        return self.net_r / self.trades if self.trades else 0.0
    @property
    def pf(self):
        return math.inf if self.losses == 0 and self.net_r > 0 else 0.0


def iso(ts):
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def getj(url, retries=8):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bybit-scalp-rr-v4/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                x = json.loads(r.read().decode())
            if int(x.get("retCode", -1)) != 0:
                raise RuntimeError(f"Bybit retCode={x.get('retCode')} retMsg={x.get('retMsg')}")
            return x
        except Exception as e:
            last = e
            time.sleep(min(5.0, 0.35 * (2 ** n)))
    raise RuntimeError(last)


def load(sym):
    now = int(time.time() * 1000)
    last_closed = (now // INTERVAL_MS) * INTERVAL_MS - INTERVAL_MS
    start = last_closed - HISTORY_DAYS * DAY_MS
    rows = {}
    cursor_end = last_closed + INTERVAL_MS - 1
    calls = 0
    while cursor_end >= start:
        chunk_start = max(start, cursor_end - 999 * INTERVAL_MS)
        q = urllib.parse.urlencode({
            "category": "linear", "symbol": sym, "interval": INTERVAL,
            "start": chunk_start, "end": cursor_end, "limit": 1000,
        })
        x = getj(BASE + "?" + q)
        batch = x.get("result", {}).get("list", []) or []
        calls += 1
        if not batch:
            cursor_end = chunk_start - 1
            continue
        earliest = None
        for z in batch:
            ts = int(z[0])
            if start <= ts <= last_closed:
                rows[ts] = z
                earliest = ts if earliest is None else min(earliest, ts)
        if earliest is None:
            cursor_end = chunk_start - 1
        else:
            if earliest <= start:
                break
            cursor_end = earliest - 1
        time.sleep(0.025)
    xs = [rows[k] for k in sorted(rows)]
    b = [Bar(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in xs]
    if len(b) < 100_000:
        raise RuntimeError(f"insufficient Bybit 5m history bars={len(b)}")
    gaps = [(a.ts, z.ts) for a, z in zip(b, b[1:]) if z.ts - a.ts != INTERVAL_MS]
    expected = (b[-1].ts - b[0].ts) // INTERVAL_MS + 1
    return b, {
        "source": "BybitV5Linear", "category": "linear", "symbol": sym,
        "interval": "5m", "first": iso(b[0].ts), "last": iso(b[-1].ts),
        "bars": len(b), "expected": expected, "coverage": len(b) / expected,
        "gaps": len(gaps), "gap_examples": [(iso(a), iso(z)) for a, z in gaps[:10]],
        "api_calls": calls,
    }


def ema(xs, p):
    a = 2.0 / (p + 1)
    out = [math.nan] * len(xs)
    v = xs[0]
    out[0] = v
    for i in range(1, len(xs)):
        v = a * xs[i] + (1 - a) * v
        out[i] = v
    return out


def prep(b):
    n = len(b)
    c = [x.c for x in b]
    e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    tr = [0.0] * n
    gains = [0.0] * n
    losses = [0.0] * n
    for i, x in enumerate(b):
        tr[i] = x.h - x.l if i == 0 else max(x.h - x.l, abs(x.h - b[i-1].c), abs(x.l - b[i-1].c))
        if i:
            d = c[i] - c[i-1]
            gains[i] = max(0.0, d)
            losses[i] = max(0.0, -d)
    atr = ema(tr, 14)
    ag, al = ema(gains, 14), ema(losses, 14)
    rsi = [50.0] * n
    for i in range(n):
        if al[i] <= 1e-15:
            rsi[i] = 100.0 if ag[i] > 0 else 50.0
        else:
            rs = ag[i] / al[i]
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)

    vs = [math.nan] * n
    mean20 = [math.nan] * n
    sd20 = [math.nan] * n
    hi20 = [math.nan] * n
    lo20 = [math.nan] * n
    qv = deque(); sv = 0.0
    qc = deque(); sc = 0.0; sc2 = 0.0
    qh = deque(); ql = deque()
    for i, x in enumerate(b):
        qv.append(x.v); sv += x.v
        qc.append(x.c); sc += x.c; sc2 += x.c * x.c
        qh.append(x.h); ql.append(x.l)
        if len(qv) > 20: sv -= qv.popleft()
        if len(qc) > 20:
            z = qc.popleft(); sc -= z; sc2 -= z * z
            qh.popleft(); ql.popleft()
        if len(qv) == 20:
            vs[i] = sv / 20.0
        if len(qc) == 20:
            m = sc / 20.0
            mean20[i] = m
            sd20[i] = math.sqrt(max(0.0, sc2 / 20.0 - m * m))
            # Excluding current bar prevents look-ahead breakout references.
            if i >= 20:
                z = b[i-20:i]
                hi20[i] = max(y.h for y in z)
                lo20[i] = min(y.l for y in z)

    eff = [0.0] * n
    mom3 = [0.0] * n
    for i in range(20, n):
        path = sum(abs(c[j] - c[j-1]) for j in range(i-11, i+1)) if i >= 12 else 0.0
        eff[i] = abs(c[i] - c[i-12]) / path if path else 0.0
        a = max(atr[i], 1e-12)
        if i >= 3:
            mom3[i] = (c[i] - c[i-3]) / a
    return {"e9":e9,"e21":e21,"e50":e50,"atr":atr,"rsi":rsi,"vs":vs,
            "mean20":mean20,"sd20":sd20,"hi20":hi20,"lo20":lo20,
            "eff":eff,"mom3":mom3}


def signal(i, b, I, p):
    if i < 60 or i >= len(b)-2:
        return False
    x = b[i]; prev = b[i-1]
    a = I["atr"][i]
    if not math.isfinite(a) or a <= 0:
        return False
    vs = I["vs"][i]
    vr = x.v / vs if vs and math.isfinite(vs) and vs > 0 else 0.0
    if vr < p.vol_min:
        return False
    e9,e21,e50 = I["e9"][i],I["e21"][i],I["e50"][i]
    sep = p.side * (e21 - e50) / a
    eff = I["eff"][i]
    rsi = I["rsi"][i]
    hi,lo = I["hi20"][i],I["lo20"][i]
    m,sd = I["mean20"][i],I["sd20"][i]
    cr = max(x.h - x.l, 1e-12)
    loc = (x.c - x.l) / cr if p.side > 0 else (x.h - x.c) / cr
    bull = x.c > x.o and x.c >= prev.c
    bear = x.c < x.o and x.c <= prev.c
    dirbar = bull if p.side > 0 else bear
    mom = p.side * I["mom3"][i]

    if p.family == "TREND_PULLBACK":
        if sep < p.p1 or eff < p.p2 or not dirbar or loc < p.trigger:
            return False
        touched = min(z.l for z in b[i-3:i+1]) <= e21 + 0.12*a if p.side > 0 else max(z.h for z in b[i-3:i+1]) >= e21 - 0.12*a
        aligned = e9 > e21 > e50 if p.side > 0 else e9 < e21 < e50
        return touched and aligned and (x.c > e21 if p.side > 0 else x.c < e21)

    if p.family == "BREAKOUT":
        if not math.isfinite(hi) or sep < p.p1 or eff < p.p2 or loc < p.trigger:
            return False
        return x.c > hi + 0.04*a if p.side > 0 else x.c < lo - 0.04*a

    if p.family == "BREAK_RETEST":
        if not math.isfinite(hi) or sep < p.p1 or eff < p.p2 or not dirbar or loc < p.trigger:
            return False
        if i < 3:
            return False
        if p.side > 0:
            broke = any(b[j].c > I["hi20"][j] + 0.03*I["atr"][j] for j in range(i-3,i) if math.isfinite(I["hi20"][j]))
            return broke and x.l <= hi + 0.15*a and x.c > hi
        broke = any(b[j].c < I["lo20"][j] - 0.03*I["atr"][j] for j in range(i-3,i) if math.isfinite(I["lo20"][j]))
        return broke and x.h >= lo - 0.15*a and x.c < lo

    if p.family == "SWEEP_RECLAIM":
        if not math.isfinite(hi) or not dirbar or loc < p.trigger:
            return False
        if p.side > 0:
            return x.l < lo - p.p1*a and x.c > lo and rsi <= p.p2
        return x.h > hi + p.p1*a and x.c < hi and rsi >= 100.0 - p.p2

    if p.family == "RANGE_FADE":
        if not math.isfinite(m) or not math.isfinite(sd) or sd <= 0 or eff > p.p1 or not dirbar:
            return False
        z = (x.c - m) / sd
        if p.side > 0:
            return z <= -p.p2 and rsi <= 42 and loc >= p.trigger
        return z >= p.p2 and rsi >= 58 and loc >= p.trigger

    if p.family == "MOMENTUM":
        aligned = e9 > e21 > e50 if p.side > 0 else e9 < e21 < e50
        return aligned and sep >= p.p1 and eff >= p.p2 and mom >= p.trigger and dirbar

    if p.family == "SQUEEZE_BREAKOUT":
        if not math.isfinite(hi) or not math.isfinite(sd) or sd <= 0:
            return False
        squeeze = sd / a <= p.p1
        if not squeeze or vr < p.p2:
            return False
        return x.c > hi and loc >= p.trigger if p.side > 0 else x.c < lo and loc >= p.trigger

    return False


def trade_from(i, b, I, p, hi, cost_bps=BASE_COST_BPS, delay=0):
    ei = i + 1 + delay
    if ei >= hi:
        return None
    entry = b[ei].o
    a = max(I["atr"][i], 1e-12)
    stopd = p.stop_atr * a
    if stopd / entry < 0.0006:
        return None
    side = p.side
    stop = entry - side * stopd
    target = entry + side * p.rr * stopd
    cost_r = (cost_bps / 10000.0) * entry / stopd
    last = ei
    for j in range(ei, min(hi + 1, ei + p.hold + 1)):
        x = b[j]; last = j
        # Conservative ambiguity: if both are touched in one candle, stop wins.
        hit_stop = x.l <= stop if side > 0 else x.h >= stop
        if hit_stop:
            return last, -1.0, -1.0 - cost_r, cost_r, "SL"
        hit_tp = x.h >= target if side > 0 else x.l <= target
        if hit_tp:
            return last, float(p.rr), float(p.rr) - cost_r, cost_r, "TP"
    gross = side * (b[last].c - entry) / stopd
    return last, gross, gross - cost_r, cost_r, "TIMEOUT"


def run_side(b, I, p, lo, hi, cost_bps=BASE_COST_BPS, delay=0):
    s = Stats(); eq = 0.0; peak = 0.0; streak = 0
    i = max(lo, 60)
    while i < hi - 2:
        if not signal(i,b,I,p):
            i += 1; continue
        t = trade_from(i,b,I,p,hi,cost_bps,delay)
        if not t:
            i += 1; continue
        last,g,n,c,outcome = t
        s.trades += 1; s.gross_r += g; s.net_r += n; s.costs_r += c
        if p.side > 0: s.longs += 1
        else: s.shorts += 1
        if outcome == "TP":
            s.wins += 1; streak = 0
            if p.side > 0: s.long_wins += 1
            else: s.short_wins += 1
        else:
            s.losses += 1; streak += 1; s.max_consecutive_losses = max(s.max_consecutive_losses, streak)
            if outcome == "TIMEOUT": s.timeouts += 1
        eq += n; peak = max(peak,eq); s.max_dd_r = max(s.max_dd_r, peak-eq)
        i = last + 1
    return s


def run_combo(b,I,lp,sp,lo,hi,cost_bps=BASE_COST_BPS,delay=0):
    s = Stats(); eq=0.0; peak=0.0; streak=0; i=max(lo,60)
    while i < hi-2:
        L = signal(i,b,I,lp) if lp else False
        S = signal(i,b,I,sp) if sp else False
        if L and S:
            i += 1; continue
        p = lp if L else sp if S else None
        if p is None:
            i += 1; continue
        t=trade_from(i,b,I,p,hi,cost_bps,delay)
        if not t:
            i += 1; continue
        last,g,n,c,outcome=t
        s.trades+=1; s.gross_r+=g; s.net_r+=n; s.costs_r+=c
        if p.side>0:s.longs+=1
        else:s.shorts+=1
        if outcome=="TP":
            s.wins+=1; streak=0
            if p.side>0:s.long_wins+=1
            else:s.short_wins+=1
        else:
            s.losses+=1; streak+=1; s.max_consecutive_losses=max(s.max_consecutive_losses,streak)
            if outcome=="TIMEOUT":s.timeouts+=1
        eq+=n; peak=max(peak,eq); s.max_dd_r=max(s.max_dd_r,peak-eq)
        i=last+1
    return s


def merge(xs):
    o=Stats()
    for s in xs:
        for f in ("trades","wins","losses","timeouts","longs","shorts","long_wins","short_wins"):
            setattr(o,f,getattr(o,f)+getattr(s,f))
        for f in ("net_r","gross_r","costs_r"):
            setattr(o,f,getattr(o,f)+getattr(s,f))
        o.max_dd_r=max(o.max_dd_r,s.max_dd_r)
        o.max_consecutive_losses=max(o.max_consecutive_losses,s.max_consecutive_losses)
    return o


def stats_dict(s):
    return {"trades":s.trades,"wins":s.wins,"losses":s.losses,"timeouts":s.timeouts,
            "win_rate":round(s.wr,6),"net_r":round(s.net_r,6),"gross_r":round(s.gross_r,6),
            "costs_r":round(s.costs_r,6),"expectancy_r":round(s.exp,6),
            "max_dd_r":round(s.max_dd_r,6),"max_consecutive_losses":s.max_consecutive_losses,
            "longs":s.longs,"shorts":s.shorts,"long_wins":s.long_wins,"short_wins":s.short_wins}


def profile_hash(p):
    return hashlib.sha256(json.dumps(dataclasses.asdict(p),sort_keys=True).encode()).hexdigest()[:16]


def base_candidates(side):
    out=[]
    for rr in (1,2):
        for stop in (0.75,1.0,1.25):
            for vol in (0.80,1.10):
                for sep in (0.12,0.28):
                    for eff in (0.18,0.32):
                        out.append(Profile("TREND_PULLBACK",side,rr,stop,sep,eff,vol,0.58,30))
                        out.append(Profile("BREAKOUT",side,rr,stop,sep,eff,vol,0.62,24))
                        out.append(Profile("BREAK_RETEST",side,rr,stop,sep,eff,vol,0.57,30))
                        out.append(Profile("MOMENTUM",side,rr,stop,sep,eff,vol,0.45,24))
                for sw in (0.02,0.08):
                    for rsi in (34.0,40.0):
                        out.append(Profile("SWEEP_RECLAIM",side,rr,stop,sw,rsi,vol,0.60,24))
                for meff in (0.22,0.34):
                    for z in (1.15,1.55):
                        out.append(Profile("RANGE_FADE",side,rr,stop,meff,z,vol,0.60,24))
                for sq in (0.85,1.10):
                    for burst in (1.0,1.25):
                        out.append(Profile("SQUEEZE_BREAKOUT",side,rr,stop,sq,burst,vol,0.62,24))
    # deterministic de-duplication
    u={profile_hash(p):p for p in out}
    return list(u.values())


def mutate(p):
    vals=[]
    for sm in (0.88,1.0,1.12):
        for vm in (-0.12,0.0,0.12):
            for tm in (-0.05,0.0,0.05):
                vals.append(dataclasses.replace(
                    p,
                    stop_atr=max(0.55,min(1.55,p.stop_atr*sm)),
                    vol_min=max(0.55,min(1.60,p.vol_min+vm)),
                    trigger=max(0.35,min(0.85,p.trigger+tm)),
                    hold=max(12,min(42,p.hold + (6 if sm>1 else -6 if sm<1 else 0))),
                ))
    u={profile_hash(x):x for x in vals}
    return list(u.values())


def idx(b, st, en):
    lo=next((i for i,x in enumerate(b) if x.ts>=st),None)
    hi=None
    for i in range(len(b)-1,-1,-1):
        if b[i].ts<=en:
            hi=i;break
    return None if lo is None or hi is None or hi<=lo else (lo,hi)


def clean(b,lo,hi):
    return all(b[j].ts-b[j-1].ts==INTERVAL_MS for j in range(lo+1,hi+1))


def split_block(b):
    # Shift only for data integrity, never based on P/L.
    for shift_days in range(0,61,5):
        final_end=b[-1].ts-shift_days*DAY_MS
        final_start=final_end-FINAL_WINDOWS*FINAL_WINDOW_DAYS*DAY_MS+INTERVAL_MS
        shadow_end=final_start-GAP_DAYS*DAY_MS-INTERVAL_MS
        shadow_start=shadow_end-SHADOW_DAYS*DAY_MS+INTERVAL_MS
        dev_end=shadow_start-GAP_DAYS*DAY_MS-INTERVAL_MS
        dev_start=dev_end-DEV_DAYS*DAY_MS+INTERVAL_MS
        di=idx(b,dev_start,dev_end); si=idx(b,shadow_start,shadow_end)
        if not di or not si or not clean(b,*di) or not clean(b,*si):
            continue
        fw=[]; good=True
        for k in range(FINAL_WINDOWS):
            st=final_start+k*FINAL_WINDOW_DAYS*DAY_MS
            en=st+FINAL_WINDOW_DAYS*DAY_MS-INTERVAL_MS
            z=idx(b,st,en)
            if not z or not clean(b,*z): good=False;break
            fw.append(z)
        if good:
            return di,si,fw,shift_days
    return None


def side_score(s):
    enough=s.trades>=120
    # Selection is economic first; WR target is not allowed to be manufactured by tiny sample.
    return (1 if enough else 0,1 if s.exp>0 else 0,s.wr,s.exp,-s.max_dd_r,s.trades)


def combo_score(dev,shadow):
    enough=dev.trades>=MIN_DEV_TRADES and shadow.trades>=MIN_SHADOW_TRADES
    robust=dev.exp>0 and shadow.exp>0
    # Strong pre-final target. FINAL remains untouched during this ranking.
    quality=min(dev.wr,shadow.wr)
    return (1 if enough and robust else 0,quality,(dev.wr+shadow.wr)/2.0,(dev.exp+shadow.exp)/2.0,-max(dev.max_dd_r,shadow.max_dd_r),shadow.trades)


def optimize(b,I,di,si):
    ranked={}
    for side in (1,-1):
        arr=[]
        for p in base_candidates(side):
            s=run_side(b,I,p,*di)
            arr.append((side_score(s),p,s))
        arr.sort(key=lambda x:x[0],reverse=True)
        # Two deterministic refinement generations around the current leaders.
        pool=[z[1] for z in arr[:6]]
        for _ in range(2):
            muts=[]
            for p in pool:
                muts.extend(mutate(p))
            scored=[]
            for p in {profile_hash(x):x for x in muts}.values():
                s=run_side(b,I,p,*di)
                scored.append((side_score(s),p,s))
            scored.sort(key=lambda x:x[0],reverse=True)
            arr=(arr+scored)
            arr.sort(key=lambda x:x[0],reverse=True)
            uniq=[];seen=set()
            for z in arr:
                h=profile_hash(z[1])
                if h not in seen:
                    seen.add(h);uniq.append(z)
            arr=uniq[:20]
            pool=[z[1] for z in arr[:6]]
        ranked[side]=arr

    combos=[]
    for lp in [z[1] for z in ranked[1][:6]]:
        for sp in [z[1] for z in ranked[-1][:6]]:
            dev=run_combo(b,I,lp,sp,*di)
            shadow=run_combo(b,I,lp,sp,*si)
            combos.append((combo_score(dev,shadow),lp,sp,dev,shadow))
    combos.sort(key=lambda x:x[0],reverse=True)
    return combos[0],ranked


def calibrate(sym,b,manifest):
    block=split_block(b)
    if not block:
        return {"symbol":sym,"status":"DATA_GAP","reason":"no clean deterministic V4 block","manifest":manifest}
    di,si,fw,shift_days=block
    I=prep(b)
    (_,lp,sp,dev,shadow), ranked=optimize(b,I,di,si)
    # Freeze profiles here. No FINAL metric is used above this line.
    fs=[run_combo(b,I,lp,sp,*z) for z in fw]
    agg=merge(fs); worst=min((x.wr for x in fs),default=0.0)
    st15=merge([run_combo(b,I,lp,sp,*z,cost_bps=BASE_COST_BPS*1.5) for z in fw])
    st20=merge([run_combo(b,I,lp,sp,*z,cost_bps=BASE_COST_BPS*2.0) for z in fw])
    delay=merge([run_combo(b,I,lp,sp,*z,delay=1) for z in fw])
    base=(agg.wr>=TARGET_WR and worst>=WORST_FINAL_WR and agg.trades>=MIN_FINAL_TRADES
          and all(x.trades>=MIN_FINAL_WINDOW_TRADES for x in fs)
          and agg.exp>0 and all(x.net_r>0 for x in fs))
    robust=st15.exp>0 and st20.exp>0 and delay.exp>0
    locked=base and robust
    reason=[]
    if agg.wr<TARGET_WR:reason.append("FINAL_WR_LT_80")
    if worst<WORST_FINAL_WR:reason.append("WORST_FINAL_WINDOW_LT_70")
    if agg.trades<MIN_FINAL_TRADES:reason.append("FINAL_TRADES_LT_220")
    if any(x.trades<MIN_FINAL_WINDOW_TRADES for x in fs):reason.append("FINAL_WINDOW_TRADES_LT_45")
    if agg.exp<=0:reason.append("NONPOSITIVE_EXPECTANCY")
    if any(x.net_r<=0 for x in fs):reason.append("NEGATIVE_FINAL_WINDOW_R")
    if not robust:reason.append("STRESS_FAIL")
    return {
        "symbol":sym,"status":"LOCKED" if locked else "RESEARCH",
        "reason":"PASS" if locked else reason,"profile_version":"scalp_rr_v4",
        "manifest":manifest,"data_gap_shift_days":shift_days,
        "long_profile":dataclasses.asdict(lp),"short_profile":dataclasses.asdict(sp),
        "long_profile_hash":profile_hash(lp),"short_profile_hash":profile_hash(sp),
        "rr_policy":"Each profile rr is exactly 1 or 2; TP distance = rr * initial SL distance",
        "win_definition":"Only full TP hit counts as a win; timeout never counts as win",
        "dev_range":[iso(b[di[0]].ts),iso(b[di[1]].ts)],"dev":stats_dict(dev),
        "shadow_range":[iso(b[si[0]].ts),iso(b[si[1]].ts)],"shadow":stats_dict(shadow),
        "final_windows":[{"range":[iso(b[z[0]].ts),iso(b[z[1]].ts)],**stats_dict(s)} for z,s in zip(fw,fs)],
        "final_aggregate":stats_dict(agg),"worst_final_window_wr":round(worst,6),
        "stress":{"cost_1_5x":stats_dict(st15),"cost_2_0x":stats_dict(st20),"entry_delay_1bar":stats_dict(delay),"pass":robust},
        "gate":{"target_wr":TARGET_WR,"worst_window_floor":WORST_FINAL_WR,
                "min_dev_trades":MIN_DEV_TRADES,"min_shadow_trades":MIN_SHADOW_TRADES,
                "min_final_trades":MIN_FINAL_TRADES,"min_final_window_trades":MIN_FINAL_WINDOW_TRADES,
                "base_pass":base,"locked":locked},
        "limitations":["Bybit 5m OHLCV only","No historical L2/taker-flow/liquidation/OI replay",
                       "Full StateFlow microstructure still requires replay/forward-paper before production"]
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default=",".join(UNIVERSE))
    ap.add_argument("--out",default="research/results/bybit_multicoin_scalp_rr_v4.json")
    a=ap.parse_args();syms=[x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    res=[]
    print("=== BYBIT MULTICOIN SCALP FIXED-RR V4 ===",flush=True)
    for n,sym in enumerate(syms,1):
        print(f"[{n}/{len(syms)}] {sym} load Bybit 5m linear",flush=True)
        try:
            b,m=load(sym)
            print(f"DATA {sym} bars={m['bars']} coverage={m['coverage']:.6f} gaps={m['gaps']} calls={m['api_calls']}",flush=True)
            r=calibrate(sym,b,m)
        except Exception as e:
            r={"symbol":sym,"status":"ERROR","reason":repr(e)}
        res.append(r)
        if r.get("final_aggregate"):
            x=r["final_aggregate"]
            print(f"RESULT {sym} {r['status']} FINAL_WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_final_window_wr']:.2f}% LONG={r['long_profile']['family']}/RR{r['long_profile']['rr']} SHORT={r['short_profile']['family']}/RR{r['short_profile']['rr']} DEV_WR={100*r['dev']['win_rate']:.2f}% SHADOW_WR={100*r['shadow']['win_rate']:.2f}% reason={r['reason']}",flush=True)
        else:
            print("RESULT",sym,r["status"],r.get("reason"),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"engine":"BYBIT_MULTICOIN_SCALP_RR_V4",
             "research_only":True,"universe":syms,"locked":[r["symbol"] for r in res if r.get("status")=="LOCKED"],
             "unresolved":[r["symbol"] for r in res if r.get("status")!="LOCKED"],"results":res}
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LOCKED",summary["locked"],flush=True);print("REPORT",out,flush=True)

if __name__=="__main__":
    main()
