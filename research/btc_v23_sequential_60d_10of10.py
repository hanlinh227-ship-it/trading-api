#!/usr/bin/env python3
"""BTC V23 — sequential 10/10 progressive-lot backtest.

User-locked rules:
- BTC only, trade 24/7 (no session filter)
- start balance $20, 0.02 lot -> 1.00 lot, +0.01 after TP only
- TP = 300 BTC price units
- no SL, no Smart Cut, no trailing, no timeout close
- one open position at a time
- after TP, skip one complete M5 bar (conservative >=5 minutes)
- block NEW entries from 15 minutes before until 15 minutes after major scheduled USD news
- one random historical window at a time; no TRAIN/HOLDOUT and no parallel 10-window fitting
- a test PASS requires full 99/99 chain through the 1.00-lot TP within <=60 days
- tune only on the current window, carry the selected method forward, then advance to the next window
- final target = 10 sequential PASS results. Anything less is FAIL.

Important: the 60-day boundary is an evaluation boundary only. It never force-closes a trade.
Historical CSV timestamps are parsed as UTC by the existing BTC loader.
"""
from __future__ import annotations
import argparse, os, random, sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_xau_btc_v21_vwap_unbounded as v21
import dual_xau_btc_v22_target99_adaptive as v22
import mt5_progressive_tp_backtest_v8 as b8

MAX_DAYS = 60.0
TARGET_TP = 99
TP_PRICE = 300.0
START_BAL = 20.0
LOT0 = 0.02
NEWS_GUARD_MIN = 15

@dataclass
class Result:
    tps:int; done:bool; bust:bool; reason:str; balance:float; dd:float
    trades:int; hold:int; lot:float; when:str; days:float; cfg:object

# Major scheduled USD releases in the available 2026 sample.
# BLS/BEA 08:30 ET releases are converted to UTC; FOMC decisions use 14:00 ET.
# March 6 is before US DST (13:30 UTC); subsequent 08:30 releases are 12:30 UTC.
NEWS_UTC = [
    # Employment Situation / NFP
    '2026-03-06 13:30:00','2026-04-03 12:30:00','2026-05-08 12:30:00',
    '2026-06-05 12:30:00','2026-07-02 12:30:00','2026-08-07 12:30:00',
    # CPI
    '2026-03-11 12:30:00','2026-04-10 12:30:00','2026-05-12 12:30:00',
    '2026-06-10 12:30:00','2026-07-14 12:30:00','2026-08-12 12:30:00',
    # PCE / Personal Income and Outlays and major GDP releases
    '2026-03-13 12:30:00','2026-04-09 12:30:00','2026-04-30 12:30:00',
    '2026-05-28 12:30:00','2026-06-25 12:30:00','2026-07-30 12:30:00',
    '2026-08-26 12:30:00',
    # FOMC statement decisions
    '2026-03-18 18:00:00','2026-04-29 18:00:00','2026-06-17 18:00:00','2026-07-29 18:00:00',
]
NEWS_TS = [int(datetime.strptime(x,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()) for x in NEWS_UTC]
NEWS_GUARD_SEC = NEWS_GUARD_MIN * 60

def blocked_by_news(ts:int)->bool:
    return any(abs(ts-n) <= NEWS_GUARD_SEC for n in NEWS_TS)

def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID'); att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit(): return int(rid)*100+int(att)
    return 230001

def window_starts(bars,seed,n=10):
    # Sequential independent starts with full 60d + indicator warmup available.
    warm=700; bars60=int(MAX_DAYS*24*12)
    hi=len(bars)-bars60-3
    if hi<=warm: raise RuntimeError('not enough BTC history for 60d windows')
    rng=random.Random(seed)
    candidates=list(range(warm,hi))
    rng.shuffle(candidates)
    out=[]
    min_gap=12*24*5  # prefer starts at least 5 days apart without requiring disjoint windows
    for s in candidates:
        if all(abs(s-x)>=min_gap for x in out):
            out.append(s)
            if len(out)==n:return sorted(out)
    return sorted(candidates[:n])

def run_window(b,c,I):
    bal=START_BAL; peak=START_BAL; dd=0.; lot=LOT0; tps=tr=mh=0
    pos=None; cool=-1; st=v21.DT(b[0].dt); when=b[0].dt
    deadline=st+timedelta(days=MAX_DAYS)
    for i in range(652,len(b)):
        z=b[i]; now=v21.DT(z.dt)
        if now>deadline:
            return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,(now-st).total_seconds()/86400,c)
        if pos is None:
            if i<=cool: continue
            # signal is based on the previous closed bar; order is placed at current bar open.
            # Block only NEW entries around scheduled high-impact news; an existing trade is untouched.
            if blocked_by_news(z.ts): continue
            d=v22.signal('BTC',i-1,b,c,I,bal,lot)
            if not d: continue
            pos=(d,z.o,lot,i); tr+=1
        d,en,L,ei=pos; mh=max(mh,i-ei+1)
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-adverse*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:
            return Result(tps,False,True,'BUST',0.,dd*100,tr,mh,L,z.dt,(now-st).total_seconds()/86400,c)
        tar=en+d*TP_PRICE; hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=TP_PRICE*L; peak=max(peak,bal); tps+=1; when=z.dt
            if L>=1.-1e-9:
                return Result(tps,tps==TARGET_TP,False,'PASS99' if tps==TARGET_TP else 'CHAIN_ERROR',bal,dd*100,tr,mh,L,z.dt,(now-st).total_seconds()/86400,c)
            lot=round(L+.01,2); pos=None
            # Skip one complete M5 bar after the TP bar; conservative >=5m separation.
            cool=i+1
    return Result(tps,False,False,'DATA_END',bal,dd*100,tr,mh,lot,when,(v21.DT(b[-1].dt)-st).total_seconds()/86400,c)

def rank(r):
    # Full completion dominates; then favor more progress, survival, lower DD and faster execution.
    return (1 if r.done and r.days<=MAX_DAYS else 0, r.tps, 0 if r.bust else 1, -r.dd, -r.days, -r.hold)

def candidate_configs(current=None):
    # BTC-specific V22 family: VWAP anti-FOMO, sweep/retest/compression and momentum after value pullback.
    # Keep search finite enough to tune one window at a time.
    cs=list(v22.cfgs('BTC'))
    if current is not None:
        # Carry-forward config is always tested first.
        yield current
    for c in cs:
        if c!=current: yield c

def tune_one_window(b,I,current,test_no):
    # First try the method carried from the previous successful window.
    if current is not None:
        r=run_window(b,current,I)
        print(f'TEST{test_no:02d} CARRY TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}%',flush=True)
        if r.done and r.days<=MAX_DAYS:return current,r,1
    best=None; bestc=None; n=0
    for c in candidate_configs(None):
        n+=1; r=run_window(b,c,I)
        if best is None or rank(r)>rank(best): best,bestc=r,c
        if r.done and r.days<=MAX_DAYS:
            print(f'TEST{test_no:02d} PASS_FOUND configs={n} days={r.days:.2f} DD={r.dd:.2f}% cfg={c}',flush=True)
            return c,r,n
        if n%1000==0:
            print(f'TEST{test_no:02d} TUNE {n} bestTP={best.tps}/99 reason={best.reason} DD={best.dd:.2f}%',flush=True)
    print(f'TEST{test_no:02d} NO_PASS configs={n} bestTP={best.tps}/99 reason={best.reason} days={best.days:.2f} DD={best.dd:.2f}% cfg={bestc}',flush=True)
    return bestc,best,n

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--seed',type=int); a=ap.parse_args()
    seed=seed_value(a.seed); bars=b8.load(); starts=window_starts(bars,seed,10)
    print('=== BTC V23 SEQUENTIAL 60D / TARGET 10 OF 10 ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)}',flush=True)
    print('RULES BTC-only 24/7 TP300 noSL noCut onePosition cooldown>=5m newsGuard=+-15m maxDays=60 target=99/99',flush=True)
    print('STARTS',[bars[s].dt for s in starts],flush=True)
    current=None; passed=0; results=[]
    for j,s in enumerate(starts,1):
        # One window only. It is tuned and resolved before the next window is opened.
        end=min(len(bars),s+int(MAX_DAYS*24*12)+700)
        w=bars[s:end]; I=v21.prep(w)
        c,r,tries=tune_one_window(w,I,current,j)
        results.append((s,c,r,tries))
        ok=r.done and r.tps==99 and r.days<=MAX_DAYS
        if ok:
            passed+=1; current=c
            print(f'BTC_TEST{j:02d}=PASS start={bars[s].dt} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when} tries={tries}',flush=True)
        else:
            print(f'BTC_TEST{j:02d}=FAIL start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when} tries={tries}',flush=True)
            print(f'BTC_FINAL PASS={passed}/{j} TARGET10=False STOP_REASON=WINDOW_{j}_NO_60D_PASS',flush=True)
            return 2
    print(f'BTC_FINAL PASS={passed}/10 TARGET10={passed==10} FINAL_CFG={current}',flush=True)
    return 0 if passed==10 else 2

if __name__=='__main__':sys.exit(main())
