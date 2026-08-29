#!/usr/bin/env python3
"""BTC V7: extreme micro-mean-reversion entries, strict no-SL progressive TP rules."""
from __future__ import annotations
import csv,io,urllib.request
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from itertools import product
URL='https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Crypto/BTCUSD/BTCUSD_M5.csv'
EQ0=20.;LOT0=.02;STEP=.01;MAXLOT=1.;TP=300.
@dataclass
class B: ts:int;dt:str;o:float;h:float;l:float;c:float
@dataclass(frozen=True)
class C: ema_n:int;rsi_n:int;rsi_ext:int;dev_atr:float;wick:float;atrmin:float;atrmax:float;confirm:int;side:str
@dataclass
class R: cfg:C;tps:int;done:bool;bust:bool;eq:float;dd:float;trades:int;hold:int;lot:float;when:str;adv:float

def load():
 req=urllib.request.Request(URL,headers={'User-Agent':'btc-v7-reversion'})
 with urllib.request.urlopen(req,timeout=120) as r:text=r.read().decode('utf-8-sig')
 a=[]
 for x in csv.DictReader(io.StringIO(text)):
  try:
   raw=(x.get('time') or x.get('datetime')).strip().replace('T',' ').replace('Z','')[:19];d=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
   a.append(B(int(d.timestamp()),raw,float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
  except:pass
 a.sort(key=lambda z:z.ts);cut=a[-1].ts-int(timedelta(days=183).total_seconds());return [x for x in a if x.ts>=cut]
def ema(v,n):
 k=2/(n+1);o=[v[0]]
 for x in v[1:]:o.append(k*x+(1-k)*o[-1])
 return o
def atr(b,n=14):
 t=[]
 for i,x in enumerate(b):
  p=b[i-1].c if i else x.c;t.append(max(x.h-x.l,abs(x.h-p),abs(x.l-p)))
 o=[]
 for i,x in enumerate(t):o.append(x if i==0 else (sum(t[:i+1])/(i+1) if i<n else (o[-1]*(n-1)+x)/n))
 return o
def rsi(v,n):
 o=[50.]*len(v);g=[max(v[i]-v[i-1],0) for i in range(1,len(v))];l=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
 if len(v)<=n:return o
 ag=sum(g[:n])/n;al=sum(l[:n])/n;o[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(v)):
  ag=(ag*(n-1)+g[i-1])/n;al=(al*(n-1)+l[i-1])/n;o[i]=100 if al==0 else 100-100/(1+ag/al)
 return o
def prep(b):
 cl=[x.c for x in b];return {'e':{n:ema(cl,n) for n in [12,20,30,50,100]},'r':{n:rsi(cl,n) for n in [5,7,9,14]},'a':atr(b)}
def sideok(s,d):return s=='both' or s=='long' and d==1 or s=='short' and d==-1
def sig(i,b,c,I):
 if i<120:return 0
 x=b[i];p=b[i-1];A=I['a'][i];E=I['e'][c.ema_n][i];R=I['r'][c.rsi_n][i]
 if not c.atrmin<=A<=c.atrmax:return 0
 dev=(x.c-E)/max(A,1e-9);rng=max(x.h-x.l,1e-9);lw=(min(x.o,x.c)-x.l)/rng;uw=(x.h-max(x.o,x.c))/rng
 longext=R<=c.rsi_ext and dev<=-c.dev_atr and lw>=c.wick
 shortext=R>=100-c.rsi_ext and dev>=c.dev_atr and uw>=c.wick
 if c.confirm==1:
  longext=longext and x.c>x.o
  shortext=shortext and x.c<x.o
 elif c.confirm==2:
  longext=longext and x.c>x.o and x.c>p.c
  shortext=shortext and x.c<x.o and x.c<p.c
 if longext and sideok(c.side,1):return 1
 if shortext and sideok(c.side,-1):return -1
 return 0
def run(b,c,I):
 bal=EQ0;peak=bal;dd=adv=0.;lot=LOT0;tps=tr=mh=0;pos=None;cool=-1;when=b[0].dt
 for i in range(122,len(b)):
  x=b[i]
  if pos is None:
   if i<=cool:continue
   d=sig(i-1,b,c,I)
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
 for z in product([12,20,30,50,100],[5,7,9,14],[20,25,30,35],[.5,.8,1.1,1.5,2.0],[.2,.35,.5],[(30,900),(50,700),(70,600)],[1,2],['both','long','short']):
  en,rn,re,dev,w,ab,cf,s=z;yield C(en,rn,re,dev,w,ab[0],ab[1],cf,s)
def rank(r):return (r.done,r.tps,not r.bust,-r.dd,-r.hold,r.eq)
def main():
 b=load();I=prep(b);print('=== BTC V7 EXTREME MICRO-REVERSION / NO SL ===');print(f'{b[0].dt}->{b[-1].dt} bars={len(b)}')
 best=None;n=0
 for c in cfgs():
  n+=1;r=run(b,c,I)
  if best is None or rank(r)>rank(best):best=r
  if r.done:
   print(f'COMPLETE_FOUND after {n}: {r.cfg}');print(f'TP=99/99 eq=${r.eq:.2f} DD={r.dd:.2f}% trades={r.trades} maxHold={r.hold} adv={r.adv:.2f} completion={r.when}');return
 r=best;print(f'NO_COMPLETE_PATH after {n}');print(f'BEST={r.cfg}');print(f'TP={r.tps}/99 bust={r.bust} eq=${r.eq:.2f} DD={r.dd:.2f}% trades={r.trades} maxHold={r.hold} lot={r.lot:.2f} when={r.when} adv={r.adv:.2f}')
if __name__=='__main__':main()
