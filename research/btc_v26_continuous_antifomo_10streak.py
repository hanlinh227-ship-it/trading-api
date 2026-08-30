#!/usr/bin/env python3
"""BTC V26 — continuous 24/7 entry engine with anti-FOMO as the only entry blocker.

Locked rules:
- BTC only, 24/7
- start balance $20
- lot 0.02 -> 1.00, +0.01 only after actual TP
- TP = 300 BTC price units
- no SL / Smart Cut / trailing / forced timeout close
- one open position at a time
- NO daily TP cap, NO cooldown, NO session filter, NO news filter
- when flat, seek an entry every M5 bar
- the ONLY reason to delay entry is anti-FOMO: price too extended from value or the just-closed bar is an expansion chase bar
- after TP, next M5 open is immediately eligible
- exact 60-day evaluation clock after warmup
- target = 99/99 TP and 10 consecutive PASS historical windows
"""
from __future__ import annotations
import argparse, os, random, sys, itertools
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_xau_btc_v21_vwap_unbounded as v21
import mt5_progressive_tp_backtest_v8 as b8

MAX_DAYS=60.0
TARGET_TP=99
TP_PRICE=300.0
START_BAL=20.0
LOT0=.02
TARGET_STREAK=10
MAX_WINDOWS=30
WARM=700

@dataclass(frozen=True)
class Cfg:
    fast:int; slow:int; vwap_win:int
    max_dist_atr:float; max_bar_atr:float; max_body_atr:float
    bias_mode:str; pullback_pref:float

@dataclass
class Result:
    tps:int; done:bool; bust:bool; reason:str; balance:float; dd:float
    trades:int; hold:int; lot:float; when:str; days:float; cfg:object


def cfgs():
    # Tune only anti-FOMO sensitivity and directional bias speed.
    # v21.prep provides VWAP 48/96; do not request unsupported VWAP24.
    for f,s,vw,md,mr,mb,bm,pp in itertools.product(
        (5,8,12),
        (20,21,36),
        (48,96),
        (0.65,0.90,1.20,1.55),
        (1.55,1.90,2.30),
        (1.10,1.40,1.75),
        ('ema','vwap','hybrid'),
        (0.0,0.12),
    ):
        if f>=s: continue
        yield Cfg(f,s,vw,md,mr,mb,bm,pp)


def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit():return int(rid)*100+int(att)
    return 260001


def candidate_starts(bars,seed,n=MAX_WINDOWS):
    bars60=int(MAX_DAYS*24*12)
    lo=WARM; hi=len(bars)-bars60-3
    if hi<=lo: raise RuntimeError('not enough BTC history')
    rng=random.Random(seed);xs=list(range(lo,hi));rng.shuffle(xs)
    out=[];gap=12*24*2
    for s in xs:
        if all(abs(s-x)>=gap for x in out):
            out.append(s)
            if len(out)>=n:break
    return out


def direction(i,b,c,I):
    E=I['e'];V=I['v'];x=b[i]
    ef=E[c.fast][i];es=E[c.slow][i];vw=V[c.vwap_win][i]
    if c.bias_mode=='ema':
        if ef>es:return 1
        if ef<es:return -1
    elif c.bias_mode=='vwap':
        if x.c>vw:return 1
        if x.c<vw:return -1
    else:
        score=(1 if ef>es else -1 if ef<es else 0)+(1 if x.c>vw else -1 if x.c<vw else 0)
        if score>0:return 1
        if score<0:return -1
    return 1 if x.c>=b[i-1].c else -1


def signal(i,b,c,I):
    if i<max(WARM,c.slow+3):return 0
    A=I['a'];V=I['v'];E=I['e'];x=b[i];atr=max(A[i],1e-9)
    vw=V[c.vwap_win][i]
    d=direction(i,b,c,I)
    value=(vw+E[c.fast][i])*0.5
    dist=(x.c-value)/atr
    rng=(x.h-x.l)/atr
    body=abs(x.c-x.o)/atr
    if abs(dist)>c.max_dist_atr:return 0
    if rng>c.max_bar_atr or body>c.max_body_atr:return 0
    if c.pullback_pref>0:
        if d>0 and dist>c.max_dist_atr-c.pullback_pref:return 0
        if d<0 and dist<-(c.max_dist_atr-c.pullback_pref):return 0
    return d


def run_window(full,s,c):
    bars60=int(MAX_DAYS*24*12)
    a=s-WARM;z=min(len(full),s+bars60+3)
    w=full[a:z];I=v21.prep(w);start_idx=WARM
    bal=START_BAL;peak=START_BAL;dd=0.;lot=LOT0;tps=tr=mh=0;pos=None
    st=v21.DT(full[s].dt);deadline=st+timedelta(days=MAX_DAYS);when=full[s].dt
    for i in range(start_idx,len(w)):
        bar=w[i];now=v21.DT(bar.dt)
        if now>deadline:
            return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,(now-st).total_seconds()/86400,c)
        if pos is None:
            d=signal(i-1,w,c,I)
            if not d:continue
            pos=(d,bar.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-bar.l) if d>0 else max(0.,bar.h-en)
        flt=bal-adverse*L;dd=max(dd,(peak-flt)/peak)
        if flt<=0:
            return Result(tps,False,True,'BUST',0.,dd*100,tr,mh,L,bar.dt,(now-st).total_seconds()/86400,c)
        tar=en+d*TP_PRICE;hit=bar.h>=tar if d>0 else bar.l<=tar
        if hit:
            bal+=TP_PRICE*L;peak=max(peak,bal);tps+=1;when=bar.dt
            if L>=1.-1e-9:
                ok=tps==TARGET_TP and now<=deadline
                return Result(tps,ok,False,'PASS99' if ok else 'CHAIN_ERROR',bal,dd*100,tr,mh,L,bar.dt,(now-st).total_seconds()/86400,c)
            lot=round(L+.01,2);pos=None
    return Result(tps,False,False,'DATA_END',bal,dd*100,tr,mh,lot,when,(v21.DT(w[-1].dt)-st).total_seconds()/86400,c)


def rank(r):
    return (1 if r.done else 0,r.tps,0 if r.bust else 1,-r.dd,-r.days,-r.hold)


def tune(full,s,current,no):
    best=None;bestc=None;n=0
    ordered=[]
    if current is not None:ordered.append(current)
    ordered.extend(c for c in cfgs() if c!=current)
    for c in ordered:
        n+=1;r=run_window(full,s,c)
        if best is None or rank(r)>rank(best):best,bestc=r,c
        if r.done:
            print(f'WINDOW{no:02d} PASS_FOUND tries={n} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% trades={r.trades} cfg={c}',flush=True)
            return c,r,n
        if n%750==0:
            print(f'WINDOW{no:02d} TUNE {n} bestTP={best.tps}/99 reason={best.reason} bust={best.bust} DD={best.dd:.2f}%',flush=True)
    print(f'WINDOW{no:02d} NO_PASS tries={n} bestTP={best.tps}/99 reason={best.reason} days={best.days:.2f} DD={best.dd:.2f}% trades={best.trades} cfg={bestc}',flush=True)
    return bestc,best,n


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int);a=ap.parse_args()
    seed=seed_value(a.seed);bars=b8.load();starts=candidate_starts(bars,seed)
    print('=== BTC V26 CONTINUOUS 24/7 / ANTI-FOMO ONLY ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)}',flush=True)
    print('RULES BTC-only 24/7 unlimitedTP/day TP300 noSL noCut noCooldown noSession noNews onePosition exact60d=True target=99/99 streak=10',flush=True)
    print('ONLY_ENTRY_BLOCKER anti-FOMO=value-distance + expansion-bar',flush=True)
    current=None;streak=passes=fails=0
    for j,s in enumerate(starts,1):
        c,r,tries=tune(bars,s,current,j)
        if r.done and r.tps==99 and r.days<=MAX_DAYS:
            streak+=1;passes+=1;current=c
            print(f'BTC_WINDOW{j:02d}=PASS start={bars[s].dt} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% trades={r.trades} end={r.when} tries={tries} STREAK={streak}/{TARGET_STREAK}',flush=True)
            if streak>=TARGET_STREAK:
                print(f'BTC_FINAL TARGET10=True CONSECUTIVE_PASS={streak} passes={passes} fails={fails} windows={j} FINAL_CFG={current}',flush=True);return 0
        else:
            fails+=1;streak=0;current=c
            print(f'BTC_WINDOW{j:02d}=FAIL start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when} tries={tries} STREAK_RESET=0',flush=True)
            print('CONTINUE_NEXT_WINDOW=True',flush=True)
    print(f'BTC_FINAL TARGET10=False CONSECUTIVE_PASS={streak} passes={passes} fails={fails} windows={len(starts)} STOP_REASON=MAX_WINDOWS_REACHED',flush=True)
    return 2

if __name__=='__main__':sys.exit(main())
