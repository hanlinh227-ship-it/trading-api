#!/usr/bin/env python3
"""V18 adaptive XAU+BTC 60-day target harness.

Target and locked execution:
- start equity $20
- independent 0.02 -> 1.00 lot chains, +0.01 only after TP
- XAU TP = 3.00 price; BTC TP = 300.00 price
- no SL / no cut / no timeout close
- one position per symbol
- after a TP skip ONE complete M5 bar => conservative >=5 minutes before a new order
- every validation window is capped at 60 calendar days
- every GitHub run samples 10 different reproducible 60-day windows

V18 changes entry architecture rather than only retuning thresholds.
XAU families: reclaim, breakout, momentum continuation.
BTC families: breakout, retest, momentum continuation.
Early chain uses stricter survival/regime guards; later chain relaxes to increase cadence.
Scoring: 60-day completions first, then faster completion, total TP, alive windows, DD.
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
import dual_xau_btc_v16_entry_repair as v16

TOP=160; STAGE1=3; DAYS=60

@dataclass(frozen=True)
class C:
 mode:str; fast:int; slow:int; lb:int; rlo:int; rhi:int; confirm:float
 budget:float; chase:float; sep:float; stable:int; guard:float; h1:int; body:float

@dataclass
class R:
 tps:int; done:bool; bust:bool; eq:float; dd:float; trades:int; hold:int; lot:float; when:str; days:float

def dt(s): return datetime.fromisoformat(str(s))

def seed_value(cli):
 if cli is not None:return cli
 rid=os.getenv('GITHUB_RUN_ID'); att=os.getenv('GITHUB_RUN_ATTEMPT','1')
 if rid and rid.isdigit():return int(rid)*100+int(att)
 import time;return int(time.time_ns()%2147483647)

def configs(symbol):
 if symbol=='XAU':
  families=['reclaim','breakout','momentum']; mas=[(8,21),(12,36),(20,50)]; lbs=[3,5,8,12]
  rb=[(45,68),(48,70),(50,72)]; conf=[0,.05,.10]; budgets=[1.5,2.0,2.5]; chase=[.6,.9,1.2]
 else:
  families=['breakout','retest','momentum']; mas=[(5,20),(8,21),(12,36)]; lbs=[8,12,20,32]
  rb=[(46,70),(48,72),(50,74)]; conf=[.05,.08,.12]; budgets=[3.0,4.0,5.0]; chase=[1.4,1.8,2.2]
 sep=[0,.08,.15]; stable=[3,6,12]; guards=[.08,.15,.25]; h1=[0,1]; bodies=[0,.12,.25]
 # Deterministic thinning keeps broad family coverage but workflow tractable.
 for n,z in enumerate(product(families,mas,lbs,rb,conf,budgets,chase,sep,stable,guards,h1,bodies)):
  if n%54:continue
  m,ma,lb,r,cf,bu,ch,se,st,g,hh,bo=z
  yield C(m,ma[0],ma[1],lb,r[0],r[1],cf,bu,ch,se,st,g,hh,bo)

def prep(symbol,b):
 return v16.prep_xau(b) if symbol=='XAU' else v16.prep_btc(b)

def window_starts(bars,seed):
 last=dt(bars[-1].dt); cutoff=last-timedelta(days=DAYS)
 valid=[i for i,z in enumerate(bars) if dt(z.dt)<=cutoff and i>=700]
 r=random.Random(seed);return sorted(r.sample(valid,10))

def make_window(bars,s):
 end=dt(bars[s].dt)+timedelta(days=DAYS)
 j=s
 while j<len(bars) and dt(bars[j].dt)<=end:j+=1
 return bars[s:j]

def side_regime(i,c,I):
 E=I['e']; A=I['a']; atr=max(A[i],1e-9)
 up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>=E[c.fast][i-3] and E[c.slow][i]>=E[c.slow][i-3] and E[60][i]>E[150][i]
 dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<=E[c.fast][i-3] and E[c.slow][i]<=E[c.slow][i-3] and E[60][i]<E[150][i]
 if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr:return 0
 return 1 if up else -1 if dn else 0

def early_guard(i,d,c,I,lot):
 if lot>c.guard+1e-9:return True
 E=I['e'];A=I['a'];j=i-c.stable
 if j<0:return False
 if d>0 and not(E[c.fast][j]>E[c.slow][j] and E[60][j]>E[150][j]):return False
 if d<0 and not(E[c.fast][j]<E[c.slow][j] and E[60][j]<E[150][j]):return False
 if c.h1:
  if d>0 and not(E[240][i]>E[600][i]):return False
  if d<0 and not(E[240][i]<E[600][i]):return False
 return True

def signal(symbol,i,b,c,I,bal,lot):
 if i<650:return 0
 E=I['e'];A=I['a'];RS=I['r'];x=b[i];p=b[i-1];pp=b[i-2];atr=max(A[i],1e-9)
 contract=100. if symbol=='XAU' else 1.
 if atr*c.budget>=bal/(lot*contract):return 0
 d=side_regime(i,c,I)
 if not d or not early_guard(i,d,c,I,lot):return 0
 if abs(x.c-E[c.fast][i])>c.chase*atr:return 0
 if abs(x.c-x.o)<c.body*atr:return 0
 if d>0 and not(c.rlo<=RS[i]<=c.rhi):return 0
 if d<0 and not((100-c.rhi)<=RS[i]<=(100-c.rlo)):return 0
 need=c.confirm*atr
 # local structure generated directly to avoid dependency on one legacy breakout cache
 lo=max(0,i-c.lb); hi0=max(z.h for z in b[lo:i]); lo0=min(z.l for z in b[lo:i])
 if c.mode=='breakout':
  if d>0 and p.c>hi0-(p.h-p.c) and x.c>p.h+need and x.c>x.o:return 1
  if d<0 and p.c<lo0+(p.c-p.l) and x.c<p.l-need and x.c<x.o:return -1
 elif c.mode=='reclaim' or c.mode=='retest':
  touch=(p.l<=E[c.fast][i-1]<=p.h)
  if d>0 and touch and p.c>=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o:return 1
  if d<0 and touch and p.c<=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o:return -1
 else:
  # momentum continuation: two same-direction closes, but reject obvious shock/exhaustion.
  shock=max(abs(p.c-p.o),abs(x.c-x.o))
  if shock>2.2*atr:return 0
  if d>0 and pp.c< p.c < x.c and p.c>p.o and x.c>x.o and x.c>p.h+need:return 1
  if d<0 and pp.c> p.c > x.c and p.c<p.o and x.c<x.o and x.c<p.l-need:return -1
 return 0

def run(symbol,b,c,I):
 bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;start=dt(b[0].dt);when=b[0].dt
 contract=100. if symbol=='XAU' else 1.;tp=3. if symbol=='XAU' else 300.
 for i in range(652,len(b)):
  z=b[i]
  if pos is None:
   if i<=cool:continue
   d=signal(symbol,i-1,b,c,I,bal,lot)
   if not d:continue
   pos=(d,z.o,lot,i);tr+=1
  d,en,L,ei=pos;mh=max(mh,i-ei+1)
  ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-ad*contract*L
  dd=max(dd,(peak-flt)/peak)
  if flt<=0:return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt,(dt(z.dt)-start).total_seconds()/86400)
  tar=en+d*tp;hit=z.h>=tar if d>0 else z.l<=tar
  if hit:
   bal+=tp*contract*L;peak=max(peak,bal);tps+=1;when=z.dt
   if L>=1.-1e-9:return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt,(dt(z.dt)-start).total_seconds()/86400)
   lot=round(L+.01,2);pos=None;cool=i+1
 return R(tps,False,False,bal,dd*100,tr,mh,lot,when,DAYS)

def score(rs):
 done=sum(r.done for r in rs); speed=-sum(r.days for r in rs if r.done); tps=sum(r.tps for r in rs); alive=sum(not r.bust for r in rs)
 return(done,speed,tps,alive,-sum(r.dd for r in rs),-sum(r.hold for r in rs))

def search(symbol,seed):
 bars=x3.load(x3.DATA['XAUUSD']['url']) if symbol=='XAU' else b8.load(); cs=list(configs(symbol)); ss=window_starts(bars,seed)
 wins=[make_window(bars,s) for s in ss]; caches=[prep(symbol,w) for w in wins]
 print(f'=== {symbol} V18 ADAPTIVE 60-DAY / 5-MIN COOLDOWN ===',flush=True);print('SEED',seed,'configs',len(cs),'range',bars[0].dt,'->',bars[-1].dt,flush=True)
 print('windows',[(bars[s].dt,w[-1].dt) for s,w in zip(ss,wins)],flush=True)
 stage=[]
 for n,c in enumerate(cs,1):
  rs=[run(symbol,w,c,I) for w,I in zip(wins[:STAGE1],caches[:STAGE1])];sc=score(rs);stage.append((sc,c,rs))
  if n%250==0 or n==len(cs):print(f'PROGRESS {symbol} stage1 {n}/{len(cs)} best={max(q[0][0] for q in stage)}/3',flush=True)
 surv=[q for q in stage if q[0][0]>=2]
 pool=sorted(surv if surv else stage,key=lambda q:q[0],reverse=True)[:TOP]
 print('POOL',len(pool),'stage1>=2',len(surv),flush=True);best=None
 for n,(sc,c,r3) in enumerate(pool,1):
  rs=r3+[run(symbol,w,c,I) for w,I in zip(wins[3:],caches[3:])];full=score(rs)
  if best is None or full>best[0]:best=(full,c,rs)
  if n%10==0 or full[0]>=6 or n==len(pool):print(f'PROGRESS {symbol} stage2 {n}/{len(pool)} pass60={full[0]}/10 sumTP={full[2]} alive={full[3]}/10',flush=True)
 sc,c,rs=best;print(f'{symbol}_V18_BEST seed={seed} {c} pass60={sc[0]}/10 sumTP={sc[2]} alive={sc[3]}/10',flush=True)
 for j,(s,r) in enumerate(zip(ss,rs),1):print(f'{symbol}{j:02d} start={bars[s].dt} TP={r.tps}/99 done60={r.done} bust={r.bust} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
 return 0

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);ap.add_argument('--seed',type=int);a=ap.parse_args();return search(a.symbol,seed_value(a.seed))
if __name__=='__main__':sys.exit(main())
