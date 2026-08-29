#!/usr/bin/env python3
"""Joint XAU+BTC V14 research harness.
Locked trade rules for both symbols:
- start $20
- lot 0.02 -> 1.00, +0.01 only after TP
- XAU TP=3.00 price, BTC TP=300.00 price
- no SL, no cut, no timeout, one position per symbol
- after TP skip TWO complete M5 bars (conservative >=10-minute cooldown)

XAU uses the V13 precision-entry family.
BTC preserves the V12 breakout core and adds regime/follow-through filters.
Ten deterministic random starts are unchanged (seed 20260829).
"""
from __future__ import annotations
import argparse, random, sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8
import xau_random10_v13_precision_entry as xv13

SEED=20260829
STAGE1=3
TOP=96


def starts(n):
    r=random.Random(SEED)
    return sorted(r.sample(range(0,max(1,int(n*.78))),10))


def roll(b,lbs):
    out={}
    for lb in lbs:
        hi=[None]*len(b); lo=[None]*len(b)
        for i in range(lb,len(b)):
            w=b[i-lb:i]
            hi[i]=max(z.h for z in w); lo[i]=min(z.l for z in w)
        out[lb]=(hi,lo)
    return out


@dataclass(frozen=True)
class BCfg:
    fast:int; slow:int; lb:int; rlo:int; rhi:int; confirm:float
    htf:int; budget:float; chase:float; sep:float; body:float
    slope:int; side:str

@dataclass
class R:
    tps:int; done:bool; bust:bool; eq:float; dd:float
    trades:int; hold:int; lot:float; when:str


def btc_cfgs():
    # Tight search around V12 best: breakout 5/20, lb20, RSI 48-70,
    # confirm .10, HTF1, budget4, chase1.6. Add only causal filters.
    mas=[(5,20),(8,21),(12,36)]
    lbs=[12,20,30]
    rb=[(46,68),(48,70),(50,72)]
    confirm=[.08,.10,.15,.20]
    htf=[1,2]
    budget=[3.0,4.0,5.0]
    chase=[1.2,1.6,2.0]
    sep=[0.0,.10,.20,.30]
    body=[0.0,.15,.25,.35]
    slope=[2,3,6]
    sides=['both','long','short']
    # Deterministic thinning keeps CI tractable while covering interactions.
    for n,z in enumerate(product(mas,lbs,rb,confirm,htf,budget,chase,sep,body,slope,sides)):
        if n%7: continue
        ma,lb,r,cf,ht,bu,ch,se,bo,sl,si=z
        yield BCfg(ma[0],ma[1],lb,r[0],r[1],cf,ht,bu,ch,se,bo,sl,si)


def prep_btc(b):
    cl=[z.c for z in b]
    ps=[5,8,12,20,21,36,60,150,240,600]
    return {
        'e':{p:x3.ema(cl,p) for p in ps},
        'a':x3.atr(b),
        'r':x3.rsi(cl),
        'roll':roll(b,[12,20,30]),
    }


def sideok(s,d):
    return s=='both' or (s=='long' and d==1) or (s=='short' and d==-1)


def btc_sig(i,b,c,I,bal,lot):
    if i<650: return 0
    E=I['e']; A=I['a']; RS=I['r']; x=b[i]; q=b[i-1]
    atr=max(A[i],1e-9)

    # Survival budget gate. BTC contract size=1.
    maxadv=bal/lot
    if atr*c.budget>=maxadv: return 0

    # V12 M5 + M15 trend core.
    up=(E[c.fast][i]>E[c.slow][i] and
        E[c.fast][i]>E[c.fast][i-c.slope] and
        E[c.slow][i]>=E[c.slow][i-c.slope] and
        E[60][i]>E[150][i] and E[60][i]>=E[60][i-c.slope])
    dn=(E[c.fast][i]<E[c.slow][i] and
        E[c.fast][i]<E[c.fast][i-c.slope] and
        E[c.slow][i]<=E[c.slow][i-c.slope] and
        E[60][i]<E[150][i] and E[60][i]<=E[60][i-c.slope])

    # Optional H1 proxy alignment for regimes that reversed after breakout in V12.
    if c.htf==2:
        up=up and E[240][i]>E[600][i] and E[240][i]>E[240][i-6]
        dn=dn and E[240][i]<E[600][i] and E[240][i]<E[240][i-6]

    # Trend strength + anti-exhaustion.
    if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr: return 0
    if abs(x.c-E[c.fast][i])>c.chase*atr: return 0

    # Keep V12 breakout logic, but require the confirmation candle to have real body.
    hi,lo=I['roll'][c.lb]
    body=abs(x.c-x.o)
    if body<c.body*atr: return 0
    need=c.confirm*atr
    rl=c.rlo<=RS[i]<=c.rhi
    rs=(100-c.rhi)<=RS[i]<=(100-c.rlo)

    if up and q.c>hi[i-1] and x.c>=q.c+need and x.c>x.o and rl and sideok(c.side,1):
        return 1
    if dn and q.c<lo[i-1] and x.c<=q.c-need and x.c<x.o and rs and sideok(c.side,-1):
        return -1
    return 0


def run_btc(b,c,I):
    bal=20.; peak=20.; dd=0.; lot=.02; tps=tr=mh=0
    pos=None; cool=-1; when=b[0].dt
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool: continue
            d=btc_sig(i-1,b,c,I,bal,lot)
            if not d: continue
            pos=(d,z.o,lot,i); tr+=1
        d,en,L,ei=pos
        mh=max(mh,i-ei+1)
        ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-ad*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:
            return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
        tar=en+d*300.
        hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=300.*L; peak=max(peak,bal); tps+=1; when=z.dt
            if L>=1.-1e-9:
                return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
            lot=round(L+.01,2); pos=None; cool=i+2  # skip two full M5 bars
    return R(tps,False,False,bal,dd*100,tr,mh,lot,when)


def score(rs):
    return (sum(r.done for r in rs),sum(r.tps for r in rs),sum(not r.bust for r in rs),-sum(r.dd for r in rs),-sum(r.hold for r in rs))


def run_btc_search():
    bars=b8.load(); ss=starts(len(bars)); wins=[bars[s:] for s in ss]
    caches=[prep_btc(w) for w in wins]; cs=list(btc_cfgs())
    print('=== BTC V14 JOINT / 10-MIN COOLDOWN ===',flush=True)
    print('range',bars[0].dt,'->',bars[-1].dt,'bars',len(bars),'configs',len(cs),flush=True)
    print('starts',[bars[s].dt for s in ss],flush=True)
    stage=[]
    for n,c in enumerate(cs,1):
        rs=[run_btc(w,c,I) for w,I in zip(wins[:STAGE1],caches[:STAGE1])]
        sc=score(rs); stage.append((sc,c,rs))
        if n%1000==0 or n==len(cs):
            print(f'PROGRESS BTC stage1 {n}/{len(cs)} best={max(x[0][0] for x in stage)}/3',flush=True)
    survivors=[x for x in stage if x[0][0]==3]
    pool=survivors if survivors else sorted(stage,key=lambda x:x[0],reverse=True)[:TOP]
    print('BTC SURVIVORS',len(survivors),'POOL',len(pool),flush=True)
    best=None
    for n,(sc,c,r3) in enumerate(pool,1):
        rs=r3+[run_btc(w,c,I) for w,I in zip(wins[3:],caches[3:])]
        full=score(rs)
        if best is None or full>best[0]: best=(full,c,rs)
        if n%10==0 or full[0]==10 or n==len(pool):
            print(f'PROGRESS BTC stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]} alive={full[2]}/10',flush=True)
        if full[0]==10: break
    sc,c,rs=best
    print(f'BTC_V14_BEST {c} pass={sc[0]}/10 sumTP={sc[1]} alive={sc[2]}/10',flush=True)
    for j,(s,r) in enumerate(zip(ss,rs),1):
        print(f'BTC{j:02d} start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
    return 0


def run_xau_search():
    # V13 already implements the new 10-minute cooldown and precision-entry families.
    print('=== XAU V14 JOINT (V13 PRECISION CORE) / 10-MIN COOLDOWN ===',flush=True)
    return xv13.main()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--symbol',choices=['XAU','BTC'],required=True)
    a=ap.parse_args()
    return run_xau_search() if a.symbol=='XAU' else run_btc_search()

if __name__=='__main__':
    sys.exit(main())
