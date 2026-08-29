#!/usr/bin/env python3
"""V21 VWAP-aware, unbounded-horizon progressive TP backtest for XAU+BTC.

Locked rules:
- $20 start
- 0.02 -> 1.00, +0.01 only after actual TP
- XAU TP=3.00 price units, BTC TP=300.00 price units
- no SL, no Smart Cut, no timeout close
- one open position per symbol
- after TP skip one complete M5 bar (>=5 minutes)

V21 changes:
- removes the 60-day completion deadline; each sampled window runs from its random start to the end of available history
- adds rolling VWAP proxy (typical-price weighted by tick volume when available; otherwise equal-weight fallback)
- blocks FOMO entries when price is too extended from VWAP
- prefers reclaim/pullback near VWAP for XAU and retest/sweep-like continuation near VWAP for BTC
- keeps 5 TRAIN + 5 HOLDOUT split to reduce overfit
"""
from __future__ import annotations
import argparse, os, random, sys
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8

EMA_KEYS=(5,8,12,20,21,36,50,60,100,150,240,600)
VWAP_WIN=(48,96,288)

@dataclass(frozen=True)
class C:
    fast:int; slow:int; lb:int; rlo:int; rhi:int
    early_mode:str; mid_mode:str; late_mode:str
    early_stable:int; early_h1:int; early_budget:float
    early_vwap_win:int; early_vwap_max:float; early_reclaim:float
    mid_vwap_win:int; mid_vwap_max:float; mid_confirm:float; mid_body:float
    late_stable:int; late_h1:int; late_vwap_win:int; late_vwap_max:float; late_sep:float

@dataclass
class R:
    tps:int; done:bool; bust:bool; balance:float; dd:float; trades:int
    hold:int; lot:float; when:str; days:float

def DT(x): return datetime.fromisoformat(str(x))

def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit():return int(rid)*100+int(att)
    import time;return int(time.time_ns()%2147483647)

def cfgs(symbol):
    if symbol=='XAU':
        mas=[(8,21),(12,36),(20,50)]; lbs=[3,5,8]; rs=[(44,68),(47,70),(50,72)]
        em=['reclaim']; mm=['reclaim','momentum','breakout']; lm=['reclaim','breakout']
        es=[6,12,24]; eh=[0,1]; eb=[1.2,1.6,2.0]
        evw=[48,96]; evmax=[.55,.75,1.0]; er=[.10,.20,.30]
        mvw=[48,96]; mvmax=[.9,1.2,1.5]; mcf=[0,.04,.08]; mb=[0,.10]
        ls=[12,24]; lh=[0,1]; lvw=[96,288]; lvmax=[.7,1.0,1.3]; lsep=[.05,.12]
        thin=1458
    else:
        mas=[(5,20),(8,21),(12,36)]; lbs=[8,12,20]; rs=[(44,70),(47,72),(50,74)]
        em=['retest']; mm=['retest','momentum','breakout']; lm=['retest','breakout']
        es=[12,24,36]; eh=[1]; eb=[1.8,2.2,2.8]
        evw=[48,96]; evmax=[.7,1.0,1.3]; er=[.15,.25,.35]
        mvw=[48,96]; mvmax=[1.0,1.4,1.8]; mcf=[.02,.05,.08]; mb=[0,.10]
        ls=[12,24,36]; lh=[0,1]; lvw=[96,288]; lvmax=[.9,1.2,1.5]; lsep=[.05,.12]
        thin=1458
    dims=product(mas,lbs,rs,em,mm,lm,es,eh,eb,evw,evmax,er,mvw,mvmax,mcf,mb,ls,lh,lvw,lvmax,lsep)
    for n,z in enumerate(dims):
        if n%thin:continue
        ma,lb,r,a,b,c,d,e,f,g,h,j,k,l,m,o,p,q,s,t,u=z
        yield C(ma[0],ma[1],lb,r[0],r[1],a,b,c,d,e,f,g,h,j,k,l,m,o,p,q,s,t,u)

def rolling_vwap(b,n):
    out=[0.0]*len(b); pv=0.0; vv=0.0; q=[]
    for i,z in enumerate(b):
        tp=(z.h+z.l+z.c)/3.0
        vol=float(getattr(z,'v',0) or getattr(z,'vol',0) or getattr(z,'volume',0) or 1.0)
        if vol<=0:vol=1.0
        q.append((tp*vol,vol));pv+=tp*vol;vv+=vol
        if len(q)>n:
            a,bv=q.pop(0);pv-=a;vv-=bv
        out[i]=pv/max(vv,1e-9)
    return out

def prep(b):
    cl=[z.c for z in b]
    return {'e':{p:x3.ema(cl,p) for p in EMA_KEYS},'a':x3.atr(b),'r':x3.rsi(cl),
            'v':{n:rolling_vwap(b,n) for n in VWAP_WIN}}

def starts(bars,seed):
    # No fixed horizon: sample starts with enough warmup and enough remaining history for meaningful validation.
    lo=700; hi=max(lo+1,len(bars)-3000)
    valid=list(range(lo,hi))
    return sorted(random.Random(seed).sample(valid,10))

def direction(i,c,I,sep=0):
    E=I['e'];A=I['a'];atr=max(A[i],1e-9)
    if abs(E[c.fast][i]-E[c.slow][i])<sep*atr:return 0
    up=E[c.fast][i]>E[c.slow][i] and E[60][i]>E[150][i] and E[c.fast][i]>=E[c.fast][i-3]
    dn=E[c.fast][i]<E[c.slow][i] and E[60][i]<E[150][i] and E[c.fast][i]<=E[c.fast][i-3]
    return 1 if up else -1 if dn else 0

def stable(i,d,c,I,n,h1):
    E=I['e'];j=i-n
    if j<0:return False
    if d>0:
        if not(E[c.fast][j]>E[c.slow][j] and E[60][j]>E[150][j]):return False
        if h1 and not(E[240][i]>E[600][i] and E[240][i]>=E[240][i-6]):return False
    else:
        if not(E[c.fast][j]<E[c.slow][j] and E[60][j]<E[150][j]):return False
        if h1 and not(E[240][i]<E[600][i] and E[240][i]<=E[240][i-6]):return False
    return True

def phase(lot):
    if lot<=.10+1e-9:return 'early'
    if lot<=.50+1e-9:return 'mid'
    return 'late'

def family(mode,d,i,b,c,I,confirm,body):
    E=I['e'];A=I['a'];x=b[i];p=b[i-1];pp=b[i-2];atr=max(A[i],1e-9);need=confirm*atr
    lo=max(0,i-c.lb);hi0=max(z.h for z in b[lo:i]);lo0=min(z.l for z in b[lo:i])
    if abs(x.c-x.o)<body*atr:return 0
    if mode=='breakout':
        if d>0 and p.c>hi0-(p.h-p.c) and x.c>p.h+need and x.c>x.o:return 1
        if d<0 and p.c<lo0+(p.c-p.l) and x.c<p.l-need and x.c<x.o:return -1
    elif mode in ('reclaim','retest'):
        touch=p.l<=E[c.fast][i-1]<=p.h
        if d>0 and touch and p.c>=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o:return 1
        if d<0 and touch and p.c<=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o:return -1
    else:
        if max(abs(p.c-p.o),abs(x.c-x.o))>2.0*atr:return 0
        if d>0 and pp.c<p.c<x.c and p.c>p.o and x.c>x.o and x.c>p.h+need:return 1
        if d<0 and pp.c>p.c>x.c and p.c<p.o and x.c<x.o and x.c<p.l-need:return -1
    return 0

def signal(symbol,i,b,c,I,bal,lot):
    if i<650:return 0
    E=I['e'];A=I['a'];RS=I['r'];V=I['v'];x=b[i];p=b[i-1];atr=max(A[i],1e-9)
    contract=100. if symbol=='XAU' else 1.;ph=phase(lot)
    if ph=='early':
        if atr*c.early_budget>=bal/(lot*contract):return 0
        d=direction(i,c,I,.05)
        if not d or not stable(i,d,c,I,c.early_stable,c.early_h1):return 0
        vw=V[c.early_vwap_win][i];dist=(x.c-vw)/atr
        if d>0:
            if not(0<=dist<=c.early_vwap_max):return 0
            # require recent pullback/reclaim near VWAP to avoid FOMO
            if p.l>V[c.early_vwap_win][i-1]+c.early_reclaim*atr:return 0
        else:
            if not(-c.early_vwap_max<=dist<=0):return 0
            if p.h<V[c.early_vwap_win][i-1]-c.early_reclaim*atr:return 0
        mode=c.early_mode;confirm=.02 if symbol=='XAU' else .04;body=0
    elif ph=='mid':
        d=direction(i,c,I,0)
        if not d:return 0
        vw=V[c.mid_vwap_win][i];dist=(x.c-vw)/atr
        if d>0 and not(0<=dist<=c.mid_vwap_max):return 0
        if d<0 and not(-c.mid_vwap_max<=dist<=0):return 0
        mode=c.mid_mode;confirm=c.mid_confirm;body=c.mid_body
    else:
        d=direction(i,c,I,c.late_sep)
        if not d or not stable(i,d,c,I,c.late_stable,c.late_h1):return 0
        vw=V[c.late_vwap_win][i];dist=(x.c-vw)/atr
        if d>0 and not(0<=dist<=c.late_vwap_max):return 0
        if d<0 and not(-c.late_vwap_max<=dist<=0):return 0
        mode=c.late_mode;confirm=.03 if symbol=='XAU' else .05;body=.05
    if d>0 and not(c.rlo<=RS[i]<=c.rhi):return 0
    if d<0 and not((100-c.rhi)<=RS[i]<=(100-c.rlo)):return 0
    return family(mode,d,i,b,c,I,confirm,body)

def run(symbol,b,c,I):
    bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;st=DT(b[0].dt);when=b[0].dt
    contract=100. if symbol=='XAU' else 1.;tp=3. if symbol=='XAU' else 300.
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool:continue
            d=signal(symbol,i-1,b,c,I,bal,lot)
            if not d:continue
            pos=(d,z.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-adverse*contract*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt,(DT(z.dt)-st).total_seconds()/86400)
        tar=en+d*tp;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=tp*contract*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt,(DT(z.dt)-st).total_seconds()/86400)
            lot=round(L+.01,2);pos=None;cool=i+1
    return R(tps,False,False,bal,dd*100,tr,mh,lot,when,(DT(b[-1].dt)-st).total_seconds()/86400)

def score(rs):
    done=sum(r.done for r in rs);alive=sum(not r.bust for r in rs);tps=sum(r.tps for r in rs)
    early=sum(r.bust and r.tps<9 for r in rs);speed=-sum(r.days for r in rs if r.done)
    return(done,-early,alive,tps,speed,-sum(r.dd for r in rs),-sum(r.hold for r in rs))

def search(symbol,seed):
    bars=x3.load(x3.DATA['XAUUSD']['url']) if symbol=='XAU' else b8.load();ss=starts(bars,seed)
    wins=[bars[s:] for s in ss];caches=[prep(w) for w in wins];cs=list(cfgs(symbol))
    print(f'=== {symbol} V21 VWAP UNBOUNDED / 5MIN ===',flush=True)
    print('SEED',seed,'configs',len(cs),'range',bars[0].dt,'->',bars[-1].dt,flush=True)
    print('TRAIN starts',[bars[s].dt for s in ss[:5]],flush=True);print('HOLDOUT starts',[bars[s].dt for s in ss[5:]],flush=True)
    stage=[]
    for n,c in enumerate(cs,1):
        rs=[run(symbol,w,c,I) for w,I in zip(wins[:3],caches[:3])];stage.append((score(rs),c))
        if n%250==0 or n==len(cs):print(f'PROGRESS {symbol} screen {n}/{len(cs)} bestDone={max(q[0][0] for q in stage)}/3',flush=True)
    pool=sorted(stage,key=lambda q:q[0],reverse=True)[:160];train=[]
    for n,(_,c) in enumerate(pool,1):
        rs=[run(symbol,w,c,I) for w,I in zip(wins[:5],caches[:5])];train.append((score(rs),c,rs))
        if n%20==0 or n==len(pool):
            z=max(train,key=lambda q:q[0]);print(f'PROGRESS {symbol} train {n}/{len(pool)} done={z[0][0]}/5 alive={z[0][2]}/5 sumTP={z[0][3]}',flush=True)
    train.sort(key=lambda q:q[0],reverse=True);ts,c,tr=train[0]
    ho=[run(symbol,w,c,I) for w,I in zip(wins[5:],caches[5:])];hs=score(ho)
    print(f'{symbol}_V21_BEST {c}',flush=True)
    print(f'{symbol}_TRAIN done={ts[0]}/5 alive={ts[2]}/5 sumTP={ts[3]} earlyBust={-ts[1]}',flush=True)
    print(f'{symbol}_HOLDOUT done={hs[0]}/5 alive={hs[2]}/5 sumTP={hs[3]} earlyBust={-hs[1]}',flush=True)
    for j,(s,r) in enumerate(zip(ss,tr+ho),1):
        tag='TR' if j<=5 else 'HO';print(f'{symbol}{j:02d}[{tag}] start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
    return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);ap.add_argument('--seed',type=int);a=ap.parse_args();return search(a.symbol,seed_value(a.seed))
if __name__=='__main__':sys.exit(main())
