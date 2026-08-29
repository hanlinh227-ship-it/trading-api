#!/usr/bin/env python3
"""V12 survival-budget refinement for XAU/BTC.
Locked trade rules unchanged: $20 start, 0.02->1.00 +0.01 only after TP,
XAU TP 3 price, BTC TP 300 price, no SL/cut/timeout, one position, 1 M5 cooldown.
Only PRE-ENTRY logic changes: multi-timeframe alignment, pullback/retest + confirmation,
ATR/equity survival budget and anti-chase filters. Ten frozen random starts are preserved.
"""
from __future__ import annotations
import argparse, random, sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8

SEED=20260829; STAGE1=3; TOP=48

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
 mode:str; fast:int; slow:int; lb:int; rlo:int; rhi:int; confirm:float; htf:int; atr_budget:float; chase:float; side:str
@dataclass
class R:
 tps:int;done:bool;bust:bool;eq:float;dd:float;trades:int;hold:int;lot:float;when:str

def cfgs(symbol):
 if symbol=='XAU':
  modes=['pullback','retest']; mas=[(5,20),(8,21),(12,36),(20,50)]; lbs=[5,8,12,20]
  rb=[(45,68),(48,70),(50,70)]; conf=[0,.08,.15,.25]; h=[1,2]; bud=[1.5,2.,2.5,3.,4.]; chase=[.5,.8,1.2]; sides=['both','long','short']
 else:
  modes=['breakout','retest']; mas=[(5,20),(8,21),(12,36),(20,50)]; lbs=[12,20,30,48]
  rb=[(46,68),(48,70),(50,70)]; conf=[.05,.10,.20,.30]; h=[1,2]; bud=[1.5,2.,2.5,3.,4.]; chase=[.8,1.2,1.6]; sides=['both','long','short']
 for z in product(modes,mas,lbs,rb,conf,h,bud,chase,sides):
  m,ma,lb,r,cf,ht,bu,ch,si=z;yield C(m,ma[0],ma[1],lb,r[0],r[1],cf,ht,bu,ch,si)

def prep(b):
 cl=[z.c for z in b]; ps=[5,8,12,20,21,36,50,60,150,240,600]
 return {'e':{p:x3.ema(cl,p) for p in ps},'a':x3.atr(b),'r':x3.rsi(cl),'roll':roll(b,[5,8,12,20,30,48])}

def sideok(s,d): return s=='both' or (s=='long' and d==1) or (s=='short' and d==-1)

def sig(i,b,c,I,symbol,balance,lot):
 if i<650:return 0
 E=I['e'];A=I['a'];RS=I['r'];x=b[i];p=b[i-1]
 # survival gate: estimated adverse ATR multiple must fit inside current equity budget
 contract=100. if symbol=='XAU' else 1.
 max_adverse=balance/(lot*contract)
 if A[i]*c.atr_budget >= max_adverse:return 0
 up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>E[c.fast][i-2] and E[c.slow][i]>=E[c.slow][i-3]
 dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<E[c.fast][i-2] and E[c.slow][i]<=E[c.slow][i-3]
 if c.htf>=1:
  up=up and E[60][i]>E[150][i] and E[60][i]>E[60][i-3]
  dn=dn and E[60][i]<E[150][i] and E[60][i]<E[60][i-3]
 if c.htf>=2:
  up=up and E[240][i]>E[600][i] and E[240][i]>E[240][i-6]
  dn=dn and E[240][i]<E[600][i] and E[240][i]<E[240][i-6]
 # anti-chase: entry signal bar may not be too far from fast EMA
 if abs(x.c-E[c.fast][i])>c.chase*A[i]: return 0
 hi,lo=I['roll'][c.lb]; need=c.confirm*A[i]
 rl=c.rlo<=RS[i]<=c.rhi; rs=(100-c.rhi)<=RS[i]<=(100-c.rlo)
 if c.mode=='pullback':
  if up and p.l<=E[c.fast][i-1] and x.c>p.h+need and x.c>x.o and rl and sideok(c.side,1):return 1
  if dn and p.h>=E[c.fast][i-1] and x.c<p.l-need and x.c<x.o and rs and sideok(c.side,-1):return -1
 elif c.mode=='retest':
  # previous bar touches prior range edge, current bar confirms back with trend
  if up and p.l<=hi[i-1] and p.c>=E[c.fast][i-1] and x.c>p.h+need and rl and sideok(c.side,1):return 1
  if dn and p.h>=lo[i-1] and p.c<=E[c.fast][i-1] and x.c<p.l-need and rs and sideok(c.side,-1):return -1
 else: # BTC breakout follow-through
  q=b[i-1]
  if up and q.c>hi[i-1] and x.c>=q.c+need and x.c>x.o and rl and sideok(c.side,1):return 1
  if dn and q.c<lo[i-1] and x.c<=q.c-need and x.c<x.o and rs and sideok(c.side,-1):return -1
 return 0

def run(b,c,I,symbol):
 tp=3. if symbol=='XAU' else 300.; contract=100. if symbol=='XAU' else 1.
 bal=20.;peak=20.;dd=0.;lot=.02;tps=tr=mh=0;pos=None;cool=-1;when=b[0].dt
 for i in range(652,len(b)):
  z=b[i]
  if pos is None:
   if i<=cool:continue
   d=sig(i-1,b,c,I,symbol,bal,lot)
   if not d:continue
   pos=(d,z.o,lot,i);tr+=1
  d,en,L,ei=pos;mh=max(mh,i-ei+1)
  ad=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-ad*contract*L;dd=max(dd,(peak-flt)/peak)
  if flt<=0:return R(tps,False,True,0.,dd*100,tr,mh,L,z.dt)
  tar=en+d*tp;hit=z.h>=tar if d>0 else z.l<=tar
  if hit:
   bal+=tp*contract*L;peak=max(peak,bal);tps+=1;when=z.dt
   if L>=1.-1e-9:return R(tps,True,False,bal,dd*100,tr,mh,L,z.dt)
   lot=round(L+.01,2);pos=None;cool=i+1
 return R(tps,False,False,bal,dd*100,tr,mh,lot,when)

def score(rs):return(sum(r.done for r in rs),sum(r.tps for r in rs),sum(not r.bust for r in rs),-sum(r.dd for r in rs),-sum(r.hold for r in rs))

def search(symbol):
 bars=x3.load(x3.DATA['XAUUSD']['url']) if symbol=='XAU' else b8.load();ss=starts(len(bars));wins=[bars[s:] for s in ss]
 print(f'=== {symbol} V12 SURVIVAL RANDOM10 ===',flush=True);print('range',bars[0].dt,'->',bars[-1].dt,'bars',len(bars),flush=True);print('starts',[bars[s].dt for s in ss],flush=True)
 caches=[prep(w) for w in wins];cs=list(cfgs(symbol));stage=[]
 for n,c in enumerate(cs,1):
  rs=[run(w,c,I,symbol) for w,I in zip(wins[:STAGE1],caches[:STAGE1])];sc=score(rs);stage.append((sc,c,rs))
  if n%500==0 or n==len(cs):print(f'PROGRESS stage1 {n}/{len(cs)} best={max(x[0][0] for x in stage)}/3',flush=True)
 survivors=[x for x in stage if x[0][0]==3];pool=survivors if survivors else sorted(stage,key=lambda x:x[0],reverse=True)[:TOP]
 print('SURVIVORS',len(survivors),'POOL',len(pool),flush=True);best=None
 for n,(sc,c,r3) in enumerate(pool,1):
  rs=r3+[run(w,c,I,symbol) for w,I in zip(wins[3:],caches[3:])];full=score(rs)
  if best is None or full>best[0]:best=(full,c,rs)
  if n%10==0 or full[0]==10 or n==len(pool):print(f'PROGRESS stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]}',flush=True)
  if full[0]==10:break
 sc,c,rs=best;print(f'{symbol}_BEST {c} pass={sc[0]}/10 sumTP={sc[1]} alive={sc[2]}/10',flush=True)
 for j,(s,r) in enumerate(zip(ss,rs),1):print(f'{symbol}{j:02d} start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}',flush=True)
 return 0

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--symbol',choices=['XAU','BTC'],required=True);a=ap.parse_args();sys.exit(search(a.symbol))
if __name__=='__main__':main()
