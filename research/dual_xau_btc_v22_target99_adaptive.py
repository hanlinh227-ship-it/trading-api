#!/usr/bin/env python3
"""V22 target-99 adaptive progressive TP backtest.

PASS is strict: only 99/99 TP stages, including the 1.00-lot TP.
Locked: $20 start, XAU TP=3, BTC TP=300, no SL/cut/timeout, one position,
+0.01 lot after TP only, >=5m cooldown. No fixed completion-time limit.

Changes vs V21:
- phase boundary moved to EARLY<=0.10, MID<=0.75, LATE>0.75 so XAU does not
  choke immediately at 0.51;
- adds VWAP liquidity-sweep/reclaim and compression-breakout entry families;
- BTC EARLY searches sweep/reversal as well as retest to reduce early busts;
- XAU MID keeps higher cadence while preserving a VWAP anti-FOMO ceiling;
- selection score requires 99/99 first, then maximizes worst-window progress before
  aggregate TP count; a lucky single window cannot dominate;
- prints phase entry/rejection diagnostics for the locked winner.
"""
from __future__ import annotations
import argparse, sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import dual_xau_btc_v21_vwap_unbounded as v21

C=v21.C
R=v21.R


def phase(lot):
    if lot<=.10+1e-9:return 'early'
    if lot<=.75+1e-9:return 'mid'
    return 'late'


def cfgs(symbol):
    if symbol=='XAU':
        mas=[(8,21),(12,36)]; lbs=[3,5,8]; rs=[(44,70),(47,72)]
        em=['reclaim','sweep']; mm=['momentum','reclaim','compression']; lm=['reclaim','momentum']
        es=[6,12]; eh=[0]; eb=[1.4,1.8,2.2]
        evw=[48,96]; evmax=[.75,1.0,1.25]; er=[.15,.25]
        mvw=[48,96]; mvmax=[1.4,1.8,2.2]; mcf=[0,.03]; mb=[0,.05]
        ls=[6,12]; lh=[0]; lvw=[96,288]; lvmax=[1.0,1.4]; lsep=[0,.05]
        thin=432
    else:
        mas=[(5,20),(8,21),(12,36)]; lbs=[8,12,20]; rs=[(42,72),(45,74)]
        em=['sweep','retest','compression']; mm=['momentum','compression','retest']; lm=['retest','momentum']
        es=[12,24]; eh=[0,1]; eb=[1.4,1.8,2.2]
        evw=[48,96]; evmax=[.8,1.1,1.4]; er=[.20,.35]
        mvw=[48,96]; mvmax=[1.3,1.7,2.1]; mcf=[.02,.05]; mb=[0,.05]
        ls=[12,24]; lh=[0]; lvw=[96,288]; lvmax=[1.0,1.4]; lsep=[0,.05]
        thin=648
    dims=product(mas,lbs,rs,em,mm,lm,es,eh,eb,evw,evmax,er,mvw,mvmax,mcf,mb,ls,lh,lvw,lvmax,lsep)
    for n,z in enumerate(dims):
        if n%thin:continue
        ma,lb,r,a,b,c,d,e,f,g,h,j,k,l,m,o,p,q,s,t,u=z
        yield C(ma[0],ma[1],lb,r[0],r[1],a,b,c,d,e,f,g,h,j,k,l,m,o,p,q,s,t,u)


def family(mode,d,i,b,c,I,confirm,body):
    E=I['e'];A=I['a'];V=I['v'];x=b[i];p=b[i-1];pp=b[i-2];atr=max(A[i],1e-9);need=confirm*atr
    lo=max(0,i-c.lb);prior=b[lo:i];hi0=max(z.h for z in prior);lo0=min(z.l for z in prior)
    if abs(x.c-x.o)<body*atr:return 0
    if mode=='sweep':
        vw=V[c.early_vwap_win][i]
        if d>0:
            swept=p.l<min(z.l for z in b[max(0,i-c.lb-1):i-1])
            reject=(p.c-p.l)>=max(.35*(p.h-p.l),.08*atr)
            if swept and reject and p.c>=vw-.25*atr and x.c>p.h+need and x.c>x.o:return 1
        else:
            swept=p.h>max(z.h for z in b[max(0,i-c.lb-1):i-1])
            reject=(p.h-p.c)>=max(.35*(p.h-p.l),.08*atr)
            if swept and reject and p.c<=vw+.25*atr and x.c<p.l-need and x.c<x.o:return -1
        return 0
    if mode=='compression':
        rng=[z.h-z.l for z in b[max(0,i-6):i]]
        if len(rng)<5:return 0
        comp=max(rng[-4:])<=1.15*max(atr,1e-9)
        if not comp:return 0
        if d>0 and x.c>max(z.h for z in b[i-4:i])+need and x.c>x.o:return 1
        if d<0 and x.c<min(z.l for z in b[i-4:i])-need and x.c<x.o:return -1
        return 0
    return v21.family(mode,d,i,b,c,I,confirm,body)


def signal(symbol,i,b,c,I,bal,lot,diag=None):
    if i<650:return 0
    A=I['a'];RS=I['r'];V=I['v'];x=b[i];p=b[i-1];atr=max(A[i],1e-9)
    contract=100. if symbol=='XAU' else 1.;ph=phase(lot)
    if diag is not None:diag[ph+'_seen']=diag.get(ph+'_seen',0)+1
    if ph=='early':
        if atr*c.early_budget>=bal/(lot*contract):
            if diag is not None:diag['early_budget']=diag.get('early_budget',0)+1
            return 0
        d=v21.direction(i,c,I,.03 if symbol=='XAU' else .02)
        if not d or not v21.stable(i,d,c,I,c.early_stable,c.early_h1):
            if diag is not None:diag['early_trend']=diag.get('early_trend',0)+1
            return 0
        vw=V[c.early_vwap_win][i];dist=(x.c-vw)/atr
        if d>0:
            if not(-.15<=dist<=c.early_vwap_max):
                if diag is not None:diag['early_vwap']=diag.get('early_vwap',0)+1
                return 0
            if c.early_mode!='sweep' and p.l>V[c.early_vwap_win][i-1]+c.early_reclaim*atr:return 0
        else:
            if not(-c.early_vwap_max<=dist<=.15):
                if diag is not None:diag['early_vwap']=diag.get('early_vwap',0)+1
                return 0
            if c.early_mode!='sweep' and p.h<V[c.early_vwap_win][i-1]-c.early_reclaim*atr:return 0
        mode=c.early_mode;confirm=.01 if symbol=='XAU' else .025;body=0
    elif ph=='mid':
        d=v21.direction(i,c,I,0)
        if not d:return 0
        vw=V[c.mid_vwap_win][i];dist=(x.c-vw)/atr
        # wider anti-FOMO band than V21; still rejects extreme extension.
        if d>0 and not(-.20<=dist<=c.mid_vwap_max):return 0
        if d<0 and not(-c.mid_vwap_max<=dist<=.20):return 0
        mode=c.mid_mode;confirm=c.mid_confirm;body=c.mid_body
    else:
        d=v21.direction(i,c,I,c.late_sep)
        if not d or not v21.stable(i,d,c,I,c.late_stable,c.late_h1):return 0
        vw=V[c.late_vwap_win][i];dist=(x.c-vw)/atr
        if d>0 and not(-.10<=dist<=c.late_vwap_max):return 0
        if d<0 and not(-c.late_vwap_max<=dist<=.10):return 0
        mode=c.late_mode;confirm=.015 if symbol=='XAU' else .03;body=0
    if d>0 and not(c.rlo<=RS[i]<=c.rhi):return 0
    if d<0 and not((100-c.rhi)<=RS[i]<=(100-c.rlo)):return 0
    s=family(mode,d,i,b,c,I,confirm,body)
    if s and diag is not None:diag[ph+'_entry']=diag.get(ph+'_entry',0)+1
    return s


def run(symbol,b,c,I,diag=None):
    bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;st=v21.DT(b[0].dt);when=b[0].dt
    contract=100. if symbol=='XAU' else 1.;tp=3. if symbol=='XAU' else 300.
    for i in range(652,len(b)):
        z=b[i]
        if pos is None:
            if i<=cool:continue
            d=signal(symbol,i-1,b,c,I,bal,lot,diag)
            if not d:continue
            pos=(d,z.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-adverse*contract*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt,(v21.DT(z.dt)-st).total_seconds()/86400)
        tar=en+d*tp;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=tp*contract*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt,(v21.DT(z.dt)-st).total_seconds()/86400)
            lot=round(L+.01,2);pos=None;cool=i+1
    return R(tps,False,False,bal,dd*100,tr,mh,lot,when,(v21.DT(b[-1].dt)-st).total_seconds()/86400)


def score(rs):
    done=sum(r.done for r in rs);worst=min(r.tps for r in rs);alive=sum(not r.bust for r in rs)
    tps=sum(r.tps for r in rs);early=sum(r.bust and r.tps<9 for r in rs)
    return(done,worst,-early,alive,tps,-sum(r.dd for r in rs),-sum(r.hold for r in rs))


def search(symbol,seed):
    bars=v21.x3.load(v21.x3.DATA['XAUUSD']['url']) if symbol=='XAU' else v21.b8.load()
    ss=v21.starts(bars,seed);wins=[bars[s:] for s in ss];caches=[v21.prep(w) for w in wins];cs=list(cfgs(symbol))
    print(f'=== {symbol} V22 TARGET99 ADAPTIVE VWAP / 5MIN ===',flush=True)
    print('SEED',seed,'configs',len(cs),'range',bars[0].dt,'->',bars[-1].dt,flush=True)
    print('TRAIN starts',[bars[s].dt for s in ss[:5]],flush=True);print('HOLDOUT starts',[bars[s].dt for s in ss[5:]],flush=True)
    stage=[]
    for n,c in enumerate(cs,1):
        rs=[run(symbol,w,c,I) for w,I in zip(wins[:3],caches[:3])];stage.append((score(rs),c))
        if n%250==0 or n==len(cs):
            z=max(stage,key=lambda q:q[0]);print(f'PROGRESS {symbol} screen {n}/{len(cs)} done={z[0][0]}/3 worstTP={z[0][1]}',flush=True)
    pool=sorted(stage,key=lambda q:q[0],reverse=True)[:200];train=[]
    for n,(_,c) in enumerate(pool,1):
        rs=[run(symbol,w,c,I) for w,I in zip(wins[:5],caches[:5])];train.append((score(rs),c,rs))
        if n%25==0 or n==len(pool):
            z=max(train,key=lambda q:q[0]);print(f'PROGRESS {symbol} train {n}/{len(pool)} done={z[0][0]}/5 worstTP={z[0][1]} alive={z[0][3]}/5 sumTP={z[0][4]}',flush=True)
    train.sort(key=lambda q:q[0],reverse=True);ts,c,tr=train[0]
    ho=[run(symbol,w,c,I) for w,I in zip(wins[5:],caches[5:])];hs=score(ho)
    print(f'{symbol}_V22_BEST {c}',flush=True)
    print(f'{symbol}_TRAIN done={ts[0]}/5 worstTP={ts[1]} alive={ts[3]}/5 sumTP={ts[4]} earlyBust={-ts[2]}',flush=True)
    print(f'{symbol}_HOLDOUT done={hs[0]}/5 worstTP={hs[1]} alive={hs[3]}/5 sumTP={hs[4]} earlyBust={-hs[2]}',flush=True)
    for j,(s,r) in enumerate(zip(ss,tr+ho),1):
        tag='TR' if j<=5 else 'HO';print(f'{symbol}{j:02d}[{tag}] start={bars[s].dt} TP={r.tps}/99 PASS={r.done} bust={r.bust} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
    diag={}
    for w,I in zip(wins,caches):run(symbol,w,c,I,diag)
    print(f'{symbol}_DIAG {diag}',flush=True)
    strict_pass=(ts[0]==5 and hs[0]==5)
    print(f'{symbol}_STRICT_PASS={strict_pass}',flush=True)
    return 0


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);ap.add_argument('--seed',type=int);a=ap.parse_args()
    return search(a.symbol,v21.seed_value(a.seed))

if __name__=='__main__':sys.exit(main())
