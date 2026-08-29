#!/usr/bin/env python3
"""V5 BTC refinement: strict no-SL/no-cut progressive TP backtest using closed M15/H1 context.

Locked execution rules:
- $20 start equity
- one BTCUSD position at a time
- start 0.02 lot, +0.01 only after a true 300-price TP, cap 1.00
- no SL, no Smart Cut, no timeout/scratch/manual close
- after TP, one full M5 bar cooldown
- path busts if conservative adverse mark-to-market equity <= 0
- latest 183 days of full BTCUSD M5 history
"""
from __future__ import annotations
import csv, io, urllib.request, math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product

URL='https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Crypto/BTCUSD/BTCUSD_M5.csv'
START_EQUITY=20.0; START_LOT=.02; LOT_STEP=.01; MAX_LOT=1.0; TP=300.0; CONTRACT=1.0; TARGET_TPS=99

@dataclass
class Bar: ts:int; dt:str; o:float; h:float; l:float; c:float
@dataclass(frozen=True)
class Cfg:
 trigger:str; fast:int; slow:int; lb:int; rlo:int; rhi:int; min_atr:float; max_atr:float; max_body_atr:float; htf_mode:int; direction:str
@dataclass
class Res:
 cfg:Cfg; tps:int; finished:bool; busted:bool; equity:float; maxdd:float; trades:int; maxhold:int; lot:float; when:str; worst_adv:float

def parse_ts(x):
 raw=(x.get('time') or x.get('datetime') or '').strip().replace('T',' ').replace('Z','')[:19]
 if raw:
  d=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc); return int(d.timestamp()),raw
 ts=int(float(x['timestamp'])); ts=ts//1000 if ts>10_000_000_000 else ts
 return ts,datetime.fromtimestamp(ts,tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def load():
 req=urllib.request.Request(URL,headers={'User-Agent':'trading-api-v5-btc'})
 with urllib.request.urlopen(req,timeout=120) as r:text=r.read().decode('utf-8-sig')
 a=[]
 for x in csv.DictReader(io.StringIO(text)):
  try:
   ts,dt=parse_ts(x); a.append(Bar(ts,dt,float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
  except Exception: pass
 a.sort(key=lambda z:z.ts); cut=a[-1].ts-int(timedelta(days=183).total_seconds()); a=[b for b in a if b.ts>=cut]
 if not a or a[-1].ts-a[0].ts<int(timedelta(days=170).total_seconds()):raise RuntimeError('insufficient history')
 return a

def ema(v,n):
 if not v:return []
 k=2/(n+1); o=[v[0]]
 for x in v[1:]:o.append(k*x+(1-k)*o[-1])
 return o

def atr(b,n=14):
 t=[]
 for i,x in enumerate(b):
  p=b[i-1].c if i else x.c; t.append(max(x.h-x.l,abs(x.h-p),abs(x.l-p)))
 o=[]
 for i,x in enumerate(t):
  if i==0:o.append(x)
  elif i<n:o.append(sum(t[:i+1])/(i+1))
  else:o.append((o[-1]*(n-1)+x)/n)
 return o

def rsi(v,n=14):
 o=[50.]*len(v)
 if len(v)<=n:return o
 g=[max(v[i]-v[i-1],0) for i in range(1,len(v))]; l=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
 ag=sum(g[:n])/n; al=sum(l[:n])/n; o[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(v)):
  ag=(ag*(n-1)+g[i-1])/n; al=(al*(n-1)+l[i-1])/n; o[i]=100 if al==0 else 100-100/(1+ag/al)
 return o

def closed_htf_map(bars,seconds,fast=20,slow=50):
 # Build real OHLC buckets. For every M5 bar, expose indicators from the PREVIOUS completed HTF bucket only.
 buckets=[]; cur=None
 for b in bars:
  key=(b.ts//seconds)*seconds
  if cur is None or cur[0]!=key:
   if cur is not None:buckets.append(cur)
   cur=[key,b.o,b.h,b.l,b.c]
  else:
   cur[2]=max(cur[2],b.h); cur[3]=min(cur[3],b.l); cur[4]=b.c
 if cur is not None:buckets.append(cur)
 closes=[x[4] for x in buckets]; ef=ema(closes,fast); es=ema(closes,slow)
 idx_by_key={x[0]:i for i,x in enumerate(buckets)}; out=[]
 for b in bars:
  key=(b.ts//seconds)*seconds; j=idx_by_key.get(key,0)-1
  if j<max(slow,3):out.append((0,0.0))
  else:
   slope=ef[j]-ef[j-2]
   trend=1 if ef[j]>es[j] and slope>0 else (-1 if ef[j]<es[j] and slope<0 else 0)
   out.append((trend,abs(ef[j]-es[j])/max(abs(es[j]),1e-9)))
 return out

def prep(b):
 c=[x.c for x in b]
 periods=[5,8,9,12,20,21,30,36,50]
 return {'ema':{p:ema(c,p) for p in periods},'atr':atr(b),'rsi':rsi(c),'m15':closed_htf_map(b,900),'h1':closed_htf_map(b,3600)}

def side_ok(mode,d):return mode=='both' or (mode=='long' and d>0) or (mode=='short' and d<0)

def sig(i,b,cfg,I):
 if i<700:return 0
 E=I['ema']; A=I['atr']; R=I['rsi']; x=b[i]; p=b[i-1]
 if not (cfg.min_atr<=A[i]<=cfg.max_atr):return 0
 body=x.c-x.o; bodyatr=abs(body)/max(A[i],1e-9)
 if bodyatr>cfg.max_body_atr:return 0  # anti-chase/exhaustion
 up=E[cfg.fast][i]>E[cfg.slow][i] and E[cfg.fast][i]>E[cfg.fast][i-2]
 dn=E[cfg.fast][i]<E[cfg.slow][i] and E[cfg.fast][i]<E[cfg.fast][i-2]
 m15=I['m15'][i][0]; h1=I['h1'][i][0]
 if cfg.htf_mode==2:
  up=up and m15==1 and h1==1; dn=dn and m15==-1 and h1==-1
 elif cfg.htf_mode==1:
  up=up and m15==1; dn=dn and m15==-1
 rlong=cfg.rlo<=R[i]<=cfg.rhi; rshort=(100-cfg.rhi)<=R[i]<=(100-cfg.rlo)
 hi=max(z.h for z in b[i-cfg.lb:i]); lo=min(z.l for z in b[i-cfg.lb:i])
 if cfg.trigger=='breakout':
  if up and x.c>hi and body>0 and rlong and side_ok(cfg.direction,1):return 1
  if dn and x.c<lo and body<0 and rshort and side_ok(cfg.direction,-1):return -1
 if cfg.trigger=='pullback':
  if up and p.l<=E[cfg.fast][i-1] and x.c>p.h and body>0 and rlong and side_ok(cfg.direction,1):return 1
  if dn and p.h>=E[cfg.fast][i-1] and x.c<p.l and body<0 and rshort and side_ok(cfg.direction,-1):return -1
 if cfg.trigger=='rejection':
  rng=max(x.h-x.l,1e-9); lw=(min(x.o,x.c)-x.l)/rng; uw=(x.h-max(x.o,x.c))/rng
  if up and lw>=.4 and x.c>x.o and x.c>E[cfg.fast][i] and rlong and side_ok(cfg.direction,1):return 1
  if dn and uw>=.4 and x.c<x.o and x.c<E[cfg.fast][i] and rshort and side_ok(cfg.direction,-1):return -1
 return 0

def run(b,cfg,I):
 bal=START_EQUITY; peak=bal; maxdd=worst=0.; lot=START_LOT; tps=trades=maxhold=0; pos=None; cool=-1; when=b[0].dt
 for i in range(702,len(b)):
  x=b[i]
  if pos is None:
   if i<=cool:continue
   d=sig(i-1,b,cfg,I)
   if not d:continue
   pos=(d,x.o,lot,i); trades+=1
  d,entry,L,ei=pos; held=i-ei+1; maxhold=max(maxhold,held); target=entry+d*TP
  adv=max(0.,entry-x.l) if d>0 else max(0.,x.h-entry); worst=max(worst,adv)
  floating=bal-adv*CONTRACT*L; maxdd=max(maxdd,(peak-floating)/peak if peak else 1.)
  if floating<=0:return Res(cfg,tps,False,True,0.,maxdd*100,trades,maxhold,L,x.dt,worst)
  hit=x.h>=target if d>0 else x.l<=target
  if hit:
   bal+=TP*CONTRACT*L; peak=max(peak,bal); tps+=1; when=x.dt
   if L>=MAX_LOT-1e-9:return Res(cfg,tps,True,False,bal,maxdd*100,trades,maxhold,L,x.dt,worst)
   lot=round(min(MAX_LOT,L+LOT_STEP)+1e-12,2); pos=None; cool=i+1
 return Res(cfg,tps,False,False,bal,maxdd*100,trades,maxhold,lot,when,worst)

def configs():
 # Ordered from strict, low-chase conditions toward broader conditions.
 for trig,(f,s),lb,band,atrband,maxbody,htf,direction in product(
  ['breakout','pullback','rejection'],[(5,20),(8,21),(9,30),(12,36),(20,50)],[5,8,12,20,30,48],
  [(50,66),(50,70),(46,72)],[(40,900),(60,700),(80,600),(100,500)], [.8,1.2,1.8], [2,1], ['both','long','short']):
  yield Cfg(trig,f,s,lb,band[0],band[1],atrband[0],atrband[1],maxbody,htf,direction)
def rank(r):return (1 if r.finished else 0,r.tps,0 if r.busted else 1,-r.maxdd,-r.maxhold,r.equity)

def main():
 b=load(); I=prep(b); print('=== BTC V5 CLOSED M15/H1 + ATR / STRICT NO-SL ===')
 print(f'bars={len(b)} range={b[0].dt} -> {b[-1].dt} | $20 | TP=300 price | lot .02->1.00')
 best=None; tested=0
 for c in configs():
  tested+=1; r=run(b,c,I)
  if best is None or rank(r)>rank(best):best=r
  if r.finished:
   print(f'COMPLETE_FOUND after {tested} configs: {r.cfg}')
   print(f'TP={r.tps}/99 eq=${r.equity:.2f} DD={r.maxdd:.2f}% trades={r.trades} maxHoldBars={r.maxhold} worstAdverse={r.worst_adv:.2f} completion={r.when}')
   return
 r=best; print(f'NO_COMPLETE_PATH after {tested} configs'); print(f'BEST={r.cfg}')
 print(f'TP={r.tps}/99 bust={r.busted} eq=${r.equity:.2f} DD={r.maxdd:.2f}% trades={r.trades} maxHoldBars={r.maxhold} lastLot={r.lot:.2f} lastTime={r.when} worstAdverse={r.worst_adv:.2f}')
if __name__=='__main__':main()
