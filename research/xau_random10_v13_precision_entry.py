#!/usr/bin/env python3
"""XAU V13 precision-entry refinement.
Locked: $20 start, 0.02->1.00 +0.01 only after TP, TP=3.00 price,
no SL/cut/timeout, one position. New rule: after TP, skip TWO full M5 bars
(conservative >=10-minute cooldown before another order).
Entry families target low-MAE starts: pullback-reclaim, rejection, compression-break-retest.
Ten frozen random starts from the same 6-month XAU dataset are preserved.
"""
from __future__ import annotations
import random,sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3

SEED=20260829; STAGE1=3; TOP=80

def starts(n):
 r=random.Random(SEED); return sorted(r.sample(range(0,max(1,int(n*.78))),10))

def roll(b,lbs):
 out={}
 for lb in lbs:
  hi=[None]*len(b);lo=[None]*len(b)
  for i in range(lb,len(b)):
   w=b[i-lb:i];hi[i]=max(z.h for z in w);lo[i]=min(z.l for z in w)
  out[lb]=(hi,lo)
 return out

@dataclass(frozen=True)
class C:
 mode:str;fast:int;slow:int;lb:int;rlo:int;rhi:int;confirm:float;htf:int
 budget:float;chase:float;wick:float;pull:float;sep:float;side:str
@dataclass
class R:
 tps:int;done:bool;bust:bool;eq:float;dd:float;trades:int;hold:int;lot:float;when:str

def cfgs():
 modes=['reclaim','reject','compress_retest']
 mas=[(5,20),(8,21),(12,36),(20,50)]
 lbs=[5,8,12,20]
 rb=[(45,68),(48,70),(50,72)]
 conf=[0.0,.08,.15]
 htf=[1,2]
 budget=[1.0,1.5,2.0,2.5]
 chase=[.5,.8,1.1]
 wick=[.25,.40]
 pull=[.15,.35,.60]
 sep=[0.0,.15,.30]
 sides=['both','long','short']
 # Keep grid tractable while covering all families: deterministic thinning of full Cartesian grid.
 for n,z in enumerate(product(modes,mas,lbs,rb,conf,htf,budget,chase,wick,pull,sep,sides)):
  if n%9: continue
  m,ma,lb,r,cf,ht,bu,ch,wi,pu,se,si=z
  yield C(m,ma[0],ma[1],lb,r[0],r[1],cf,ht,bu,ch,wi,pu,se,si)

def prep(b):
 cl=[z.c for z in b];ps=[5,8,12,20,21,36,50,60,150,240,600]
 return {'e':{p:x3.ema(cl,p) for p in ps},'a':x3.atr(b),'r':x3.rsi(cl),'roll':roll(b,[5,8,12,20])}

def sideok(s,d):return s=='both' or s=='long' and d==1 or s=='short' and d==-1

def sig(i,b,c,I,bal,lot):
 if i<650:return 0
 E=I['e'];A=I['a'];RS=I['r'];x=b[i];p=b[i-1];pp=b[i-2];atr=max(A[i],1e-9)
 # Survival budget: estimated adverse excursion must fit current balance.
 maxadv=bal/(lot*100.)
 if atr*c.budget>=maxadv:return 0
 # M5 trend + M15 proxy, optional H1 proxy.
 up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>E[c.fast][i-2] and E[c.slow][i]>=E[c.slow][i-3]
 dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<E[c.fast][i-2] and E[c.slow][i]<=E[c.slow][i-3]
 up=up and E[60][i]>E[150][i] and E[60][i]>=E[60][i-3]
 dn=dn and E[60][i]<E[150][i] and E[60][i]<=E[60][i-3]
 if c.htf==2:
  up=up and E[240][i]>E[600][i] and E[240][i]>=E[240][i-6]
  dn=dn and E[240][i]<E[600][i] and E[240][i]<=E[240][i-6]
 # Require trend separation but never chase an extended candle.
 if abs(E[c.fast][i]-E[c.slow][i])<c.sep*atr:return 0
 if abs(x.c-E[c.fast][i])>c.chase*atr:return 0
 rl=c.rlo<=RS[i]<=c.rhi;rs=(100-c.rhi)<=RS[i]<=(100-c.rlo)
 need=c.confirm*atr;hi,lo=I['roll'][c.lb]
 rg=max(p.h-p.l,1e-9);lower=(min(p.o,p.c)-p.l)/rg;upper=(p.h-max(p.o,p.c))/rg
 # pullback depth measured from fast EMA, bounded to avoid catching deep reversals.
 pd_long=(E[c.fast][i-1]-p.l)/atr;pd_short=(p.h-E[c.fast][i-1])/atr
 if c.mode=='reclaim':
  if up and 0<=pd_long<=c.pull and p.l<=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o and rl and sideok(c.side,1):return 1
  if dn and 0<=pd_short<=c.pull and p.h>=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o and rs and sideok(c.side,-1):return -1
 elif c.mode=='reject':
  if up and lower>=c.wick and p.c>=E[c.fast][i-1] and x.c>p.h+need and rl and sideok(c.side,1):return 1
  if dn and upper>=c.wick and p.c<=E[c.fast][i-1] and x.c<p.l-need and rs and sideok(c.side,-1):return -1
 else:
  # small two-bar compression near fast EMA, then break in trend direction.
  comp=(p.h-p.l)<=.9*atr and (pp.h-pp.l)<=1.1*max(A[i-2],1e-9)
  if up and comp and p.l<=hi[i-1] and x.c>p.h+need and rl and sideok(c.side,1):return 1
  if dn and comp and p.h>=lo[i-1] and x.c<p.l-need and rs and sideok(c.side,-1):return -1
 return 0

def run(b,c,I):
 bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;when=b[0].dt
 for i in range(652,len(b)):
  z=b[i]
  if pos is None:
   if i<=cool:continue
   d=sig(i-1,b,c,I,bal,lot)
   if not d:continue
   pos=(d,z.o,lot,i);tr+=1
  d,en,L,ei=pos;mh=max(mh,i-ei+1)
  ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-ad*100.*L;dd=max(dd,(peak-flt)/peak)
  if flt<=0:return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
  tar=en+d*3.;hit=z.h>=tar if d>0 else z.l<=tar
  if hit:
   bal+=3.*100.*L;peak=max(peak,bal);tps+=1;when=z.dt
   if L>=1.-1e-9:return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
   lot=round(L+.01,2);pos=None;cool=i+2  # skip two complete M5 bars => conservative >=10 min
 return R(tps,False,False,bal,dd*100,tr,mh,lot,when)

def score(rs):return(sum(r.done for r in rs),sum(r.tps for r in rs),sum(not r.bust for r in rs),-sum(r.dd for r in rs),-sum(r.hold for r in rs))

def main():
 bars=x3.load(x3.DATA['XAUUSD']['url']);ss=starts(len(bars));wins=[bars[s:] for s in ss];I=[prep(w) for w in wins];cs=list(cfgs())
 print('=== XAU V13 PRECISION ENTRY RANDOM10 / 10-MIN COOLDOWN ===',flush=True)
 print('range',bars[0].dt,'->',bars[-1].dt,'bars',len(bars),'configs',len(cs),flush=True);print('starts',[bars[s].dt for s in ss],flush=True)
 stage=[]
 for n,c in enumerate(cs,1):
  rs=[run(w,c,j) for w,j in zip(wins[:STAGE1],I[:STAGE1])];sc=score(rs);stage.append((sc,c,rs))
  if n%1000==0 or n==len(cs):print(f'PROGRESS stage1 {n}/{len(cs)} best={max(q[0][0] for q in stage)}/3',flush=True)
 surv=[q for q in stage if q[0][0]==3];pool=surv if surv else sorted(stage,key=lambda q:q[0],reverse=True)[:TOP]
 print('SURVIVORS',len(surv),'POOL',len(pool),flush=True);best=None
 for n,(sc,c,r3) in enumerate(pool,1):
  rs=r3+[run(w,c,j) for w,j in zip(wins[3:],I[3:])];full=score(rs)
  if best is None or full>best[0]:best=(full,c,rs)
  if n%10==0 or full[0]==10 or n==len(pool):print(f'PROGRESS stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]} alive={full[2]}/10',flush=True)
  if full[0]==10:break
 sc,c,rs=best;print(f'XAU_V13_BEST {c} pass={sc[0]}/10 sumTP={sc[1]} alive={sc[2]}/10',flush=True)
 for j,(s,r) in enumerate(zip(ss,rs),1):print(f'XAU{j:02d} start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
 return 0
if __name__=='__main__':sys.exit(main())
