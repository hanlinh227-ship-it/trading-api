#!/usr/bin/env python3
"""BTC V30: official complete Binance M5 + HTF/value confirmation, unbounded holding.
Research only. Locked execution: $20, one position, 0.02->1.00 +0.01 after TP,
TP=300 price units, no SL/cut/trailing/cooldown/session/news/daily cap, no timeout close.
"""
from __future__ import annotations
import itertools,random,statistics,sys
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import btc_binance_m5_full_loader as data
import dual_xau_btc_v21_vwap_unbounded as v21

START_BAL=20.0;LOT0=.02;TP=300.0;TARGET=99;WARM=700

@dataclass(frozen=True)
class Cfg:
    min_score:float;max_dist:float;pullback:float;max_bar:float;confirm:float
@dataclass
class R:
    tps:int;done:bool;bust:bool;reason:str;bal:float;dd:float;trades:int;lot:float;days:float;when:str

def cfgs():
    for z in itertools.product((4.8,5.6),(.55,.75),(.10,.22),(1.35,1.70),(.02,.05)):
        yield Cfg(*z)

def sgn(x,eps=0):return 1 if x>eps else -1 if x<-eps else 0

def swing_dir(i,b,n=12):
    if i<2*n+2:return 0
    a=b[i-n+1:i+1];p=b[i-2*n+1:i-n+1]
    h1=max(x.h for x in a);l1=min(x.l for x in a);h0=max(x.h for x in p);l0=min(x.l for x in p)
    return 1 if h1>h0 and l1>l0 else -1 if h1<h0 and l1<l0 else 0

def authority(i,b,I):
    E=I['e'];V=I['v'];A=I['a'];atr=max(A[i],1e-9);vw=V[96][i]
    ef=sgn(E[8][i]-E[20][i]);es=sgn(E[12][i]-E[36][i])
    sf=sgn(E[8][i]-E[8][i-6]);ss=sgn(E[36][i]-E[36][i-12])
    sw=swing_dir(i,b,12)
    h1=sgn(b[i].c-b[i-12].c);h2=sgn(b[i-12].c-b[i-24].c);h4=sgn(b[i].c-b[i-48].c)
    vws=sgn(vw-V[96][i-12])
    score=1.9*ef+1.3*es+0.9*sf+0.75*ss+1.65*sw+1.3*h1+0.8*h2+0.55*h4+0.5*vws
    sep=(E[8][i]-E[20][i])/atr;score+=max(-.9,min(.9,sep))*.75
    value=(E[8][i]+E[20][i]+vw)/3
    return score,value,atr

def signal(i,b,c,I):
    if i<WARM:return 0
    sc,val,atr=authority(i,b,I)
    if abs(sc)<c.min_score:return 0
    d=1 if sc>0 else -1;x=b[i];p=b[i-1];pp=b[i-2]
    rng=(x.h-x.l)/atr;body=abs(x.c-x.o)/atr;dist=(x.c-val)/atr
    if rng>c.max_bar or body>1.05 or abs(dist)>c.max_dist:return 0
    E=I['e']
    if d>0 and not(E[12][i]>E[36][i] and E[60][i]>E[150][i]):return 0
    if d<0 and not(E[12][i]<E[36][i] and E[60][i]<E[150][i]):return 0
    if d>0:
        if p.l>val+c.pullback*atr:return 0
        if not(p.c>=p.o or p.c>=val-.12*atr):return 0
        if not(x.c>x.o and x.c>p.h+c.confirm*atr and x.c>val):return 0
        if pp.c>x.c:return 0
    else:
        if p.h<val-c.pullback*atr:return 0
        if not(p.c<=p.o or p.c<=val+.12*atr):return 0
        if not(x.c<x.o and x.c<p.l-c.confirm*atr and x.c<val):return 0
        if pp.c<x.c:return 0
    return d

def run(b,start,c,I):
    bal=peak=START_BAL;dd=0.;lot=LOT0;tps=tr=0;pos=None;st=b[start].ts;when=b[start].dt
    for i in range(max(start,WARM+2),len(b)):
        z=b[i]
        if pos is None:
            d=signal(i-1,b,c,I)
            if not d:continue
            pos=(d,z.o,lot);tr+=1
        d,en,L=pos;adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-adverse*L;dd=max(dd,(peak-flt)/peak)
        if flt<=0:return R(tps,False,True,'BUST',0.,dd*100,tr,L,(z.ts-st)/86400,z.dt)
        tar=en+d*TP;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=TP*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:return R(tps,tps==TARGET,False,'PASS99' if tps==TARGET else 'CHAIN_ERROR',bal,dd*100,tr,L,(z.ts-st)/86400,z.dt)
            lot=round(L+.01,2);pos=None
    return R(tps,False,False,'DATA_END',bal,dd*100,tr,lot,(b[-1].ts-st)/86400,when)

def idx_at(b,s):
    ts=int(datetime.strptime(s,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp());lo=0;hi=len(b)
    while lo<hi:
        m=(lo+hi)//2
        if b[m].ts<ts:lo=m+1
        else:hi=m
    return lo

def calibration_starts(b):
    return [idx_at(b,x) for x in ('2023-04-15','2023-06-15','2023-08-15','2023-10-15')]

def fresh_starts(b,seed=300831):
    # Ten fresh dates all leave roughly >=2 years of future data, so DATA_END is not caused by short history.
    lo=idx_at(b,'2023-12-01');hi=idx_at(b,'2024-08-01');cand=list(range(lo,hi,12*24))
    rng=random.Random(seed);rng.shuffle(cand);out=[];gap=12*24*14
    for s in cand:
        if all(abs(s-x)>=gap for x in out):out.append(s)
        if len(out)==10:break
    return sorted(out)

def rank(rs):
    p=sum(r.done for r in rs);early=sum(r.bust and r.tps<10 for r in rs);bust=sum(r.bust for r in rs)
    worst=min(r.tps for r in rs);tp=sum(r.tps for r in rs);med=statistics.median(r.tps for r in rs)
    return (p,-early,-bust,worst,tp,med,-statistics.median(r.dd for r in rs))

def main():
    b=data.load();I=v21.prep(b);cs=list(cfgs());cal=calibration_starts(b)
    print('=== BTC V30 COMPLETE-DATA QUALITY ENTRY / UNBOUNDED ===',flush=True)
    print('RULES $20 TP300 0.02->1.00 noSL noCut noTrailing noCooldown noTimeout 24/7',flush=True)
    best=None
    for n,c in enumerate(cs,1):
        rs=[run(b,s,c,I) for s in cal];rk=rank(rs)
        if best is None or rk>best[0]:best=(rk,c,rs)
        print(f'CAL {n:02d}/{len(cs)} rank={rk} cfg={c}',flush=True)
    rk,c,_=best;print('BEST_CFG',c,'CAL_RANK',rk,flush=True)
    starts=fresh_starts(b);rs=[run(b,s,c,I) for s in starts]
    for j,(s,r) in enumerate(zip(starts,rs),1):
        print(f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} TP={r.tps}/99 days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when}',flush=True)
    print(f'BTC_FINAL PASS={sum(r.done for r in rs)}/10 BUST={sum(r.bust for r in rs)}/10 DATA_END={sum(r.reason=="DATA_END" for r in rs)}/10 TP_SUM={sum(r.tps for r in rs)} MED_TP={statistics.median(r.tps for r in rs):.1f} MAX_TP={max(r.tps for r in rs)} MIN_TP={min(r.tps for r in rs)} BEST_CFG={c}',flush=True)
if __name__=='__main__':main()
