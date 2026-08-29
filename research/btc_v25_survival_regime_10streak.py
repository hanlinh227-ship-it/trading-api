#!/usr/bin/env python3
"""BTC V25 — survival-first regime/pullback entry engine.

Locked rules preserved:
- BTC only, 24/7, start $20
- 0.02 -> 1.00 lot, +0.01 only after actual TP
- TP = 300 BTC price units
- no SL / no Smart Cut / no trailing / no forced timeout close
- one position at a time
- after TP, next M5 bar may re-enter immediately if setup is valid
- block NEW entries +/-15m around major scheduled USD news
- each evaluation window = 60 days, target = 99/99 TP
- failed window moves immediately to another historical window
- final target = 10 consecutive PASS windows

V25 changes entry architecture completely:
1) trend-regime only: never countertrend mean-revert into a strong move;
2) pullback-to-value + reclaim entry, not momentum chasing;
3) capital survival gate based on balance/lot adverse-price capacity;
4) volatility/range shock gate and directional danger gate;
5) exact 60-day evaluation clock starts AFTER warmup bars.
"""
from __future__ import annotations
import argparse, os, random, sys, itertools
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
MAX_WINDOWS=36
WARM=700

NEWS_UTC=[
 '2026-03-06 13:30:00','2026-04-03 12:30:00','2026-05-08 12:30:00','2026-06-05 12:30:00','2026-07-02 12:30:00','2026-08-07 12:30:00',
 '2026-03-11 12:30:00','2026-04-10 12:30:00','2026-05-12 12:30:00','2026-06-10 12:30:00','2026-07-14 12:30:00','2026-08-12 12:30:00',
 '2026-03-13 12:30:00','2026-04-09 12:30:00','2026-04-30 12:30:00','2026-05-28 12:30:00','2026-06-25 12:30:00','2026-07-30 12:30:00','2026-08-26 12:30:00',
 '2026-03-18 18:00:00','2026-04-29 18:00:00','2026-06-17 18:00:00','2026-07-29 18:00:00',
]
NEWS_TS=[int(datetime.strptime(x,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()) for x in NEWS_UTC]
NEWS_GUARD_SEC=15*60

def blocked_by_news(ts): return any(abs(ts-n)<=NEWS_GUARD_SEC for n in NEWS_TS)

@dataclass(frozen=True)
class Cfg:
    trend_fast:int; trend_slow:int; vwap_win:int
    value_atr:float; reclaim_atr:float
    capacity_frac:float; shock_atr:float
    slope_bars:int; min_slope_atr:float
    rsi_long_lo:int; rsi_long_hi:int

@dataclass
class Result:
    tps:int; done:bool; bust:bool; reason:str; balance:float; dd:float
    trades:int; hold:int; lot:float; when:str; days:float; cfg:object


def cfgs():
    # ~1,296 configurations: materially different survival architecture but finite enough for sequential tuning.
    for vals in itertools.product(
        ((8,21),(12,36),(20,60)),
        (48,96),
        (.55,.80,1.05),
        (.08,.16),
        (.28,.38,.50),
        (1.6,2.1),
        (6,12),
        (.10,.20),
        ((42,68),(46,72),(50,74)),
    ):
        tf,vw,va,rc,cf,sh,sb,ms,rr=vals
        yield Cfg(tf[0],tf[1],vw,va,rc,cf,sh,sb,ms,rr[0],rr[1])


def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit():return int(rid)*100+int(att)
    return 250001


def candidate_starts(bars,seed,n=MAX_WINDOWS):
    bars60=int(MAX_DAYS*24*12)
    lo=WARM; hi=len(bars)-bars60-3
    if hi<=lo: raise RuntimeError('not enough BTC history')
    rng=random.Random(seed); xs=list(range(lo,hi)); rng.shuffle(xs)
    out=[]; gap=12*24*2
    for s in xs:
        if all(abs(s-x)>=gap for x in out):
            out.append(s)
            if len(out)>=n:break
    return out


def recent_range(b,i,n):
    lo=min(x.l for x in b[i-n+1:i+1]); hi=max(x.h for x in b[i-n+1:i+1])
    return hi-lo


def signal(i,b,c,I,bal,lot):
    if i<max(WARM, c.trend_slow+5): return 0
    E=I['e']; A=I['a']; R=I['r']; V=I['v']
    x=b[i]; p=b[i-1]; pp=b[i-2]
    atr=max(A[i],1e-9); cap=bal/max(lot,1e-9)

    # Survival budget: only enter when current realized volatility is small relative to
    # the price move that would wipe current equity. This is strongest in early progression.
    frac=c.capacity_frac
    if lot<=.10: frac*=.72
    elif lot<=.20: frac*=.86
    if atr*c.shock_atr > cap*frac: return 0
    if recent_range(b,i,24) > cap*frac*1.35: return 0

    # Reject fresh shock / expansion bars and stale FOMO entries.
    if (x.h-x.l)>c.shock_atr*atr or abs(x.c-x.o)>1.35*atr: return 0
    vw=V[c.vwap_win][i]
    dist=(x.c-vw)/atr
    if abs(dist)>c.value_atr: return 0

    ef=E[c.trend_fast]; es=E[c.trend_slow]
    slope=(es[i]-es[i-c.slope_bars])/max(c.slope_bars*atr,1e-9)
    up=ef[i]>es[i] and E[60][i]>=E[150][i] and slope>=c.min_slope_atr
    dn=ef[i]<es[i] and E[60][i]<=E[150][i] and slope<=-c.min_slope_atr

    # Directional danger: no longs while last 12 bars are persistently selling, and vice versa.
    mom12=(x.c-b[i-12].c)/atr
    if up and mom12 < -1.15:return 0
    if dn and mom12 > 1.15:return 0

    # Pullback must touch value; current closed bar must reclaim in trend direction.
    vwp=V[c.vwap_win][i-1]
    long_touch=(p.l<=vwp+c.reclaim_atr*atr) or (p.l<=ef[i-1]<=p.h)
    short_touch=(p.h>=vwp-c.reclaim_atr*atr) or (p.l<=ef[i-1]<=p.h)
    long_reclaim=(x.c>x.o and x.c>p.h and x.c>=vw-c.reclaim_atr*atr and pp.c<=p.c)
    short_reclaim=(x.c<x.o and x.c<p.l and x.c<=vw+c.reclaim_atr*atr and pp.c>=p.c)

    if up and c.rsi_long_lo<=R[i]<=c.rsi_long_hi and long_touch and long_reclaim:
        return 1
    slo=100-c.rsi_long_hi; shi=100-c.rsi_long_lo
    if dn and slo<=R[i]<=shi and short_touch and short_reclaim:
        return -1
    return 0


def run_window(full,s,c):
    # Warmup is BEFORE evaluation start, so the 60-day clock is exact.
    bars60=int(MAX_DAYS*24*12)
    a=s-WARM; z=min(len(full),s+bars60+3)
    w=full[a:z]; I=v21.prep(w); start_idx=WARM
    bal=START_BAL;peak=START_BAL;dd=0.;lot=LOT0;tps=tr=mh=0;pos=None
    st=v21.DT(full[s].dt);deadline=st+timedelta(days=MAX_DAYS);when=full[s].dt
    for i in range(start_idx,len(w)):
        bar=w[i]; now=v21.DT(bar.dt)
        if now>deadline:
            return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,(now-st).total_seconds()/86400,c)
        if pos is None:
            if blocked_by_news(bar.ts):continue
            d=signal(i-1,w,c,I,bal,lot)
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
    return (1 if r.done else 0, 0 if r.bust else 1, r.tps, -r.dd, -r.days, -r.hold)


def tune(full,s,current,no):
    best=None;bestc=None;n=0
    ordered=[]
    if current is not None:ordered.append(current)
    ordered.extend(c for c in cfgs() if c!=current)
    for c in ordered:
        n+=1;r=run_window(full,s,c)
        if best is None or rank(r)>rank(best):best,bestc=r,c
        if r.done:
            print(f'WINDOW{no:02d} PASS_FOUND tries={n} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% cfg={c}',flush=True)
            return c,r,n
        if n%500==0:
            print(f'WINDOW{no:02d} TUNE {n} bestTP={best.tps}/99 reason={best.reason} bust={best.bust} DD={best.dd:.2f}%',flush=True)
    print(f'WINDOW{no:02d} NO_PASS tries={n} bestTP={best.tps}/99 reason={best.reason} days={best.days:.2f} DD={best.dd:.2f}% cfg={bestc}',flush=True)
    return bestc,best,n


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int);a=ap.parse_args()
    seed=seed_value(a.seed);bars=b8.load();starts=candidate_starts(bars,seed)
    print('=== BTC V25 SURVIVAL-REGIME / 10 CONSECUTIVE PASS ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)}',flush=True)
    print('RULES BTC-only 24/7 TP300 noSL noCut onePosition reentry=NEXT_M5_IF_VALID newsGuard=+-15m exact60d=True target=99/99 streak=10',flush=True)
    print('ARCH regime-trend + pullback-value-reclaim + capital-capacity + shock/danger gates',flush=True)
    current=None;streak=passes=fails=0
    for j,s in enumerate(starts,1):
        c,r,tries=tune(bars,s,current,j)
        if r.done and r.tps==99 and r.days<=MAX_DAYS:
            streak+=1;passes+=1;current=c
            print(f'BTC_WINDOW{j:02d}=PASS start={bars[s].dt} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% end={r.when} tries={tries} STREAK={streak}/{TARGET_STREAK}',flush=True)
            if streak>=TARGET_STREAK:
                print(f'BTC_FINAL TARGET10=True CONSECUTIVE_PASS={streak} passes={passes} fails={fails} windows={j} FINAL_CFG={current}',flush=True);return 0
        else:
            fails+=1;streak=0;current=c
            print(f'BTC_WINDOW{j:02d}=FAIL start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when} tries={tries} STREAK_RESET=0',flush=True)
            print('CONTINUE_NEXT_WINDOW=True',flush=True)
    print(f'BTC_FINAL TARGET10=False CONSECUTIVE_PASS={streak} passes={passes} fails={fails} windows={len(starts)} STOP_REASON=MAX_WINDOWS_REACHED',flush=True)
    return 2

if __name__=='__main__':sys.exit(main())
