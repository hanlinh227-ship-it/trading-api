#!/usr/bin/env python3
"""V19 paced-survival XAU+BTC backtest.

Locked rules:
- $20 start, 0.02 -> 1.00, +0.01 only after TP
- XAU TP=3 price, BTC TP=300 price
- no SL / no Smart Cut / no timeout close
- one open position per symbol
- after TP skip one complete M5 bar => >=5 minute cooldown
- target must complete inside 60 calendar days
- 10 reproducible rotating 60-day windows per GitHub run

V19 repairs V18:
1) self-contained indicator cache includes every EMA used by both symbols/configs.
2) entry search keeps reclaim/breakout/momentum families.
3) two chain phases:
   EARLY: survival guard while equity is fragile.
   LATE: reversal guard once lot is large, requiring HTF alignment + non-contracting trend.
4) scoring rewards <=60d completion first, then completion speed, then pace/TP, survival and DD.
"""
from __future__ import annotations
import argparse, os, random, sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8

TOP=180; STAGE1=3; DAYS=60
EMA_KEYS=(5,8,12,20,21,36,50,60,150,240,600)

@dataclass(frozen=True)
class C:
 mode:str; fast:int; slow:int; lb:int; rlo:int; rhi:int; confirm:float
 budget:float; chase:float; sep:float; stable:int; early_guard:float; early_h1:int; body:float
 late_guard:float; late_stable:int; late_chase:float; late_h1:int

@dataclass
class R:
 tps:int; done:bool; bust:bool; eq:float; dd:float; trades:int; hold:int; lot:float; when:str; days:float

def D(x): return datetime.fromisoformat(str(x))

def seed_value(cli):
 if cli is not None:return cli
 rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
 if rid and rid.isdigit():return int(rid)*100+int(att)
 import time;return int(time.time_ns()%2147483647)

def cfgs(symbol):
 if symbol=='XAU':
  fam=['reclaim','breakout','momentum']; mas=[(8,21),(12,36),(20,50)]; lbs=[3,5,8,12]
  rs=[(45,68),(48,70),(50,72)]; cf=[0,.05,.10]; budgets=[1.5,2.0,2.5]; chase=[.6,.9,1.2]
  late=[.30,.45,.60]; late_ch=[.45,.65,.85]
 else:
  fam=['breakout','retest','momentum']; mas=[(5,20),(8,21),(12,36)]; lbs=[8,12,20,32]
  rs=[(46,70),(48,72),(50,74)]; cf=[.05,.08,.12]; budgets=[3.,4.,5.]; chase=[1.4,1.8,2.2]
  late=[.35,.50,.65]; late_ch=[1.0,1.3,1.6]
 sep=[0,.08,.15]; stable=[3,6,12]; eg=[.08,.15,.25]; eh=[0,1]; bodies=[0,.12,.25]
 lst=[6,12,24]; lh=[0,1]
 # broad deterministic thinning across all dimensions
 for n,z in enumerate(product(fam,mas,lbs,rs,cf,budgets,chase,sep,stable,eg,eh,bodies,late,lst,late_ch,lh)):
  if n%1458: continue
  m,ma,lb,r,c,b,ch,se,st,egh,ehi,bo,lg,ls,lc,lhi=z
  yield C(m,ma[0],ma[1],lb,r[0],r[1],c,b,ch,se,st,egh,ehi,bo,lg,ls,lc,lhi)

def prep(b):
 cl=[z.c for z in b]
 return {'e':{p:x3.ema(cl,p) for p in EMA_KEYS},'a':x3.atr(b),'r':x3.rsi(cl)}

def starts(bars,seed):
 cutoff=D(bars[-1].dt)-timedelta(days=DAYS)
 valid=[i for i,z in enumerate(bars) if i>=700 and D(z.dt)<=cutoff]
 return sorted(random.Random(seed).sample(valid,10))

def window(bars,s):
 end=D(bars[s].dt)+timedelta(days=DAYS);j=s
 while j<len(bars) and D(bars[j].dt)<=end:j+=1
 return bars[s:j]

def regime(i,c,I):
 E=I['e'];A=I['a'];atr=max(A[i],1e-9)
 up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>=E[c.fast][i-3] and E[c.slow][i]>=E[c.slow][i-3] and E[60][i]>E[150][i]
 dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<=E[c.fast][i-3] and E[c.slow][i]<=E[c.slow][i-3] and E[60][i]<E[150][i]
 if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr:return 0
 return 1 if up else -1 if dn else 0

def stable_guard(i,d,c,I,n,h1):
 E=I['e'];j=i-n
 if j<0:return False
 if d>0:
  if not(E[c.fast][j]>E[c.slow][j] and E[60][j]>E[150][j]):return False
  if h1 and not(E[240][i]>E[600][i] and E[240][i]>=E[240][i-6]):return False
 else:
  if not(E[c.fast][j]<E[c.slow][j] and E[60][j]<E[150][j]):return False
  if h1 and not(E[240][i]<E[600][i] and E[240][i]<=E[240][i-6]):return False
 return True

def signal(symbol,i,b,c,I,bal,lot):
 if i<650:return 0
 E=I['e'];A=I['a'];RS=I['r'];x=b[i];p=b[i-1];pp=b[i-2];atr=max(A[i],1e-9)
 contract=100. if symbol=='XAU' else 1.
 if atr*c.budget>=bal/(lot*contract):return 0
 d=regime(i,c,I)
 if not d:return 0
 # Early phase: protect fragile $20 chain.
 if lot<=c.early_guard+1e-9 and not stable_guard(i,d,c,I,c.stable,c.early_h1):return 0
 # Late phase: do NOT simply loosen forever; defend large lots from major reversal.
 max_chase=c.chase
 if lot>=c.late_guard-1e-9:
  if not stable_guard(i,d,c,I,c.late_stable,c.late_h1):return 0
  max_chase=min(max_chase,c.late_chase)
  spread_now=abs(E[c.fast][i]-E[c.slow][i]);spread_old=abs(E[c.fast][i-c.late_stable]-E[c.slow][i-c.late_stable])
  if spread_now<spread_old*.85:return 0
  # avoid entering against fresh medium-trend deceleration
  if d>0 and E[60][i]<E[60][i-3]:return 0
  if d<0 and E[60][i]>E[60][i-3]:return 0
 if abs(x.c-E[c.fast][i])>max_chase*atr:return 0
 if abs(x.c-x.o)<c.body*atr:return 0
 if d>0 and not(c.rlo<=RS[i]<=c.rhi):return 0
 if d<0 and not((100-c.rhi)<=RS[i]<=(100-c.rlo)):return 0
 need=c.confirm*atr;lo=max(0,i-c.lb);hi0=max(z.h for z in b[lo:i]);lo0=min(z.l for z in b[lo:i])
 if c.mode=='breakout':
  if d>0 and p.c>hi0-(p.h-p.c) and x.c>p.h+need and x.c>x.o:return 1
  if d<0 and p.c<lo0+(p.c-p.l) and x.c<p.l-need and x.c<x.o:return -1
 elif c.mode in ('reclaim','retest'):
  touch=p.l<=E[c.fast][i-1]<=p.h
  if d>0 and touch and p.c>=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o:return 1
  if d<0 and touch and p.c<=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o:return -1
 else:
  shock=max(abs(p.c-p.o),abs(x.c-x.o))
  shock_cap=1.8 if lot>=c.late_guard-1e-9 else 2.2
  if shock>shock_cap*atr:return 0
  if d>0 and pp.c<p.c<x.c and p.c>p.o and x.c>x.o and x.c>p.h+need:return 1
  if d<0 and pp.c>p.c>x.c and p.c<p.o and x.c<x.o and x.c<p.l-need:return -1
 return 0

def run(symbol,b,c,I):
 bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;st=D(b[0].dt);when=b[0].dt
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
  if flt<=0:return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt,(D(z.dt)-st).total_seconds()/86400)
  tar=en+d*tp;hit=z.h>=tar if d>0 else z.l<=tar
  if hit:
   bal+=tp*contract*L;peak=max(peak,bal);tps+=1;when=z.dt
   if L>=1.-1e-9:return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt,(D(z.dt)-st).total_seconds()/86400)
   lot=round(L+.01,2);pos=None;cool=i+1
 return R(tps,False,False,bal,dd*100,tr,mh,lot,when,DAYS)

def score(rs):
 done=sum(r.done for r in rs);speed=-sum(r.days for r in rs if r.done);tps=sum(r.tps for r in rs);alive=sum(not r.bust for r in rs)
 # pace bonus measures progress toward 99 within 60d without overriding true completion count.
 pace=sum(min(r.tps/99.,1.) for r in rs)
 return(done,speed,pace,tps,alive,-sum(r.dd for r in rs),-sum(r.hold for r in rs))

def search(symbol,seed):
 bars=x3.load(x3.DATA['XAUUSD']['url']) if symbol=='XAU' else b8.load();cs=list(cfgs(symbol));ss=starts(bars,seed)
 wins=[window(bars,s) for s in ss];caches=[prep(w) for w in wins]
 print(f'=== {symbol} V19 PACED SURVIVAL / 60D / 5MIN ===',flush=True)
 print('SEED',seed,'configs',len(cs),'range',bars[0].dt,'->',bars[-1].dt,flush=True)
 print('windows',[(bars[s].dt,w[-1].dt) for s,w in zip(ss,wins)],flush=True)
 stage=[]
 for n,c in enumerate(cs,1):
  rs=[run(symbol,w,c,I) for w,I in zip(wins[:STAGE1],caches[:STAGE1])];sc=score(rs);stage.append((sc,c,rs))
  if n%250==0 or n==len(cs):print(f'PROGRESS {symbol} stage1 {n}/{len(cs)} best60={max(q[0][0] for q in stage)}/3',flush=True)
 surv=[q for q in stage if q[0][0]>=1]
 pool=sorted(surv if surv else stage,key=lambda q:q[0],reverse=True)[:TOP]
 print('POOL',len(pool),'stage1>=1',len(surv),flush=True);best=None
 for n,(sc,c,r3) in enumerate(pool,1):
  rs=r3+[run(symbol,w,c,I) for w,I in zip(wins[3:],caches[3:])];full=score(rs)
  if best is None or full>best[0]:best=(full,c,rs)
  if n%10==0 or full[0]>=5 or n==len(pool):print(f'PROGRESS {symbol} stage2 {n}/{len(pool)} pass60={full[0]}/10 sumTP={full[3]} alive={full[4]}/10',flush=True)
 sc,c,rs=best
 print(f'{symbol}_V19_BEST seed={seed} {c} pass60={sc[0]}/10 sumTP={sc[3]} alive={sc[4]}/10',flush=True)
 for j,(s,r) in enumerate(zip(ss,rs),1):print(f'{symbol}{j:02d} start={bars[s].dt} TP={r.tps}/99 done60={r.done} bust={r.bust} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
 return 0

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);ap.add_argument('--seed',type=int);a=ap.parse_args();return search(a.symbol,seed_value(a.seed))
if __name__=='__main__':sys.exit(main())
