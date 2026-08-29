#!/usr/bin/env python3
"""Research-only progressive-lot backtest for XAUUSD and BTCUSDT.

Rules fixed by user:
- initial equity: $20
- start lot: 0.02; +0.01 after each true TP; cap 1.00
- stop only after the 1.00-lot trade reaches TP (99 TP stages total)
- one open position at a time per symbol
- wait one full M5 bar after each TP
- no stop loss; account is considered busted if mark-to-market equity <= 0
- XAUUSD TP distance: 3.00 price units
- BTCUSDT TP distance: 300.00 price units

This script deliberately separates optimization and untouched OOS validation.
It does not modify or interact with production trading code.
"""
from __future__ import annotations

import csv
import io
import math
import statistics
import urllib.request
from dataclasses import dataclass
from typing import Iterable

START_EQUITY = 20.0
START_LOT = 0.02
LOT_STEP = 0.01
MAX_LOT = 1.00
TARGET_TPS = int(round((MAX_LOT - START_LOT) / LOT_STEP)) + 1  # 99
COOLDOWN_BARS = 1

DATA = {
    "XAUUSD": {
        "url": "https://raw.githubusercontent.com/simom1/XAUUSD-history/main/TradingView_Deep_Datasets/OANDA_XAUUSD/OANDA_XAUUSD_5.csv",
        "tp": 3.0,
        "contract": 100.0,  # standard gold CFD convention; broker can differ
    },
    "BTCUSDT": {
        "url": "https://raw.githubusercontent.com/simom1/XAUUSD-history/main/TradingView_Deep_Datasets/BINANCE_BTCUSDT/BINANCE_BTCUSDT_5.csv",
        "tp": 300.0,
        "contract": 1.0,  # normalized 1 BTC per lot convention; MT5 broker can differ
    },
}

@dataclass
class Bar:
    ts: int
    dt: str
    o: float
    h: float
    l: float
    c: float

@dataclass(frozen=True)
class Config:
    kind: str
    fast: int
    slow: int
    lookback: int
    threshold: float

@dataclass
class Result:
    symbol: str
    config: Config
    tps: int
    finished: bool
    busted: bool
    equity: float
    max_dd_pct: float
    max_adverse_price: float
    bars_held_max: int
    last_lot: float
    last_time: str
    trades: int


def download(url: str) -> list[Bar]:
    req = urllib.request.Request(url, headers={"User-Agent": "trading-api-research-backtest"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    rows = []
    for x in csv.DictReader(io.StringIO(text)):
        try:
            rows.append(Bar(int(float(x["timestamp"])), x["datetime"], float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"])))
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda b: b.ts)
    return rows


def ema(values: list[float], n: int) -> list[float]:
    if not values: return []
    a = 2.0 / (n + 1.0)
    out = [values[0]]
    for v in values[1:]: out.append(a * v + (1-a) * out[-1])
    return out


def rsi(values: list[float], n: int = 14) -> list[float]:
    out = [50.0] * len(values)
    if len(values) <= n: return out
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i-1]
        gains.append(max(d, 0.0)); losses.append(max(-d, 0.0))
    ag = sum(gains[:n])/n; al = sum(losses[:n])/n
    out[n] = 100.0 if al == 0 else 100 - 100/(1 + ag/al)
    for i in range(n+1, len(values)):
        ag = (ag*(n-1)+gains[i-1])/n; al = (al*(n-1)+losses[i-1])/n
        out[i] = 100.0 if al == 0 else 100 - 100/(1 + ag/al)
    return out


def atr(bars: list[Bar], n: int = 14) -> list[float]:
    tr = []
    for i,b in enumerate(bars):
        prev = bars[i-1].c if i else b.c
        tr.append(max(b.h-b.l, abs(b.h-prev), abs(b.l-prev)))
    out = [tr[0] if tr else 0.0] * len(tr)
    if not tr: return out
    s=0.0
    for i,x in enumerate(tr):
        if i<n:
            s += x; out[i]=s/(i+1)
        elif i==n:
            s=sum(tr[i-n+1:i+1]); out[i]=s/n
        else:
            out[i]=(out[i-1]*(n-1)+x)/n
    return out


def signal_at(i: int, bars: list[Bar], cfg: Config, ef: list[float], es: list[float], rr: list[float], aa: list[float]) -> int:
    if i < max(cfg.slow, cfg.lookback, 15): return 0
    b = bars[i]
    prev = bars[i-1]
    vol_ok = aa[i] > 0 and abs(b.c-prev.c) / aa[i] >= cfg.threshold
    if cfg.kind == "trend":
        if ef[i] > es[i] and b.c > ef[i] and rr[i] >= 52 and vol_ok: return 1
        if ef[i] < es[i] and b.c < ef[i] and rr[i] <= 48 and vol_ok: return -1
    elif cfg.kind == "breakout":
        hi=max(x.h for x in bars[i-cfg.lookback:i]); lo=min(x.l for x in bars[i-cfg.lookback:i])
        if b.c > hi and ef[i] > es[i]: return 1
        if b.c < lo and ef[i] < es[i]: return -1
    elif cfg.kind == "pullback":
        # trend continuation after a one-bar retrace/rejection around fast EMA
        if ef[i] > es[i] and prev.l <= ef[i-1] and b.c > prev.h and rr[i] >= 50: return 1
        if ef[i] < es[i] and prev.h >= ef[i-1] and b.c < prev.l and rr[i] <= 50: return -1
    elif cfg.kind == "meanrev":
        z = (b.c-ef[i]) / max(aa[i], 1e-9)
        if z <= -cfg.threshold and rr[i] <= 35: return 1
        if z >= cfg.threshold and rr[i] >= 65: return -1
    return 0


def simulate(symbol: str, bars: list[Bar], cfg: Config, start: int, end: int) -> Result:
    meta=DATA[symbol]; tpdist=meta["tp"]; contract=meta["contract"]
    closes=[b.c for b in bars]
    ef=ema(closes,cfg.fast); es=ema(closes,cfg.slow); rr=rsi(closes,14); aa=atr(bars,14)
    equity=START_EQUITY; peak=equity; maxdd=0.0; max_adv=0.0; tps=0; trades=0; cooldown_until=start
    pos=None; bars_held=0; bars_held_max=0; last_time=bars[start].dt if start < len(bars) else ""
    lot=START_LOT
    # enter from a signal on the completed previous bar, at current bar open -> no lookahead
    for i in range(max(start, cfg.slow+2), min(end,len(bars))):
        b=bars[i]
        if pos is None:
            if i <= cooldown_until: continue
            sig=signal_at(i-1,bars,cfg,ef,es,rr,aa)
            if sig:
                pos={"dir":sig,"entry":b.o,"lot":lot,"entry_i":i}
                trades += 1
            continue
        d=pos["dir"]; entry=pos["entry"]; L=pos["lot"]
        bars_held=i-pos["entry_i"]+1; bars_held_max=max(bars_held_max,bars_held)
        target=entry + d*tpdist
        # Conservative same-bar solvency rule: adverse extreme is evaluated before crediting TP.
        adverse=(entry-b.l) if d>0 else (b.h-entry)
        adverse=max(0.0, adverse); max_adv=max(max_adv, adverse)
        floating_equity=equity - adverse*contract*L
        dd=(peak-floating_equity)/peak if peak>0 else 1.0; maxdd=max(maxdd,dd)
        if floating_equity <= 0:
            return Result(symbol,cfg,tps,False,True,0.0,maxdd*100,max_adv,bars_held_max,L,b.dt,trades)
        hit=(b.h>=target) if d>0 else (b.l<=target)
        if hit:
            equity += tpdist*contract*L
            peak=max(peak,equity); tps += 1; last_time=b.dt
            if L >= MAX_LOT-1e-9:
                return Result(symbol,cfg,tps,True,False,equity,maxdd*100,max_adv,bars_held_max,L,b.dt,trades)
            lot=round(min(MAX_LOT,L+LOT_STEP)+1e-12,2)
            pos=None; cooldown_until=i+COOLDOWN_BARS
    return Result(symbol,cfg,tps,False,False,equity,maxdd*100,max_adv,bars_held_max,lot,last_time,trades)


def configs() -> Iterable[Config]:
    for f,s in [(5,20),(8,21),(9,30),(12,36),(20,50),(20,100)]:
        for th in [0.0,0.15,0.30,0.50]: yield Config("trend",f,s,10,th)
    for f,s in [(5,20),(8,21),(12,36),(20,50)]:
        for lb in [5,8,12,20,30]: yield Config("breakout",f,s,lb,0.0)
    for f,s in [(5,20),(8,21),(12,36),(20,50)]: yield Config("pullback",f,s,10,0.0)
    for f in [10,20,30]:
        for z in [0.8,1.0,1.2,1.5,2.0]: yield Config("meanrev",f,max(f+1,50),10,z)


def score(r: Result) -> tuple:
    # Completion dominates, then progression; lower DD breaks ties.
    return (1 if r.finished else 0, r.tps, -r.max_dd_pct, -r.bars_held_max)


def main():
    print("=== MT5 PROGRESSIVE TP RESEARCH BACKTEST ===")
    print(f"Rules: equity=${START_EQUITY:.2f}, lot {START_LOT:.2f}->{MAX_LOT:.2f} +{LOT_STEP:.2f}/TP, required_TPs={TARGET_TPS}, cooldown=M5 x {COOLDOWN_BARS}")
    print("TP: XAUUSD=3.00 price | BTCUSDT=300.00 price | NO SL")
    print("Solvency: conservative intrabar adverse-extreme mark-to-market, equity<=0 => BUST")
    print("NOTE: XAU contract=100 oz/lot; BTC normalized=1 BTC/lot. Broker margin/spread/commission/swap are not in source OHLC.\n")

    for symbol in ("XAUUSD","BTCUSDT"):
        bars=download(DATA[symbol]["url"])
        n=len(bars); cut1=int(n*0.65); cut2=int(n*0.85)
        print(f"[{symbol}] bars={n} range={bars[0].dt} -> {bars[-1].dt}")
        print(f"  train=[0,{cut1}) validation=[{cut1},{cut2}) OOS=[{cut2},{n})")

        # Phase 1: choose on training. To give 99-stage progression enough runway,
        # evaluate from train start through validation end but rank train-only robustness first.
        candidates=[]
        for c in configs():
            tr=simulate(symbol,bars,c,0,cut1)
            va=simulate(symbol,bars,c,cut1,cut2)
            # hard reject train busts; prefer configs that survive both regions
            robust=(0 if tr.busted else 1, 0 if va.busted else 1, tr.tps+va.tps, min(tr.tps,va.tps), -max(tr.max_dd_pct,va.max_dd_pct))
            candidates.append((robust,c,tr,va))
        candidates.sort(key=lambda x:x[0], reverse=True)

        print("  top optimization candidates:")
        for rank,(sc,c,tr,va) in enumerate(candidates[:5],1):
            print(f"   {rank}. {c} | train TP={tr.tps} bust={tr.busted} DD={tr.max_dd_pct:.1f}% | val TP={va.tps} bust={va.busted} DD={va.max_dd_pct:.1f}%")

        # OOS is touched once for the selected candidate only.
        best=candidates[0][1]
        oos=simulate(symbol,bars,best,cut2,n)
        full=simulate(symbol,bars,best,0,n)
        print(f"  SELECTED={best}")
        print(f"  UNTOUCHED_OOS: TP={oos.tps}/{TARGET_TPS} finished={oos.finished} bust={oos.busted} equity=${oos.equity:.2f} maxDD={oos.max_dd_pct:.1f}% lastLot={oos.last_lot:.2f}")
        print(f"  FULL_PATH: TP={full.tps}/{TARGET_TPS} finished={full.finished} bust={full.busted} equity=${full.equity:.2f} maxDD={full.max_dd_pct:.1f}% maxAdversePrice={full.max_adverse_price:.2f} maxHoldBars={full.bars_held_max} lastLot={full.last_lot:.2f} lastTime={full.last_time}")

        # Also show oracle diagnostic across all configs on full data, explicitly NOT validation.
        # This tells us whether the searched family contains any path to 1.00 without pretending OOS validity.
        diag=[]
        for c in configs(): diag.append(simulate(symbol,bars,c,0,n))
        diag.sort(key=score,reverse=True)
        d=diag[0]
        print(f"  SEARCH_DIAGNOSTIC_BEST_FULL (NOT OOS): {d.config} TP={d.tps}/{TARGET_TPS} finished={d.finished} bust={d.busted} equity=${d.equity:.2f} DD={d.max_dd_pct:.1f}%")
        print()

if __name__ == "__main__":
    main()
