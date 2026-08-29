#!/usr/bin/env python3
"""Joint XAU+BTC V15 research harness.

Purpose: preserve V14 winners while targeting the five BTC V14 failure windows.
Locked execution rules remain unchanged:
- start $20
- lot 0.02 -> 1.00, +0.01 only after TP
- XAU TP=3.00 price, BTC TP=300.00 price
- no SL, no cut, no timeout, one position per symbol
- after TP skip TWO complete M5 bars (conservative >=10-minute cooldown)

BTC V15 change is deliberately localized to the vulnerable early chain (<= guard_lot):
1) require trend ordering to have remained stable for N bars;
2) reject contracting EMA separation / transition regimes;
3) reject oversized confirmation candles (exhaustion shock);
4) optionally require H1 proxy agreement only during the vulnerable early chain;
5) keep the proven V14 breakout core after the guard threshold.

XAU stays on the V14/V13 precision core so the joint workflow remains comparable.
Ten deterministic starts remain unchanged (seed 20260829).
"""
from __future__ import annotations
import argparse, sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_xau_btc_v14_joint as v14
import mt5_progressive_tp_backtest_v8 as b8

STAGE1=3
TOP=128

@dataclass(frozen=True)
class C:
    # Proven V14 core neighborhood.
    fast:int; slow:int; lb:int; rlo:int; rhi:int; confirm:float
    budget:float; chase:float; sep:float; body:float; slope:int; side:str
    # Failure-focused early-chain guard.
    guard_lot:float; stable:int; spread_keep:float; shock:float; early_h1:int


def cfgs():
    # Keep search centered on V14 best (5/20, lb20, 48/70, confirm .08,
    # budget4, chase2, sep.1, slope3, both) instead of re-optimizing everything.
    core=[
        (5,20,20,48,70,.08,4.0,2.0,.10,0.0,3,'both'),
        (5,20,20,48,70,.10,4.0,2.0,.10,0.0,3,'both'),
        (5,20,20,48,70,.08,4.0,1.6,.10,.15,3,'both'),
        (5,20,20,48,70,.10,4.0,1.6,.10,.15,3,'both'),
        (5,20,20,46,68,.08,4.0,2.0,.10,0.0,3,'both'),
        (5,20,20,50,72,.08,4.0,2.0,.10,0.0,3,'both'),
    ]
    guard_lot=[.08,.12,.18,.25]
    stable=[3,6,12,18]
    spread_keep=[-.10,0.0,.10,.20]
    shock=[1.25,1.75,2.5,99.0]
    early_h1=[0,1]
    for base,g,st,sk,sh,h1 in product(core,guard_lot,stable,spread_keep,shock,early_h1):
        yield C(*base,g,st,sk,sh,h1)


def sideok(s,d):
    return s=='both' or (s=='long' and d==1) or (s=='short' and d==-1)


def sig(i,b,c,I,bal,lot):
    if i<650: return 0
    E=I['e']; A=I['a']; RS=I['r']; x=b[i]; q=b[i-1]
    atr=max(A[i],1e-9)

    # Same survival-budget gate as V14.
    maxadv=bal/lot
    if atr*c.budget>=maxadv: return 0

    up=(E[c.fast][i]>E[c.slow][i] and
        E[c.fast][i]>E[c.fast][i-c.slope] and
        E[c.slow][i]>=E[c.slow][i-c.slope] and
        E[60][i]>E[150][i] and E[60][i]>=E[60][i-c.slope])
    dn=(E[c.fast][i]<E[c.slow][i] and
        E[c.fast][i]<E[c.fast][i-c.slope] and
        E[c.slow][i]<=E[c.slow][i-c.slope] and
        E[60][i]<E[150][i] and E[60][i]<=E[60][i-c.slope])

    if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr: return 0
    if abs(x.c-E[c.fast][i])>c.chase*atr: return 0

    body=abs(x.c-x.o)
    if body<c.body*atr: return 0

    # Localized early-chain protection. V14 failures all occurred <=0.17 lot.
    if lot<=c.guard_lot+1e-9:
        j=i-c.stable
        if j<0: return 0
        # Trend side must have been ordered continuously at guard endpoints;
        # this screens fresh cross/transition regimes without touching late chain.
        if up:
            if not (E[c.fast][j]>E[c.slow][j] and E[60][j]>E[150][j]): return 0
        if dn:
            if not (E[c.fast][j]<E[c.slow][j] and E[60][j]<E[150][j]): return 0

        # Avoid entering while the fast/slow spread is materially contracting.
        old=max(abs(E[c.fast][j]-E[c.slow][j]),1e-9)
        now=abs(E[c.fast][i]-E[c.slow][i])
        if now < old + c.spread_keep*atr: return 0

        # Oversized confirmation bars frequently mark exhaustion rather than follow-through.
        if body>c.shock*atr: return 0

        # H1 proxy alignment only where the $20 chain is most fragile.
        if c.early_h1:
            if up and not (E[240][i]>E[600][i] and E[240][i]>=E[240][i-6]): return 0
            if dn and not (E[240][i]<E[600][i] and E[240][i]<=E[240][i-6]): return 0

    hi,lo=I['roll'][c.lb]
    need=c.confirm*atr
    rl=c.rlo<=RS[i]<=c.rhi
    rs=(100-c.rhi)<=RS[i]<=(100-c.rlo)
    if up and q.c>hi[i-1] and x.c>=q.c+need and x.c>x.o and rl and sideok(c.side,1): return 1
    if dn and q.c<lo[i-1] and x.c<=q.c-need and x.c<x.o and rs and sideok(c.side,-1): return -1
    return 0


def run(b,c,I):
    bal=20.; peak=20.; dd=0.; lot=.02; tps=tr=mh=0
    pos=None; cool=-1; when=b[0].dt
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool: continue
            d=sig(i-1,b,c,I,bal,lot)
            if not d: continue
            pos=(d,z.o,lot,i); tr+=1
        d,en,L,ei=pos
        mh=max(mh,i-ei+1)
        ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-ad*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:
            return v14.R(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
        tar=en+d*300.
        hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=300.*L; peak=max(peak,bal); tps+=1; when=z.dt
            if L>=1.-1e-9:
                return v14.R(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
            lot=round(L+.01,2); pos=None; cool=i+2
    return v14.R(tps,False,False,bal,dd*100,tr,mh,lot,when)


def btc():
    bars=b8.load(); ss=v14.starts(len(bars)); wins=[bars[s:] for s in ss]
    caches=[v14.prep_btc(w) for w in wins]; cs=list(cfgs())
    print('=== BTC V15 FAILURE-GUARD / 10-MIN COOLDOWN ===',flush=True)
    print('range',bars[0].dt,'->',bars[-1].dt,'bars',len(bars),'configs',len(cs),flush=True)
    print('starts',[bars[s].dt for s in ss],flush=True)
    stage=[]
    for n,c in enumerate(cs,1):
        rs=[run(w,c,I) for w,I in zip(wins[:STAGE1],caches[:STAGE1])]
        sc=v14.score(rs); stage.append((sc,c,rs))
        if n%500==0 or n==len(cs):
            print(f'PROGRESS BTC V15 stage1 {n}/{len(cs)} best={max(x[0][0] for x in stage)}/3',flush=True)
    survivors=[x for x in stage if x[0][0]==3]
    pool=survivors if survivors else sorted(stage,key=lambda x:x[0],reverse=True)[:TOP]
    # Bound stage2 if many guards preserve the same first-three behavior.
    if len(pool)>TOP: pool=sorted(pool,key=lambda x:x[0],reverse=True)[:TOP]
    print('BTC V15 SURVIVORS',len(survivors),'POOL',len(pool),flush=True)
    best=None
    for n,(sc,c,r3) in enumerate(pool,1):
        rs=r3+[run(w,c,I) for w,I in zip(wins[3:],caches[3:])]
        full=v14.score(rs)
        if best is None or full>best[0]: best=(full,c,rs)
        if n%10==0 or full[0]>=6 or n==len(pool):
            print(f'PROGRESS BTC V15 stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]} alive={full[2]}/10',flush=True)
        if full[0]==10: break
    sc,c,rs=best
    print(f'BTC_V15_BEST {c} pass={sc[0]}/10 sumTP={sc[1]} alive={sc[2]}/10',flush=True)
    for j,(s,r) in enumerate(zip(ss,rs),1):
        print(f'BTC{j:02d} start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
    return 0


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--symbol',choices=['XAU','BTC'],required=True); a=ap.parse_args()
    if a.symbol=='XAU':
        print('=== XAU V15 JOINT: unchanged V14 precision core ===',flush=True)
        return v14.run_xau_search()
    return btc()

if __name__=='__main__': sys.exit(main())
