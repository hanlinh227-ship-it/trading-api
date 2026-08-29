#!/usr/bin/env python3
"""BTC V9: freeze V8 best core; add only pre-entry high-lot regime protection. No SL/cut/timeout."""
from mt5_progressive_tp_backtest_v8 import load,prep,C,EQ0,LOT0,STEP,MAXLOT,TP
from itertools import product
BASE=C(5,20,12,46,70,0.10,68,1,'short')

def base_sig(i,b,I,lot,gate,atrmax,sepmin,slopebars):
 if i<650:return 0
 E=I['e'];A=I['a'];R=I['r'];q=b[i-1];x=b[i]
 dn=E[5][i]<E[20][i] and E[5][i]<E[5][i-2] and E[60][i]<E[150][i] and E[60][i]<E[60][i-3]
 hi=max(z.h for z in b[i-13:i-1]);lo=min(z.l for z in b[i-13:i-1]);need=.10*A[i]
 ok=dn and q.c<lo and x.c<=q.c-need and x.c<x.o and 32<=R[i]<=54
 if not ok:return 0
 if lot>=gate:
  # High-lot entries must also agree with the slower regime and avoid volatility spikes.
  if not (E[240][i]<E[600][i] and E[240][i]<E[240][i-slopebars]):return 0
  if A[i]>atrmax:return 0
  if (E[600][i]-E[240][i]) < sepmin*A[i]:return 0
 return -1

def run(b,I,gate,atrmax,sepmin,slopebars):
 bal=EQ0;peak=bal;dd=0.;lot=LOT0;tps=tr=0;pos=None;cool=-1;when=b[0].dt;maxhold=0
 for i in range(652,len(b)):
  x=b[i]
  if pos is None:
   if i<=cool:continue
   d=base_sig(i-1,b,I,lot,gate,atrmax,sepmin,slopebars)
   if not d:continue
   pos=(d,x.o,lot,i);tr+=1
  d,en,L,ei=pos;maxhold=max(maxhold,i-ei+1);ad=max(0.,x.h-en);flt=bal-ad*L;dd=max(dd,(peak-flt)/peak)
  if flt<=0:return (False,tps,True,0.,dd*100,tr,L,x.dt,maxhold)
  if x.l<=en-TP:
   bal+=TP*L;peak=max(peak,bal);tps+=1;when=x.dt
   if L>=MAXLOT-1e-9:return (True,tps,False,bal,dd*100,tr,L,x.dt,maxhold)
   lot=round(L+STEP,2);pos=None;cool=i+1
 return (False,tps,False,bal,dd*100,tr,lot,when,maxhold)

def main():
 b=load();I=prep(b);best=None;bestp=None;n=0
 print('=== BTC V9 HIGH-LOT REGIME PROTECTION / STRICT NO SL ===')
 for p in product([.35,.45,.55,.65,.75,.85],[180,220,260,320,400,500],[0,.25,.5,1.0],[3,6,12,24]):
  n+=1;r=run(b,I,*p);key=(r[0],r[1],not r[2],-r[4],-r[8],r[3])
  if best is None or key>best:best=key;bestp=(p,r)
  if r[0]:print('COMPLETE_FOUND',p,r);return
 print('NO_COMPLETE_PATH',n,'BEST',bestp)
if __name__=='__main__':main()
