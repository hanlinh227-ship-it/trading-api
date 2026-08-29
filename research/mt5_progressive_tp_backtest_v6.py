#!/usr/bin/env python3
"""BTC V6: stateful breakout-retest / sweep-reclaim entries under strict no-SL progressive rules."""
from __future__ import annotations
import csv,io,urllib.request
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from itertools import product
URL='https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Crypto/BTCUSD/BTCUSD_M5.csv'
EQ0=20.; LOT0=.02; STEP=.01; MAXLOT=1.; TP=300.; TARGET=99
@dataclass
class B: ts:int; dt:str; o:float; h:float; l:float; c:float
@dataclass(frozen=True)
class C: mode:str; lb:int; fast:int; slow:int; atrmin:float; atrmax:float; retbuf:float; rlo:int; rhi:int; htf:int; side:str
@dataclass
class R: cfg:C; tps:int; done:bool; bust:bool; eq:float; dd:float; trades:int; hold:int; lot:float; when:str; adv:float

def load():
 req=urllib.request.Request(URL,headers={'User-Agent':'btc-v6-retest'})
 with urllib.request.urlopen(req,timeout=120) as r:text=r.read().decode('utf-8-sig')
 a=[]
 for x in csv.DictReader(io.StringIO(text)):
  try:
   raw=(x.get('time') or x.get('datetime')).strip().replace('T',' ').replace('Z','')[:19]
   d=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
   a.append(B(int(d.timestamp()),raw,float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
  except:pass
 a.sort(key=lambda z:z.ts); cut=a[-1].ts-int(timedelta(days=183).total_seconds()); return [x for x in a if x.ts>=cut]
def ema(v,n):
 k=2/(n+1); o=[v[0]]
 for x in v[1:]:o.append(k*x+(1-k)*o[-1])
 return o
def atr(b,n=14):
 t=[]
 for i,x in enumerate(b):
  p=b[i-1].c if i else x.c;t.append(max(x.h-x.l,abs(x.h-p),abs(x.l-p)))
 o=[]
 for i,x in enumerate(t):o.append(x if i==0 else (sum(t[:i+1])/(i+1) if i<n else (o[-1]*(n-1)+x)/n))
 return o
def rsi(v,n=14):
 o=[50.]*len(v);g=[max(v[i]-v[i-1],0) for i in range(1,len(v))];l=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
 if len(v)<=n:return o
 ag=sum(g[:n])/n;al=sum(l[:n])/n;o[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(v)):
  ag=(ag*(n-1)+g[i-1])/n;al=(al*(n-1)+l[i-1])/n;o[i]=100 if al==0 else 100-100/(1+ag/al)
 return o
def htf(b,sec):
 buckets=[];cur=None
 for x in b:
  k=x.ts//sec*sec
  if cur is None or cur[0]!=k:
   if cur:buckets.append(cur)
   cur=[k,x.c]
  else:cur[1]=x.c
 if cur:buckets.append(cur)
 cl=[x[1] for x in buckets];e20=ema(cl,20);e50=ema(cl,50);idx={x[0]:i for i,x in enumerate(buckets)};out=[]
 for x in b:
  j=idx[x.ts//sec*sec]-1
  if j<52:out.append(0)
  else:out.append(1 if e20[j]>e50[j] and e20[j]>e20[j-2] else (-1 if e20[j]<e50[j] and e20[j]<e20[j-2] else 0))
 return out
def prep(b):
 cl=[x.c for x in b];ps=[5,8,9,12,20,21,30,36,50]
 return {'e':{p:ema(cl,p) for p in ps},'a':atr(b),'r':rsi(cl),'m15':htf(b,900),'h1':htf(b,3600)}
def sideok(s,d):return s=='both' or s=='long' and d==1 or s=='short' and d==-1
def signal(i,b,c,I):
 if i<700:return 0
 E=I['e'];A=I['a'];RR=I['r'];x=b[i];p=b[i-1];q=b[i-2]
 if not c.atrmin<=A[i]<=c.atrmax:return 0
 up=E[c.fast][i]>E[c.slow][i] and E[c.fast][i]>E[c.fast][i-2];dn=E[c.fast][i]<E[c.slow][i] and E[c.fast][i]<E[c.fast][i-2]
 if c.htf>=1:up=up and I['m15'][i]==1;dn=dn and I['m15'][i]==-1
 if c.htf>=2:up=up and I['h1'][i]==1;dn=dn and I['h1'][i]==-1
 longr=c.rlo<=RR[i]<=c.rhi;shortr=100-c.rhi<=RR[i]<=100-c.rlo
 # Levels are based only on bars BEFORE the breakout candidate q.
 hi=max(z.h for z in b[i-2-c.lb:i-2]);lo=min(z.l for z in b[i-2-c.lb:i-2]);buf=c.retbuf*A[i]
 if c.mode=='retest':
  # q closes through level, p retests but holds, x confirms away from level.
  if up and q.c>hi and p.l<=hi+buf and p.c>=hi and x.c>p.h and longr and sideok(c.side,1):return 1
  if dn and q.c<lo and p.h>=lo-buf and p.c<=lo and x.c<p.l and shortr and sideok(c.side,-1):return -1
 if c.mode=='sweep':
  # q sweeps level but rejects back, p+x confirm reversal in HTF trend direction.
  if up and q.l<lo and q.c>lo and p.c>p.o and x.c>p.h and longr and sideok(c.side,1):return 1
  if dn and q.h>hi and q.c<hi and p.c<p.o and x.c<p.l and shortr and sideok(c.side,-1):return -1
 return 0
def run(b,c,I):
 bal=EQ0;peak=bal;dd=adv=0.;lot=LOT0;tps=tr=mh=0;pos=None;cool=-1;when=b[0].dt
 for i in range(702,len(b)):
  x=b[i]
  if pos is None:
   if i<=cool:continue
   d=signal(i-1,b,c,I)
   if not d:continue
   pos=(d,x.o,lot,i);tr+=1
  d,en,L,ei=pos;mh=max(mh,i-ei+1);tar=en+d*TP;ad=max(0.,en-x.l) if d>0 else max(0.,x.h-en);adv=max(adv,ad);flt=bal-ad*L;dd=max(dd,(peak-flt)/peak)
  if flt<=0:return R(c,tps,False,True,0.,dd*100,tr,mh,L,x.dt,adv)
  hit=x.h>=tar if d>0 else x.l<=tar
  if hit:
   bal+=TP*L;peak=max(peak,bal);tps+=1;when=x.dt
   if L>=MAXLOT-1e-9:return R(c,tps,True,False,bal,dd*100,tr,mh,L,x.dt,adv)
   lot=round(L+STEP,2);pos=None;cool=i+1
 return R(c,tps,False,False,bal,dd*100,tr,mh,lot,when,adv)
def cfgs():
 for z in product(['retest','sweep'],[5,8,12,20,30,48],[(5,20),(8,21),(9,30),(12,36),(20,50)],[(40,900),(60,700),(80,600),(100,500)],[.05,.15,.3],[(48,70),(50,68),(52,66)],[2,1],['both','long','short']):
  m,lb,ma,ab,rb,rr,h,s=z;yield C(m,lb,ma[0],ma[1],ab[0],ab[1],rb,rr[0],rr[1],h,s)
def rank(r):return (r.done,r.tps,not r.bust,-r.dd,-r.hold,r.eq)
def main():
 b=load();I=prep(b);print('=== BTC V6 BREAKOUT-RETEST / SWEEP-RECLAIM / NO SL ===');print(f'{b[0].dt}->{b[-1].dt} bars={len(b)}')
 best=None;n=0
 for c in cfgs():
  n+=1;r=run(b,c,I)
  if best is None or rank(r)>rank(best):best=r
  if r.done:
   print(f'COMPLETE_FOUND after {n}: {r.cfg}');print(f'TP=99/99 eq=${r.eq:.2f} DD={r.dd:.2f}% trades={r.trades} maxHold={r.hold} adv={r.adv:.2f} completion={r.when}');return
 r=best;print(f'NO_COMPLETE_PATH after {n}');print(f'BEST={r.cfg}');print(f'TP={r.tps}/99 bust={r.bust} eq=${r.eq:.2f} DD={r.dd:.2f}% trades={r.trades} maxHold={r.hold} lot={r.lot:.2f} when={r.when} adv={r.adv:.2f}')
if __name__=='__main__':main()
