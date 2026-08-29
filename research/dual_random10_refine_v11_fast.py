#!/usr/bin/env python3
"""V11 fast random10 harness.
Same trading rules/data as V10; optimization only changes computation, not outcomes:
- cache indicators once per window
- cache rolling breakout levels
- screen all configs on first 3 frozen windows; only configs 3/3 can possibly become 10/10
- validate survivors on remaining 7 windows
- if no 3/3 survivor, validate top diagnostics on all 10
- symbol selected by --symbol XAU|BTC so GitHub matrix runs both in parallel
"""
from __future__ import annotations
import argparse, random, sys
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8

SEED=20260829
STAGE1=3
TOP_DIAG=32


def frozen_starts(n,count=10):
    r=random.Random(SEED); hi=max(1,int(n*.78)); return sorted(r.sample(range(0,hi),count))

def rolling_levels(bars,lbs):
    out={}
    for lb in lbs:
        hi=[None]*len(bars); lo=[None]*len(bars)
        for i in range(lb,len(bars)):
            w=bars[i-lb:i]; hi[i]=max(z.h for z in w); lo[i]=min(z.l for z in w)
        out[lb]=(hi,lo)
    return out

@dataclass
class XR:
    tps:int; finished:bool; busted:bool; equity:float; maxdd:float; trades:int; maxhold:int; lot:float; when:str


def prep_x(bars):
    cl=[z.c for z in bars]
    ps=sorted({3,5,8,9,12,20,21,30,36,50,100})
    return {'e':{p:x3.ema(cl,p) for p in ps},'a':x3.atr(bars),'r':x3.rsi(cl),'roll':rolling_levels(bars,[3,5,8,12,20])}

def xsig(i,b,c,I):
    if i<max(c.slow,c.lookback,c.slope_bars,15): return 0
    E=I['e']; A=I['a']; R=I['r']; x=b[i]; p=b[i-1]
    sf=E[c.fast][i]-E[c.fast][i-c.slope_bars]; ss=E[c.slow][i]-E[c.slow][i-c.slope_bars]
    body=x.c-x.o; strength=abs(body)/max(A[i],1e-9)
    up=E[c.fast][i]>E[c.slow][i] and sf>0 and ss>=0
    dn=E[c.fast][i]<E[c.slow][i] and sf<0 and ss<=0
    rl=c.rsi_lo<=R[i]<=c.rsi_hi; rs=(100-c.rsi_hi)<=R[i]<=(100-c.rsi_lo)
    if c.kind=='trend':
        if up and x.c>E[c.fast][i] and body>0 and strength>=c.body_atr and rl:return 1
        if dn and x.c<E[c.fast][i] and body<0 and strength>=c.body_atr and rs:return -1
    elif c.kind=='breakout':
        hi,lo=I['roll'][c.lookback]
        if up and x.c>hi[i] and rl:return 1
        if dn and x.c<lo[i] and rs:return -1
    elif c.kind=='pullback':
        if up and p.l<=E[c.fast][i-1] and x.c>p.h and rl:return 1
        if dn and p.h>=E[c.fast][i-1] and x.c<p.l and rs:return -1
    elif c.kind=='rejection':
        rg=max(x.h-x.l,1e-9); lower=(min(x.o,x.c)-x.l)/rg; upper=(x.h-max(x.o,x.c))/rg
        if up and lower>=.35 and x.c>x.o and x.c>E[c.fast][i] and rl:return 1
        if dn and upper>=.35 and x.c<x.o and x.c<E[c.fast][i] and rs:return -1
    return 0

def xrun(b,c,I):
    tp=3.; contract=100.; bal=20.; peak=20.; dd=0.; lot=.02; tps=tr=mh=0; pos=None; cool=-1; when=b[0].dt
    for i in range(max(c.slow,c.lookback,20)+2,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool: continue
            d=xsig(i-1,b,c,I)
            if not d: continue
            pos=(d,z.o,lot,i); tr+=1
        d,en,L,ei=pos; mh=max(mh,i-ei+1); ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-ad*contract*L; dd=max(dd,(peak-flt)/peak)
        if flt<=0:return XR(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
        tar=en+d*tp; hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=tp*contract*L; peak=max(peak,bal); tps+=1; when=z.dt
            if L>=1.-1e-9:return XR(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
            lot=round(L+.01,2); pos=None; cool=i+1
    return XR(tps,False,False,bal,dd*100,tr,mh,lot,when)

@dataclass
class BR:
    tps:int; done:bool; bust:bool; eq:float; dd:float; trades:int; hold:int; lot:float; when:str

def prep_b(b):
    cl=[z.c for z in b]; ps=[5,8,9,12,20,21,30,36,50,60,150,240,600]
    return {'e':{p:b8.ema(cl,p) for p in ps},'a':b8.atr(b),'r':b8.rsi(cl),'roll':rolling_levels(b,[12,20,30,48,72])}

def bsig(i,b,c,I):
    if i<650:return 0
    E=I['e'];A=I['a'];R=I['r'];q=b[i-1];x=b[i]
    up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>E[c.fast][i-2]
    dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<E[c.fast][i-2]
    if c.htf>=1:
        up=up and E[60][i]>E[150][i] and E[60][i]>E[60][i-3]
        dn=dn and E[60][i]<E[150][i] and E[60][i]<E[60][i-3]
    if c.htf>=2:
        up=up and E[240][i]>E[600][i] and E[240][i]>E[240][i-6]
        dn=dn and E[240][i]<E[600][i] and E[240][i]<E[240][i-6]
    hi,lo=I['roll'][c.lb]; hi=hi[i-1]; lo=lo[i-1]; need=c.confirm_atr*A[i]
    side=lambda d:c.side=='both' or c.side=='long' and d==1 or c.side=='short' and d==-1
    if up and q.c>hi and x.c>=q.c+need and x.c>x.o and c.rlo<=R[i]<=c.max_rsi and side(1):return 1
    if dn and q.c<lo and x.c<=q.c-need and x.c<x.o and 100-c.max_rsi<=R[i]<=100-c.rlo and side(-1):return -1
    return 0

def brun(b,c,I):
    bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;when=b[0].dt
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool:continue
            d=bsig(i-1,b,c,I)
            if not d:continue
            pos=(d,z.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1);ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-ad*L;dd=max(dd,(peak-flt)/peak)
        if flt<=0:return BR(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
        tar=en+d*300.;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=300.*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:return BR(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
            lot=round(L+.01,2);pos=None;cool=i+1
    return BR(tps,False,False,bal,dd*100,tr,mh,lot,when)

def score(rs,done_attr,dd_attr,hold_attr):
    return (sum(bool(getattr(r,done_attr)) for r in rs),sum(r.tps for r in rs),-sum(getattr(r,dd_attr) for r in rs),-sum(getattr(r,hold_attr) for r in rs))

def search(symbol):
    if symbol=='XAU':
        bars=x3.load(x3.DATA['XAUUSD']['url']); cfg=list(x3.cfgs()); run=xrun; prep=prep_x; done='finished'; dd='maxdd'; hold='maxhold'
    else:
        bars=b8.load(); cfg=list(b8.cfgs()); run=brun; prep=prep_b; done='done'; dd='dd'; hold='hold'
    starts=frozen_starts(len(bars)); windows=[bars[s:] for s in starts]
    print(f'=== {symbol} V11 FAST RANDOM10 ===',flush=True)
    print('bars',len(bars),'range',bars[0].dt,'->',bars[-1].dt,flush=True)
    print('starts',[bars[s].dt for s in starts],flush=True)
    print('precompute indicators for 10 windows...',flush=True)
    caches=[prep(w) for w in windows]
    stage=[]
    total=len(cfg)
    for n,c in enumerate(cfg,1):
        rs=[run(w,c,I) for w,I in zip(windows[:STAGE1],caches[:STAGE1])]
        sc=score(rs,done,dd,hold); stage.append((sc,c,rs))
        if n%100==0 or n==total: print(f'PROGRESS stage1 {n}/{total} bestPass3={max(x[0][0] for x in stage)}/3',flush=True)
    survivors=[x for x in stage if x[0][0]==STAGE1]
    print('STAGE1 survivors',len(survivors),'of',total,flush=True)
    pool=survivors if survivors else sorted(stage,key=lambda x:x[0],reverse=True)[:TOP_DIAG]
    best=None
    for n,(sc,c,rs3) in enumerate(pool,1):
        rs=rs3+[run(w,c,I) for w,I in zip(windows[STAGE1:],caches[STAGE1:])]
        full=score(rs,done,dd,hold)
        if best is None or full>best[0]:best=(full,c,rs)
        print(f'PROGRESS stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]}',flush=True)
        if full[0]==10:break
    sc,c,rs=best
    print(f'{symbol}_BEST {c} pass={sc[0]}/10 sumTP={sc[1]}',flush=True)
    for i,(s,r) in enumerate(zip(starts,rs),1):
        d=bool(getattr(r,done)); bust=bool(getattr(r,'busted' if symbol=='XAU' else 'bust')); lot=r.lot; ddraw=getattr(r,dd)
        print(f'{symbol}{i:02d} start={bars[s].dt} TP={r.tps}/99 done={d} bust={bust} DD={ddraw:.2f}% lot={lot:.2f} end={r.when}',flush=True)
    return 0 if sc[0]==10 else 2

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);a=ap.parse_args();sys.exit(search(a.symbol))
if __name__=='__main__':main()
