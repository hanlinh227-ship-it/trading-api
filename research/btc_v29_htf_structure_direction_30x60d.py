#!/usr/bin/env python3
"""BTC V29 — HTF structure authority + M5 anti-FOMO timing, maximize PASS/30.

Locked rules: BTC only, 24/7, $20 start, one position, 0.02->1.00 +0.01 after TP,
TP=300 price units, no SL/cut/trailing/cooldown/session/news/daily cap, exact 60d.

Core change:
- Direction authority is separated from entry timing.
- Direction uses EMA8/20 + EMA12/36 + synthetic H1 (12xM5) trend + swing structure.
- M5 only times entry near value and blocks FOMO/expansion.
- Mixed/conflicting direction waits; no forced trade.
"""
from __future__ import annotations
import argparse,itertools,os,random,statistics,sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import dual_xau_btc_v21_vwap_unbounded as v21
import mt5_progressive_tp_backtest_v8 as b8

MAX_DAYS=60.0;TARGET_TP=99;TP_PRICE=300.0;START_BAL=20.0;LOT0=.02;MAX_WINDOWS=30;WARM=700

@dataclass(frozen=True)
class Cfg:
    vwap_win:int; htf_bars:int; swing:int; min_score:float
    max_dist:float; max_bar:float; max_body:float; pullback:float

@dataclass
class Result:
    tps:int;done:bool;bust:bool;reason:str;balance:float;dd:float
    trades:int;hold:int;lot:float;when:str;days:float;cfg:object

def cfgs():
    for x in itertools.product((48,96),(12,24),(6,12),(3.0,3.8,4.6),(0.75,1.0,1.25),(1.55,1.9),(1.1,1.4),(0.10,0.22)):
        yield Cfg(*x)

def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    return int(rid)*100+int(att) if rid and rid.isdigit() else 290001

def candidate_starts(bars,seed,n=MAX_WINDOWS):
    bars60=int(MAX_DAYS*24*12);lo=WARM;hi=len(bars)-bars60-3
    rng=random.Random(seed);xs=list(range(lo,hi));rng.shuffle(xs);out=[];gap=12*24*2
    for s in xs:
        if all(abs(s-x)>=gap for x in out):out.append(s)
        if len(out)>=n:break
    if len(out)<n:raise RuntimeError('not enough starts')
    return out

def sgn(x,eps=0.0):return 1 if x>eps else -1 if x<-eps else 0

def swing_dir(i,b,n):
    if i<2*n+2:return 0
    r1=b[i-n+1:i+1];r0=b[i-2*n+1:i-n+1]
    hi1=max(x.h for x in r1);lo1=min(x.l for x in r1)
    hi0=max(x.h for x in r0);lo0=min(x.l for x in r0)
    if hi1>hi0 and lo1>lo0:return 1
    if hi1<hi0 and lo1<lo0:return -1
    return 0

def authority(i,b,c,I):
    E=I['e'];V=I['v'];A=I['a'];atr=max(A[i],1e-9);x=b[i]
    e8,e20,e12,e36=E[8][i],E[20][i],E[12][i],E[36][i];vw=V[c.vwap_win][i]
    ema_fast=sgn(e8-e20);ema_slow=sgn(e12-e36)
    slope_fast=sgn(e8-E[8][i-6]);slope_slow=sgn(e36-E[36][i-12])
    sw= swing_dir(i,b,c.swing)
    h=c.htf_bars
    htf=sgn(b[i].c-b[i-h].c)
    htf2=sgn(b[i-h].c-b[i-2*h].c)
    vws=sgn(vw-V[c.vwap_win][i-12])
    score=(1.8*ema_fast+1.15*ema_slow+0.9*slope_fast+0.65*slope_slow+1.5*sw+1.2*htf+0.7*htf2+0.45*vws)
    sep=(e8-e20)/atr
    score+=max(-0.8,min(0.8,sep))*0.8
    value=(e8+e20+vw)/3.0
    return score,value,atr

def signal(i,b,c,I):
    if i<max(WARM,2*c.htf_bars+2*c.swing+5):return 0
    score,value,atr=authority(i,b,c,I)
    if abs(score)<c.min_score:return 0
    d=1 if score>0 else -1;x=b[i]
    dist=(x.c-value)/atr;rng=(x.h-x.l)/atr;body=abs(x.c-x.o)/atr
    if abs(dist)>c.max_dist or rng>c.max_bar or body>c.max_body:return 0
    edge=c.max_dist*0.78
    if d>0 and dist>edge:return 0
    if d<0 and dist<-edge:return 0
    # prefer value-side pullback but do not require a special candle pattern
    if d>0 and dist>c.max_dist-c.pullback:return 0
    if d<0 and dist<-(c.max_dist-c.pullback):return 0
    return d

def run_window(full,s,c):
    bars60=int(MAX_DAYS*24*12);w=full[s-WARM:min(len(full),s+bars60+3)];I=v21.prep(w)
    bal=peak=START_BAL;dd=0.;lot=LOT0;tps=tr=mh=0;pos=None
    st=v21.DT(full[s].dt);deadline=st+timedelta(days=MAX_DAYS);when=full[s].dt
    for i in range(WARM,len(w)):
        bar=w[i];now=v21.DT(bar.dt)
        if now>deadline:return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,MAX_DAYS,c)
        if pos is None:
            d=signal(i-1,w,c,I)
            if not d:continue
            pos=(d,bar.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-bar.l) if d>0 else max(0.,bar.h-en)
        flt=bal-adverse*L;dd=max(dd,(peak-flt)/peak)
        if flt<=0:return Result(tps,False,True,'BUST',0.,dd*100,tr,mh,L,bar.dt,(now-st).total_seconds()/86400,c)
        tar=en+d*TP_PRICE;hit=bar.h>=tar if d>0 else bar.l<=tar
        if hit:
            bal+=TP_PRICE*L;peak=max(peak,bal);tps+=1;when=bar.dt
            if L>=1.-1e-9:
                ok=tps==TARGET_TP and now<=deadline
                return Result(tps,ok,False,'PASS99' if ok else 'CHAIN_ERROR',bal,dd*100,tr,mh,L,bar.dt,(now-st).total_seconds()/86400,c)
            lot=round(L+.01,2);pos=None
    return Result(tps,False,False,'DATA_END',bal,dd*100,tr,mh,lot,when,(v21.DT(w[-1].dt)-st).total_seconds()/86400,c)

def rank(rs):
    p=sum(r.done for r in rs);near=sum(r.tps>=80 for r in rs);near50=sum(r.tps>=50 for r in rs)
    tp=sum(r.tps for r in rs);med=statistics.median(r.tps for r in rs);bu=sum(r.bust for r in rs)
    return (p,near,near50,tp,med,-bu,-statistics.median(r.dd for r in rs))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int);a=ap.parse_args()
    seed=seed_value(a.seed);bars=b8.load();starts=candidate_starts(bars,seed);configs=list(cfgs())
    print('=== BTC V29 HTF STRUCTURE DIRECTION / MAX PASS 30x60D ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)} windows=30 configs={len(configs)}',flush=True)
    print('RULES 24/7 unlimitedTP/day TP300 noSL noCut noCooldown noSession noNews exact60d=True',flush=True)
    print('ENTRY direction=HTF+swing+EMA authority; M5=value/anti-FOMO timing; objective=max PASS/30',flush=True)
    bestc=bestr=bestrk=None
    for n,c in enumerate(configs,1):
        rs=[run_window(bars,s,c) for s in starts];rk=rank(rs)
        if bestrk is None or rk>bestrk:
            bestc,bestr,bestrk=c,rs,rk
            print(f'NEW_BEST cfg#{n} PASS={rk[0]}/30 NEAR80={rk[1]}/30 NEAR50={rk[2]}/30 TP_SUM={rk[3]} MED={rk[4]:.1f} BUST={sum(r.bust for r in rs)}/30 CFG={c}',flush=True)
        if n%100==0:print(f'PROGRESS {n}/{len(configs)} BEST_PASS={bestrk[0]}/30 TP_SUM={bestrk[3]}',flush=True)
    p=sum(r.done for r in bestr);bu=sum(r.bust for r in bestr)
    print('=== BEST CONFIG WINDOW DETAIL ===',flush=True)
    for j,(s,r) in enumerate(zip(starts,bestr),1):
        state='PASS' if r.done else 'FAIL'
        print(f'BTC_WINDOW{j:02d}={state} start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when}',flush=True)
    print(f'BTC_FINAL PASS={p}/30 FAIL={30-p}/30 BUST={bu}/30 NEAR80={sum(r.tps>=80 for r in bestr)}/30 NEAR50={sum(r.tps>=50 for r in bestr)}/30 TP_SUM={sum(r.tps for r in bestr)} MED_TP={statistics.median(r.tps for r in bestr):.1f} BEST_CFG={bestc}',flush=True)
    return 0
if __name__=='__main__':sys.exit(main())
