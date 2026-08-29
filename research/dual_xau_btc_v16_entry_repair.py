#!/usr/bin/env python3
"""Dual XAU+BTC V16 entry-repair research harness.

Goal: repair the actual failure zone of V14/V15 without changing locked exits.
Locked execution:
- $20 start
- lot 0.02 -> 1.00, +0.01 only after TP
- XAU TP +3.00 price, BTC TP +300.00 price
- no SL / no cut / no timeout
- one position per symbol
- >=10 minute cooldown after TP (skip two complete M5 bars)

Observed V14 failure zone:
- XAU: all 7 failures died between 0.02 and 0.13 lot.
- BTC: all 5 failures died between 0.02 and 0.17 lot.

V16 therefore makes ONLY early-chain entry stricter:
XAU <=0.15 lot:
  * preserve reclaim core
  * require trend stable for N bars
  * require EMA spread not contracting
  * optional H1 alignment
  * confirmation candle cannot be exhaustion shock
  * require reclaim break to also clear a short structural high/low
BTC <=0.25 lot:
  * preserve V14 breakout core
  * V15 regime guards
  * require stronger two-step continuation quality before entry
Late chain returns to the proven core.
"""
from __future__ import annotations
import argparse, sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8
import xau_random10_v13_precision_entry as xv13
import dual_xau_btc_v14_joint as v14

TOP=128
STAGE1=3

@dataclass(frozen=True)
class XCfg:
    fast:int; slow:int; rlo:int; rhi:int; confirm:float; budget:float; chase:float
    pull:float; sep:float; side:str
    guard_lot:float; stable:int; spread_keep:float; shock:float; early_h1:int; struct_lb:int

@dataclass(frozen=True)
class BCfg:
    fast:int; slow:int; lb:int; rlo:int; rhi:int; confirm:float; budget:float; chase:float
    sep:float; slope:int; side:str
    guard_lot:float; stable:int; spread_keep:float; shock:float; early_h1:int; cont_body:float


def xcfgs():
    # Centered on V14 XAU best reclaim 12/36, RSI45/68, budget2, chase.5, pull.35.
    cores=[
        (12,36,45,68,0.0,2.0,.5,.35,0.0,'both'),
        (12,36,45,68,.08,2.0,.5,.35,0.0,'both'),
        (12,36,48,70,0.0,2.0,.8,.35,.10,'both'),
        (8,21,45,68,.08,2.0,.8,.35,.10,'both'),
    ]
    for base,g,st,sk,sh,h1,slb in product(
        cores,[.08,.12,.15],[3,6,12,18],[-.10,0.0,.10,.20],[1.25,1.75,2.5,99.0],[0,1],[3,5,8]
    ):
        yield XCfg(*base,g,st,sk,sh,h1,slb)


def bcfgs():
    cores=[
        (5,20,20,48,70,.08,4.0,2.0,.10,3,'both'),
        (5,20,20,48,70,.10,4.0,1.6,.10,3,'both'),
        (5,20,20,46,68,.08,4.0,2.0,.10,3,'both'),
        (5,20,20,50,72,.08,4.0,2.0,.10,3,'both'),
    ]
    for base,g,st,sk,sh,h1,cb in product(
        cores,[.12,.18,.25],[3,6,12,18],[-.10,0.0,.10,.20],[1.25,1.75,2.5,99.0],[0,1],[0.0,.15,.25]
    ):
        yield BCfg(*base,g,st,sk,sh,h1,cb)


def sideok(s,d):
    return s=='both' or (s=='long' and d==1) or (s=='short' and d==-1)


def roll(b,lbs):
    out={}
    for lb in lbs:
        hi=[None]*len(b); lo=[None]*len(b)
        for i in range(lb,len(b)):
            w=b[i-lb:i]; hi[i]=max(z.h for z in w); lo[i]=min(z.l for z in w)
        out[lb]=(hi,lo)
    return out


def prep_xau(b):
    cl=[z.c for z in b]; ps=[8,12,21,36,60,150,240,600]
    return {'e':{p:x3.ema(cl,p) for p in ps},'a':x3.atr(b),'r':x3.rsi(cl),'roll':roll(b,[3,5,8])}


def prep_btc(b):
    return v14.prep_btc(b)


def trend_guard(E,A,i,fast,slow,stable,spread_keep,up,dn,early_h1):
    atr=max(A[i],1e-9); j=i-stable
    if j<0: return False
    if up and not (E[fast][j]>E[slow][j] and E[60][j]>E[150][j]): return False
    if dn and not (E[fast][j]<E[slow][j] and E[60][j]<E[150][j]): return False
    old=abs(E[fast][j]-E[slow][j]); now=abs(E[fast][i]-E[slow][i])
    if now < old + spread_keep*atr: return False
    if early_h1:
        if up and not (E[240][i]>E[600][i] and E[240][i]>=E[240][i-6]): return False
        if dn and not (E[240][i]<E[600][i] and E[240][i]<=E[240][i-6]): return False
    return True


def xsig(i,b,c,I,bal,lot):
    if i<650:return 0
    E=I['e']; A=I['a']; RS=I['r']; x=b[i]; p=b[i-1]; atr=max(A[i],1e-9)
    maxadv=bal/(lot*100.)
    if atr*c.budget>=maxadv:return 0
    up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>E[c.fast][i-2] and E[c.slow][i]>=E[c.slow][i-3] and E[60][i]>E[150][i] and E[60][i]>=E[60][i-3]
    dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<E[c.fast][i-2] and E[c.slow][i]<=E[c.slow][i-3] and E[60][i]<E[150][i] and E[60][i]<=E[60][i-3]
    if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr:return 0
    if abs(x.c-E[c.fast][i])>c.chase*atr:return 0
    pd_long=(E[c.fast][i-1]-p.l)/atr; pd_short=(p.h-E[c.fast][i-1])/atr
    rl=c.rlo<=RS[i]<=c.rhi; rs=(100-c.rhi)<=RS[i]<=(100-c.rlo); need=c.confirm*atr
    long_ok=up and 0<=pd_long<=c.pull and p.l<=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o and rl and sideok(c.side,1)
    short_ok=dn and 0<=pd_short<=c.pull and p.h>=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o and rs and sideok(c.side,-1)
    if lot<=c.guard_lot+1e-9 and (long_ok or short_ok):
        if not trend_guard(E,A,i,c.fast,c.slow,c.stable,c.spread_keep,up,dn,c.early_h1):return 0
        body=abs(x.c-x.o)
        if body>c.shock*atr:return 0
        hi,lo=I['roll'][c.struct_lb]
        # Early chain must reclaim AND break short structure; this rejects weak pseudo-reclaims.
        if long_ok and not (x.c>hi[i-1]): return 0
        if short_ok and not (x.c<lo[i-1]): return 0
    if long_ok:return 1
    if short_ok:return -1
    return 0


def bsig(i,b,c,I,bal,lot):
    if i<650:return 0
    E=I['e']; A=I['a']; RS=I['r']; x=b[i]; q=b[i-1]; qq=b[i-2]; atr=max(A[i],1e-9)
    if atr*c.budget>=bal/lot:return 0
    up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>E[c.fast][i-c.slope] and E[c.slow][i]>=E[c.slow][i-c.slope] and E[60][i]>E[150][i] and E[60][i]>=E[60][i-c.slope]
    dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<E[c.fast][i-c.slope] and E[c.slow][i]<=E[c.slow][i-c.slope] and E[60][i]<E[150][i] and E[60][i]<=E[60][i-c.slope]
    if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr:return 0
    if abs(x.c-E[c.fast][i])>c.chase*atr:return 0
    hi,lo=I['roll'][c.lb]; need=c.confirm*atr
    rl=c.rlo<=RS[i]<=c.rhi; rs=(100-c.rhi)<=RS[i]<=(100-c.rlo)
    long_ok=up and q.c>hi[i-1] and x.c>=q.c+need and x.c>x.o and rl and sideok(c.side,1)
    short_ok=dn and q.c<lo[i-1] and x.c<=q.c-need and x.c<x.o and rs and sideok(c.side,-1)
    if lot<=c.guard_lot+1e-9 and (long_ok or short_ok):
        if not trend_guard(E,A,i,c.fast,c.slow,c.stable,c.spread_keep,up,dn,c.early_h1):return 0
        body=abs(x.c-x.o)
        if body>c.shock*atr:return 0
        # two-step quality: breakout bar and confirmation bar should agree; reject one-bar fakeouts
        qbody=abs(q.c-q.o)
        if qbody<c.cont_body*max(A[i-1],1e-9):return 0
        if long_ok and not (q.c>q.o and x.l>=min(q.o,q.c)-.35*atr):return 0
        if short_ok and not (q.c<q.o and x.h<=max(q.o,q.c)+.35*atr):return 0
    if long_ok:return 1
    if short_ok:return -1
    return 0


def run_symbol(b,c,I,symbol):
    bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;when=b[0].dt
    contract=100. if symbol=='XAU' else 1.; tp=3. if symbol=='XAU' else 300.
    sig=xsig if symbol=='XAU' else bsig
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool:continue
            d=sig(i-1,b,c,I,bal,lot)
            if not d:continue
            pos=(d,z.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-ad*contract*L;dd=max(dd,(peak-flt)/peak)
        if flt<=0:return v14.R(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
        tar=en+d*tp;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=tp*contract*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:return v14.R(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
            lot=round(L+.01,2);pos=None;cool=i+2
    return v14.R(tps,False,False,bal,dd*100,tr,mh,lot,when)


def search(symbol):
    if symbol=='XAU':
        bars=x3.load(x3.DATA['XAUUSD']['url']); cs=list(xcfgs()); prep=prep_xau
    else:
        bars=b8.load(); cs=list(bcfgs()); prep=prep_btc
    ss=v14.starts(len(bars)); wins=[bars[s:] for s in ss]; caches=[prep(w) for w in wins]
    print(f'=== {symbol} V16 ENTRY REPAIR / 10-MIN COOLDOWN ===',flush=True)
    print('range',bars[0].dt,'->',bars[-1].dt,'bars',len(bars),'configs',len(cs),flush=True)
    print('starts',[bars[s].dt for s in ss],flush=True)
    stage=[]
    for n,c in enumerate(cs,1):
        rs=[run_symbol(w,c,I,symbol) for w,I in zip(wins[:STAGE1],caches[:STAGE1])]
        sc=v14.score(rs);stage.append((sc,c,rs))
        if n%500==0 or n==len(cs):print(f'PROGRESS {symbol} V16 stage1 {n}/{len(cs)} best={max(x[0][0] for x in stage)}/3',flush=True)
    surv=[x for x in stage if x[0][0]==3]
    pool=surv if surv else sorted(stage,key=lambda x:x[0],reverse=True)[:TOP]
    if len(pool)>TOP:pool=sorted(pool,key=lambda x:x[0],reverse=True)[:TOP]
    print(f'{symbol} V16 SURVIVORS',len(surv),'POOL',len(pool),flush=True)
    best=None
    for n,(sc,c,r3) in enumerate(pool,1):
        rs=r3+[run_symbol(w,c,I,symbol) for w,I in zip(wins[3:],caches[3:])]
        full=v14.score(rs)
        if best is None or full>best[0]:best=(full,c,rs)
        if n%10==0 or full[0]>=6 or n==len(pool):print(f'PROGRESS {symbol} V16 stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]} alive={full[2]}/10',flush=True)
        if full[0]==10:break
    sc,c,rs=best
    print(f'{symbol}_V16_BEST {c} pass={sc[0]}/10 sumTP={sc[1]} alive={sc[2]}/10',flush=True)
    for j,(s,r) in enumerate(zip(ss,rs),1):print(f'{symbol}{j:02d} start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
    return 0


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);a=ap.parse_args();return search(a.symbol)

if __name__=='__main__':sys.exit(main())
