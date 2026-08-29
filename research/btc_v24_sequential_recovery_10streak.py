#!/usr/bin/env python3
"""BTC V24 — sequential recovery backtest targeting 10 consecutive 60-day PASS windows.

Locked rules:
- BTC only, 24/7
- start $20, 0.02 -> 1.00, +0.01 after actual TP only
- TP = 300 BTC price units
- no SL / no Smart Cut / no trailing / no forced timeout close
- one open position at a time
- after TP there is NO extra cooldown; at M5 resolution the earliest truthful re-entry is
  the next M5 bar open, and only if the setup is still valid
- block NEW entries +/-15 minutes around major scheduled USD news
- one historical window is opened and resolved at a time; no TRAIN/HOLDOUT
- every window has a hard evaluation limit of 60 days and requires 99/99 TP including 1.00 lot
- if a window cannot reach 99/99, immediately move to another random window
- final target is 10 CONSECUTIVE PASS windows; any FAIL resets the streak to zero

V24 cadence change:
- preserves the V22 anti-FOMO logic as the primary signal
- adds a BTC-specific fast VWAP value-reclaim fallback near value, never at extreme extension
- reduces unnecessary post-TP delay while keeping one-position-only semantics
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

MAX_DAYS=60.0
TARGET_TP=99
TP_PRICE=300.0
START_BAL=20.0
LOT0=.02
NEWS_GUARD_MIN=15
TARGET_STREAK=10
MAX_WINDOWS=30

@dataclass
class Result:
    tps:int; done:bool; bust:bool; reason:str; balance:float; dd:float
    trades:int; hold:int; lot:float; when:str; days:float; cfg:object

NEWS_UTC=[
 '2026-03-06 13:30:00','2026-04-03 12:30:00','2026-05-08 12:30:00','2026-06-05 12:30:00','2026-07-02 12:30:00','2026-08-07 12:30:00',
 '2026-03-11 12:30:00','2026-04-10 12:30:00','2026-05-12 12:30:00','2026-06-10 12:30:00','2026-07-14 12:30:00','2026-08-12 12:30:00',
 '2026-03-13 12:30:00','2026-04-09 12:30:00','2026-04-30 12:30:00','2026-05-28 12:30:00','2026-06-25 12:30:00','2026-07-30 12:30:00','2026-08-26 12:30:00',
 '2026-03-18 18:00:00','2026-04-29 18:00:00','2026-06-17 18:00:00','2026-07-29 18:00:00',
]
NEWS_TS=[int(datetime.strptime(x,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()) for x in NEWS_UTC]
NEWS_GUARD_SEC=NEWS_GUARD_MIN*60

def blocked_by_news(ts:int)->bool:
    return any(abs(ts-n)<=NEWS_GUARD_SEC for n in NEWS_TS)

def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit():return int(rid)*100+int(att)
    return 240001

def candidate_starts(bars,seed,n=MAX_WINDOWS):
    warm=700;bars60=int(MAX_DAYS*24*12);hi=len(bars)-bars60-3
    if hi<=warm:raise RuntimeError('not enough BTC history for 60d windows')
    rng=random.Random(seed); candidates=list(range(warm,hi));rng.shuffle(candidates)
    out=[];min_gap=12*24*2
    for s in candidates:
        if all(abs(s-x)>=min_gap for x in out):
            out.append(s)
            if len(out)>=n:break
    return out

def fast_value_signal(i,b,c,I,bal,lot):
    """Higher-cadence BTC-only fallback close to VWAP; anti-FOMO remains hard."""
    if i<650:return 0
    E=I['e'];A=I['a'];R=I['r'];V=I['v'];x=b[i];p=b[i-1];pp=b[i-2]
    atr=max(A[i],1e-9)
    # Capital survival gate is strongest while the account is still tiny.
    if lot<=.10+1e-9 and atr*1.6>=bal/max(lot,1e-9):return 0
    up=E[8][i]>E[21][i] and E[60][i]>=E[150][i] and E[8][i]>=E[8][i-2]
    dn=E[8][i]<E[21][i] and E[60][i]<=E[150][i] and E[8][i]<=E[8][i-2]
    vw=V[48][i]; dist=(x.c-vw)/atr
    # Never chase: fallback is valid only inside a compact value band.
    maxdist=.85 if lot<=.10+1e-9 else 1.05 if lot<=.75+1e-9 else .80
    if abs(dist)>maxdist:return 0
    # Avoid expansion candles where the close itself is already a FOMO move.
    if (x.h-x.l)>1.65*atr or abs(x.c-x.o)>1.25*atr:return 0
    if up and 40<=R[i]<=70:
        touched=(p.l<=V[48][i-1]+.20*atr) or (p.l<=E[8][i-1]<=p.h)
        reclaim=(p.c>=V[48][i-1]-.12*atr and x.c>p.h and x.c>x.o)
        micro=(pp.c<=p.c<x.c and x.c>x.o and x.c>=vw-.10*atr)
        if touched and (reclaim or micro) and dist>=-.12:return 1
    if dn and 30<=R[i]<=60:
        touched=(p.h>=V[48][i-1]-.20*atr) or (p.l<=E[8][i-1]<=p.h)
        reclaim=(p.c<=V[48][i-1]+.12*atr and x.c<p.l and x.c<x.o)
        micro=(pp.c>=p.c>x.c and x.c<x.o and x.c<=vw+.10*atr)
        if touched and (reclaim or micro) and dist<=.12:return -1
    return 0

def signal(i,b,c,I,bal,lot):
    s=v22.signal('BTC',i,b,c,I,bal,lot)
    if s:return s
    return fast_value_signal(i,b,c,I,bal,lot)

def run_window(b,c,I):
    bal=START_BAL;peak=START_BAL;dd=0.;lot=LOT0;tps=tr=mh=0;pos=None
    st=v21.DT(b[0].dt);when=b[0].dt;deadline=st+timedelta(days=MAX_DAYS)
    for i in range(652,len(b)):
        z=b[i];now=v21.DT(z.dt)
        if now>deadline:
            return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,(now-st).total_seconds()/86400,c)
        if pos is None:
            if blocked_by_news(z.ts):continue
            # Previous closed M5 bar decides; entry is current M5 open.
            # No post-TP cooldown: the next M5 open is immediately eligible if setup remains valid.
            d=signal(i-1,b,c,I,bal,lot)
            if not d:continue
            pos=(d,z.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-adverse*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:
            return Result(tps,False,True,'BUST',0.,dd*100,tr,mh,L,z.dt,(now-st).total_seconds()/86400,c)
        tar=en+d*TP_PRICE;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=TP_PRICE*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:
                ok=tps==TARGET_TP and (now-st).total_seconds()/86400<=MAX_DAYS
                return Result(tps,ok,False,'PASS99' if ok else 'CHAIN_ERROR',bal,dd*100,tr,mh,L,z.dt,(now-st).total_seconds()/86400,c)
            lot=round(L+.01,2);pos=None
            # deliberately no cooldown variable here
    return Result(tps,False,False,'DATA_END',bal,dd*100,tr,mh,lot,when,(v21.DT(b[-1].dt)-st).total_seconds()/86400,c)

def rank(r):
    return (1 if r.done else 0,r.tps,0 if r.bust else 1,-r.dd,-r.days,-r.hold)

def configs(current=None):
    if current is not None:yield current
    for c in v22.cfgs('BTC'):
        if c!=current:yield c

def tune_window(b,I,current,no):
    best=None;bestc=None;n=0
    for c in configs(current):
        n+=1;r=run_window(b,c,I)
        if best is None or rank(r)>rank(best):best,bestc=r,c
        if r.done:
            print(f'WINDOW{no:02d} PASS_FOUND tries={n} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% cfg={c}',flush=True)
            return c,r,n
        if n%2000==0:
            print(f'WINDOW{no:02d} TUNE {n} bestTP={best.tps}/99 reason={best.reason} DD={best.dd:.2f}%',flush=True)
    print(f'WINDOW{no:02d} NO_PASS tries={n} bestTP={best.tps}/99 reason={best.reason} days={best.days:.2f} DD={best.dd:.2f}% cfg={bestc}',flush=True)
    return bestc,best,n

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int);a=ap.parse_args()
    seed=seed_value(a.seed);bars=b8.load();starts=candidate_starts(bars,seed)
    print('=== BTC V24 SEQUENTIAL RECOVERY / 10 CONSECUTIVE PASS ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)}',flush=True)
    print('RULES BTC-only 24/7 TP300 noSL noCut onePosition reentry=NEXT_M5_IF_VALID newsGuard=+-15m maxDays=60 target=99/99 streak=10',flush=True)
    print('WINDOW_STARTS',[bars[s].dt for s in starts],flush=True)
    current=None;streak=0;passes=0;fails=0
    for j,s in enumerate(starts,1):
        end=min(len(bars),s+int(MAX_DAYS*24*12)+700);w=bars[s:end];I=v21.prep(w)
        c,r,tries=tune_window(w,I,current,j)
        if r.done and r.tps==99 and r.days<=MAX_DAYS:
            streak+=1;passes+=1;current=c
            print(f'BTC_WINDOW{j:02d}=PASS start={bars[s].dt} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when} tries={tries} STREAK={streak}/{TARGET_STREAK}',flush=True)
            if streak>=TARGET_STREAK:
                print(f'BTC_FINAL TARGET10=True CONSECUTIVE_PASS={streak} passes={passes} fails={fails} windows={j} FINAL_CFG={current}',flush=True)
                return 0
        else:
            fails+=1;streak=0
            # Keep best config as a warm start, but this failed window does not count.
            current=c
            print(f'BTC_WINDOW{j:02d}=FAIL start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when} tries={tries} STREAK_RESET=0',flush=True)
            print('CONTINUE_NEXT_WINDOW=True',flush=True)
    print(f'BTC_FINAL TARGET10=False CONSECUTIVE_PASS={streak} passes={passes} fails={fails} windows={len(starts)} STOP_REASON=MAX_WINDOWS_REACHED',flush=True)
    return 2

if __name__=='__main__':sys.exit(main())
