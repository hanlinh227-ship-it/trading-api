#!/usr/bin/env python3
"""BTC V27 — optimize LONG/SHORT quality for maximum PASS count across 30 random 60-day windows.

Locked execution rules:
- BTC only, 24/7
- start balance $20
- lot 0.02 -> 1.00, +0.01 only after actual TP
- TP = 300 BTC price units
- no SL / Smart Cut / trailing / forced timeout close
- one position at a time
- no daily TP cap, no cooldown, no session filter, no news filter
- after TP, the next M5 open is immediately eligible
- entry may wait indefinitely until setup quality is good enough
- anti-FOMO blocks entries that are too extended from value or follow an abnormal expansion bar
- exact 60-day evaluation after warmup
- objective: maximize number of 99/99 PASS windows out of 30; no consecutive-PASS requirement

V27 is centered on the two V26 PASS families, both of which favored EMA direction,
especially EMA8/20. VWAP is treated primarily as value/extension context rather than
as a standalone direction authority. Direction uses a multi-horizon score combining
EMA structure, EMA slopes, value/VWAP slope and short momentum; a trade is allowed only
when directional evidence is sufficiently coherent and anti-FOMO is clear.
"""
from __future__ import annotations
import argparse, itertools, os, random, sys, statistics
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
MAX_WINDOWS=30
WARM=700

@dataclass(frozen=True)
class Cfg:
    fast:int
    slow:int
    vwap_win:int
    max_dist_atr:float
    max_bar_atr:float
    max_body_atr:float
    quality:float
    mode:str

@dataclass
class Result:
    tps:int; done:bool; bust:bool; reason:str; balance:float; dd:float
    trades:int; hold:int; lot:float; when:str; days:float; cfg:object


def cfgs():
    # Deliberately concentrate around the two V26 PASS families instead of reopening a huge search space.
    for f,s,vw,md,mr,mb,q,mode in itertools.product(
        (5,8,12),
        (20,21,36),
        (48,96),
        (0.65,0.90,1.20),
        (1.55,1.90),
        (1.10,1.40),
        (1.50,2.00,2.50),
        ('trend','balanced'),
    ):
        if f>=s: continue
        yield Cfg(f,s,vw,md,mr,mb,q,mode)


def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit():return int(rid)*100+int(att)
    return 270001


def candidate_starts(bars,seed,n=MAX_WINDOWS):
    bars60=int(MAX_DAYS*24*12)
    lo=WARM;hi=len(bars)-bars60-3
    if hi<=lo: raise RuntimeError('not enough BTC history')
    rng=random.Random(seed);xs=list(range(lo,hi));rng.shuffle(xs)
    out=[];gap=12*24*2
    for s in xs:
        if all(abs(s-x)>=gap for x in out):
            out.append(s)
            if len(out)>=n:break
    if len(out)<n:raise RuntimeError(f'only {len(out)} valid starts')
    return out


def sgn(x,eps=0.0):
    return 1 if x>eps else -1 if x<-eps else 0


def direction_score(i,b,c,I):
    E=I['e'];V=I['v'];A=I['a'];x=b[i];atr=max(A[i],1e-9)
    ef=E[c.fast][i];es=E[c.slow][i];vw=V[c.vwap_win][i]
    ef3=E[c.fast][i-3];es6=E[c.slow][i-6];vw6=V[c.vwap_win][i-6]
    value=(ef+vw)*0.5

    # Structural trend is the anchor because both V26 PASS windows favored EMA bias.
    ema_structure=sgn(ef-es)
    fast_slope=sgn(ef-ef3)
    slow_slope=sgn(es-es6)
    value_side=sgn(x.c-value)
    vwap_slope=sgn(vw-vw6)
    mom3=sgn(x.c-b[i-3].c)
    mom6=sgn(x.c-b[i-6].c)

    if c.mode=='trend':
        score=(2.00*ema_structure + 1.20*fast_slope + 0.85*slow_slope +
               0.55*vwap_slope + 0.45*mom3 + 0.30*mom6 + 0.25*value_side)
    else:
        score=(1.55*ema_structure + 1.00*fast_slope + 0.70*slow_slope +
               0.70*vwap_slope + 0.70*mom3 + 0.45*mom6 + 0.45*value_side)

    # Small continuous-strength bonus prevents weak, nearly-flat EMA crosses from looking identical to clean trends.
    sep=(ef-es)/atr
    fs=(ef-ef3)/atr
    score += max(-0.75,min(0.75,sep))*0.8 + max(-0.50,min(0.50,fs))*0.6
    return score,value


def signal(i,b,c,I):
    if i<max(WARM,c.slow+8):return 0
    A=I['a'];x=b[i];atr=max(A[i],1e-9)
    score,value=direction_score(i,b,c,I)
    d=1 if score>0 else -1

    # Quality gate: we can wait as long as needed after TP; do not force a mediocre entry.
    if abs(score)<c.quality:return 0

    # Anti-FOMO: no chase if price is already too far from blended value or last bar is abnormal expansion.
    dist=(x.c-value)/atr
    rng=(x.h-x.l)/atr
    body=abs(x.c-x.o)/atr
    if abs(dist)>c.max_dist_atr:return 0
    if rng>c.max_bar_atr or body>c.max_body_atr:return 0

    # Direction-specific chase check: entering must not be on the extreme edge in the intended direction.
    edge=c.max_dist_atr*0.82
    if d>0 and dist>edge:return 0
    if d<0 and dist<-edge:return 0
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
            return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,MAX_DAYS,c)
        if pos is None:
            d=signal(i-1,w,c,I)
            if not d:continue
            pos=(d,bar.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-bar.l) if d>0 else max(0.,bar.h-en)
        flt=bal-adverse*L;dd=max(dd,(peak-flt)/peak)
        # Conservative intrabar ordering: bust before TP if both could happen in same OHLC bar.
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


def cfg_rank(results):
    passes=sum(r.done for r in results)
    busts=sum(r.bust for r in results)
    tp_sum=sum(r.tps for r in results)
    tp_med=statistics.median(r.tps for r in results)
    dd_med=statistics.median(r.dd for r in results)
    pass_days=[r.days for r in results if r.done]
    avg_pass_days=statistics.mean(pass_days) if pass_days else 999.0
    # Primary objective is exactly what the user requested: maximize PASS count out of 30.
    return (passes,tp_sum,tp_med,-busts,-dd_med,-avg_pass_days)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int);a=ap.parse_args()
    seed=seed_value(a.seed);bars=b8.load();starts=candidate_starts(bars,seed)
    configs=list(cfgs())
    print('=== BTC V27 DIRECTION QUALITY / MAX PASS 30x60D ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)} windows={len(starts)} configs={len(configs)}',flush=True)
    print('RULES BTC-only 24/7 unlimitedTP/day TP300 noSL noCut noCooldown noSession noNews onePosition exact60d=True',flush=True)
    print('ENTRY wait-unlimited-after-TP quality-gated direction + anti-FOMO; objective=max PASS/30, no streak requirement',flush=True)

    best_cfg=None;best_results=None;best_rank=None
    for n,c in enumerate(configs,1):
        results=[]
        for s in starts:
            results.append(run_window(bars,s,c))
        rk=cfg_rank(results)
        if best_rank is None or rk>best_rank:
            best_cfg,best_results,best_rank=c,results,rk
            passes=sum(r.done for r in results);busts=sum(r.bust for r in results);tp_sum=sum(r.tps for r in results)
            print(f'NEW_BEST cfg#{n} PASS={passes}/30 TP_SUM={tp_sum} BUST={busts}/30 MED_TP={statistics.median(r.tps for r in results):.1f} CFG={c}',flush=True)
        if n%150==0:
            print(f'PROGRESS {n}/{len(configs)} CURRENT_BEST_PASS={best_rank[0]}/30 TP_SUM={best_rank[1]}',flush=True)

    assert best_cfg is not None and best_results is not None
    passes=sum(r.done for r in best_results);fails=MAX_WINDOWS-passes;busts=sum(r.bust for r in best_results)
    print('=== BEST CONFIG WINDOW DETAIL ===',flush=True)
    for j,(s,r) in enumerate(zip(starts,best_results),1):
        if r.done:
            print(f'BTC_WINDOW{j:02d}=PASS start={bars[s].dt} TP=99/99 days={r.days:.2f} DD={r.dd:.2f}% trades={r.trades} end={r.when}',flush=True)
        else:
            print(f'BTC_WINDOW{j:02d}=FAIL start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when}',flush=True)
    print(f'BTC_FINAL PASS={passes}/30 FAIL={fails}/30 BUST={busts}/30 TP_SUM={sum(r.tps for r in best_results)} MED_TP={statistics.median(r.tps for r in best_results):.1f} BEST_CFG={best_cfg}',flush=True)
    return 0

if __name__=='__main__':sys.exit(main())
