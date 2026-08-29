#!/usr/bin/env python3
"""V20 three-phase, train/holdout XAU+BTC backtest.

Locked rules remain unchanged:
- $20 start
- 0.02 -> 1.00, +0.01 only after actual TP
- XAU TP = 3.00 price units; BTC TP = 300.00 price units
- no SL, no Smart Cut, no timeout close
- one open position per symbol
- after TP skip one complete M5 bar (>=5 minutes)
- target horizon <=60 calendar days

V20 changes only entry intelligence:
A) 0.02-0.10: survival-first.
B) 0.11-0.50: cadence-first.
C) 0.51-1.00: reversal-defense.

To reduce window overfit, 10 rotating 60-day windows are split 5 TRAIN + 5 HOLDOUT.
Candidate ranking uses TRAIN only. HOLDOUT is reported afterwards and never used to select the winner.
"""
from __future__ import annotations
import argparse, os, random, sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8

DAYS=60
EMA_KEYS=(5,8,12,20,21,36,50,60,100,150,240,600)

@dataclass(frozen=True)
class C:
    fast:int; slow:int; lb:int; rlo:int; rhi:int
    early_mode:str; mid_mode:str; late_mode:str
    early_stable:int; early_h1:int; early_chase:float; early_budget:float
    mid_chase:float; mid_confirm:float; mid_body:float
    late_stable:int; late_h1:int; late_chase:float; late_sep:float

@dataclass
class R:
    tps:int; done:bool; bust:bool; balance:float; dd:float; trades:int
    hold:int; lot:float; when:str; days:float

def DT(x): return datetime.fromisoformat(str(x))

def seed_value(cli):
    if cli is not None: return cli
    rid=os.getenv('GITHUB_RUN_ID'); att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit(): return int(rid)*100+int(att)
    import time
    return int(time.time_ns()%2147483647)

def configs(symbol):
    # Curated search: phase logic varies, but keep the space compact enough for repeated random-window validation.
    if symbol=='XAU':
        mas=[(8,21),(12,36),(20,50)]
        lbs=[3,5,8]
        rs=[(44,68),(47,70),(50,72)]
        early_modes=['reclaim']
        mid_modes=['reclaim','momentum','breakout']
        late_modes=['reclaim','breakout']
        est=[6,12,24]; eh=[0,1]; ech=[.40,.55,.70]; eb=[1.2,1.6,2.0]
        mch=[.8,1.1,1.4]; mcf=[0,.04,.08]; mb=[0,.10]
        lst=[12,24]; lh=[0,1]; lch=[.40,.55,.70]; lsep=[.05,.12]
        thin=972
    else:
        mas=[(5,20),(8,21),(12,36)]
        lbs=[8,12,20]
        rs=[(44,70),(47,72),(50,74)]
        early_modes=['retest']
        mid_modes=['breakout','momentum','retest']
        late_modes=['retest','breakout']
        est=[12,24,36]; eh=[1]; ech=[.70,1.00,1.30]; eb=[2.0,2.5,3.0]
        mch=[1.4,1.8,2.2]; mcf=[.03,.06,.10]; mb=[0,.10]
        lst=[12,24,36]; lh=[0,1]; lch=[.8,1.1,1.4]; lsep=[.05,.12]
        thin=972
    dims=product(mas,lbs,rs,early_modes,mid_modes,late_modes,est,eh,ech,eb,mch,mcf,mb,lst,lh,lch,lsep)
    for n,z in enumerate(dims):
        if n%thin: continue
        ma,lb,r,em,mm,lm,es,ehi,ec,ebu,mc,mcfv,body,ls,lhi,lc,lsp=z
        yield C(ma[0],ma[1],lb,r[0],r[1],em,mm,lm,es,ehi,ec,ebu,mc,mcfv,body,ls,lhi,lc,lsp)

def prep(b):
    cl=[z.c for z in b]
    return {'e':{p:x3.ema(cl,p) for p in EMA_KEYS}, 'a':x3.atr(b), 'r':x3.rsi(cl)}

def starts(bars,seed):
    cutoff=DT(bars[-1].dt)-timedelta(days=DAYS)
    valid=[i for i,z in enumerate(bars) if i>=700 and DT(z.dt)<=cutoff]
    return sorted(random.Random(seed).sample(valid,10))

def window(bars,s):
    end=DT(bars[s].dt)+timedelta(days=DAYS); j=s
    while j<len(bars) and DT(bars[j].dt)<=end: j+=1
    return bars[s:j]

def direction(i,c,I,sep=0.0):
    E=I['e']; A=I['a']; atr=max(A[i],1e-9)
    if abs(E[c.fast][i]-E[c.slow][i]) < sep*atr: return 0
    up=(E[c.fast][i]>E[c.slow][i] and E[60][i]>E[150][i] and E[c.fast][i]>=E[c.fast][i-3])
    dn=(E[c.fast][i]<E[c.slow][i] and E[60][i]<E[150][i] and E[c.fast][i]<=E[c.fast][i-3])
    return 1 if up else -1 if dn else 0

def stable(i,d,c,I,n,h1):
    E=I['e']; j=i-n
    if j<0:return False
    if d>0:
        if not(E[c.fast][j]>E[c.slow][j] and E[60][j]>E[150][j]):return False
        if E[60][i]<E[60][i-3]:return False
        if h1 and not(E[240][i]>E[600][i] and E[240][i]>=E[240][i-6]):return False
    else:
        if not(E[c.fast][j]<E[c.slow][j] and E[60][j]<E[150][j]):return False
        if E[60][i]>E[60][i-3]:return False
        if h1 and not(E[240][i]<E[600][i] and E[240][i]<=E[240][i-6]):return False
    return True

def phase(lot):
    if lot<=.10+1e-9:return 'early'
    if lot<=.50+1e-9:return 'mid'
    return 'late'

def family_signal(mode,d,i,b,c,I,confirm,body):
    E=I['e']; A=I['a']; x=b[i]; p=b[i-1]; pp=b[i-2]; atr=max(A[i],1e-9)
    need=confirm*atr
    lo=max(0,i-c.lb); hi0=max(z.h for z in b[lo:i]); lo0=min(z.l for z in b[lo:i])
    if abs(x.c-x.o)<body*atr:return 0
    if mode=='breakout':
        if d>0 and p.c>hi0-(p.h-p.c) and x.c>p.h+need and x.c>x.o:return 1
        if d<0 and p.c<lo0+(p.c-p.l) and x.c<p.l-need and x.c<x.o:return -1
    elif mode in ('reclaim','retest'):
        touch=p.l<=E[c.fast][i-1]<=p.h
        if d>0 and touch and p.c>=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o:return 1
        if d<0 and touch and p.c<=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o:return -1
    else:
        shock=max(abs(p.c-p.o),abs(x.c-x.o))
        if shock>2.0*atr:return 0
        if d>0 and pp.c<p.c<x.c and p.c>p.o and x.c>x.o and x.c>p.h+need:return 1
        if d<0 and pp.c>p.c>x.c and p.c<p.o and x.c<x.o and x.c<p.l-need:return -1
    return 0

def signal(symbol,i,b,c,I,bal,lot):
    if i<650:return 0
    E=I['e']; A=I['a']; RS=I['r']; x=b[i]; atr=max(A[i],1e-9)
    contract=100. if symbol=='XAU' else 1.
    ph=phase(lot)

    if ph=='early':
        # Initial capital is the hardest constraint: only stable trend + pullback/retest entries.
        if atr*c.early_budget >= bal/(lot*contract):return 0
        d=direction(i,c,I,.05)
        if not d or not stable(i,d,c,I,c.early_stable,c.early_h1):return 0
        chase=c.early_chase; mode=c.early_mode; confirm=.02 if symbol=='XAU' else .05; body=0.
        # BTC early: avoid locally extended impulse; XAU early: avoid entering far from EMA20/fast.
        if abs(x.c-E[c.fast][i])>chase*atr:return 0
        if symbol=='BTC' and abs(x.c-E[20][i])>1.4*atr:return 0
    elif ph=='mid':
        # Once the chain has a buffer, prioritize cadence but keep the dominant trend filter.
        d=direction(i,c,I,0.0)
        if not d:return 0
        chase=c.mid_chase; mode=c.mid_mode; confirm=c.mid_confirm; body=c.mid_body
        if abs(x.c-E[c.fast][i])>chase*atr:return 0
        # Block fresh fast/slow cross deterioration.
        if d>0 and E[c.fast][i]-E[c.slow][i] < .75*(E[c.fast][i-3]-E[c.slow][i-3]):return 0
        if d<0 and E[c.slow][i]-E[c.fast][i] < .75*(E[c.slow][i-3]-E[c.fast][i-3]):return 0
    else:
        # Large lots: require sustained structure and HTF agreement; no blind cadence relaxation.
        d=direction(i,c,I,c.late_sep)
        if not d or not stable(i,d,c,I,c.late_stable,c.late_h1):return 0
        chase=c.late_chase; mode=c.late_mode; confirm=.03 if symbol=='XAU' else .06; body=.05
        if abs(x.c-E[c.fast][i])>chase*atr:return 0
        spread=abs(E[c.fast][i]-E[c.slow][i]); old=abs(E[c.fast][i-c.late_stable]-E[c.slow][i-c.late_stable])
        if spread<old*.90:return 0

    if d>0 and not(c.rlo<=RS[i]<=c.rhi):return 0
    if d<0 and not((100-c.rhi)<=RS[i]<=(100-c.rlo)):return 0
    return family_signal(mode,d,i,b,c,I,confirm,body)

def run(symbol,b,c,I):
    bal=20.; peak=20.; dd=0.; lot=.02; tps=tr=mh=0; pos=None; cool=-1; st=DT(b[0].dt); when=b[0].dt
    contract=100. if symbol=='XAU' else 1.; tp=3. if symbol=='XAU' else 300.
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool:continue
            d=signal(symbol,i-1,b,c,I,bal,lot)
            if not d:continue
            pos=(d,z.o,lot,i);tr+=1
        d,en,L,ei=pos; mh=max(mh,i-ei+1)
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en)
        flt=bal-adverse*contract*L
        dd=max(dd,(peak-flt)/peak)
        # Conservative same-bar rule: bust is evaluated before TP.
        if flt<=0:
            return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt,(DT(z.dt)-st).total_seconds()/86400)
        tar=en+d*tp; hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=tp*contract*L; peak=max(peak,bal); tps+=1; when=z.dt
            if L>=1.-1e-9:
                return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt,(DT(z.dt)-st).total_seconds()/86400)
            lot=round(L+.01,2); pos=None; cool=i+1
    return R(tps,False,False,bal,dd*100,tr,mh,lot,when,DAYS)

def score(rs):
    done=sum(r.done for r in rs); alive=sum(not r.bust for r in rs); tps=sum(r.tps for r in rs)
    speed=-sum(r.days for r in rs if r.done)
    # Early-stage deaths are heavily penalized because that was BTC V19's dominant failure.
    early_bust=sum(r.bust and r.tps<9 for r in rs)
    progress=sum(min(r.tps/99.,1.) for r in rs)
    return (done,-early_bust,alive,progress,tps,speed,-sum(r.dd for r in rs),-sum(r.hold for r in rs))

def search(symbol,seed):
    bars=x3.load(x3.DATA['XAUUSD']['url']) if symbol=='XAU' else b8.load()
    cs=list(configs(symbol)); ss=starts(bars,seed); wins=[window(bars,s) for s in ss]; caches=[prep(w) for w in wins]
    print(f'=== {symbol} V20 3PHASE TRAIN/HOLDOUT / 60D / 5MIN ===',flush=True)
    print('SEED',seed,'configs',len(cs),'range',bars[0].dt,'->',bars[-1].dt,flush=True)
    print('TRAIN',[(bars[s].dt,w[-1].dt) for s,w in zip(ss[:5],wins[:5])],flush=True)
    print('HOLDOUT',[(bars[s].dt,w[-1].dt) for s,w in zip(ss[5:],wins[5:])],flush=True)

    # Stage 1: cheap 3-window train screening.
    stage=[]
    for n,c in enumerate(cs,1):
        rs=[run(symbol,w,c,I) for w,I in zip(wins[:3],caches[:3])]
        stage.append((score(rs),c))
        if n%250==0 or n==len(cs):
            print(f'PROGRESS {symbol} screen {n}/{len(cs)} bestDone={max(q[0][0] for q in stage)}/3',flush=True)
    pool=sorted(stage,key=lambda q:q[0],reverse=True)[:160]

    # Stage 2: rank using all five TRAIN windows only.
    train_rank=[]
    for n,(_,c) in enumerate(pool,1):
        rs=[run(symbol,w,c,I) for w,I in zip(wins[:5],caches[:5])]
        train_rank.append((score(rs),c,rs))
        if n%20==0 or n==len(pool):
            best=max(train_rank,key=lambda q:q[0])
            print(f'PROGRESS {symbol} train {n}/{len(pool)} done={best[0][0]}/5 alive={best[0][2]}/5 sumTP={best[0][4]}',flush=True)
    train_rank.sort(key=lambda q:q[0],reverse=True)
    train_sc,best_c,train_rs=train_rank[0]

    # Locked holdout evaluation: no candidate reselection after seeing these results.
    hold_rs=[run(symbol,w,best_c,I) for w,I in zip(wins[5:],caches[5:])]
    hold_sc=score(hold_rs)
    print(f'{symbol}_V20_BEST {best_c}',flush=True)
    print(f'{symbol}_TRAIN done60={train_sc[0]}/5 alive={train_sc[2]}/5 sumTP={train_sc[4]} earlyBust={-train_sc[1]}',flush=True)
    print(f'{symbol}_HOLDOUT done60={hold_sc[0]}/5 alive={hold_sc[2]}/5 sumTP={hold_sc[4]} earlyBust={-hold_sc[1]}',flush=True)
    allrs=train_rs+hold_rs
    for j,(s,r) in enumerate(zip(ss,allrs),1):
        tag='TR' if j<=5 else 'HO'
        print(f'{symbol}{j:02d}[{tag}] start={bars[s].dt} TP={r.tps}/99 done60={r.done} bust={r.bust} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
    return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--symbol',choices=['XAU','BTC'],required=True); ap.add_argument('--seed',type=int)
    a=ap.parse_args(); return search(a.symbol,seed_value(a.seed))

if __name__=='__main__': sys.exit(main())
