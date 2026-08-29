#!/usr/bin/env python3
"""V4 research refinement after V3: keep strict no-SL/no-cut rules, improve BTC entry quality.

User-locked execution model:
- independent $20 start per symbol
- 0.02 lot start, +0.01 only after TP, max 1.00
- one open position per symbol
- XAU TP distance 3.00 price; BTC TP distance 300.00 price
- no SL, no Smart Cut, no timeout/scratch close
- skip one complete M5 bar after TP
- bust if adverse mark-to-market equity <= 0

V4 adds BTC M5 + M15/H1 trend proxies and caches indicators for faster iterative search.
"""
from __future__ import annotations
import csv, io, urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product

START_EQUITY=20.0; START_LOT=.02; LOT_STEP=.01; MAX_LOT=1.0; TARGET_TPS=99; COOLDOWN_BARS=1
DATA={
 'XAUUSD':{'url':'https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Gold-Cash/XAUUSD/XAUUSD_M5.csv','tp':3.0,'contract':100.0},
 'BTCUSD':{'url':'https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Crypto/BTCUSD/BTCUSD_M5.csv','tp':300.0,'contract':1.0},
}

@dataclass
class Bar: ts:int; dt:str; o:float; h:float; l:float; c:float
@dataclass(frozen=True)
class Cfg:
 kind:str; fast:int; slow:int; lookback:int; rsi_lo:int; rsi_hi:int; body_atr:float; htf:int; direction:str
@dataclass
class Res:
 cfg:Cfg; tps:int; finished:bool; busted:bool; equity:float; maxdd:float; trades:int; maxhold:int; lot:float; when:str; worst_adverse:float


def parse_ts(x):
 if x.get('timestamp') not in (None,''):
  ts=int(float(x['timestamp'])); ts=ts//1000 if ts>10_000_000_000 else ts
  return ts,x.get('datetime') or datetime.fromtimestamp(ts,tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
 raw=(x.get('time') or x.get('datetime') or '').strip().replace('T',' ').replace('Z','')[:19]
 d=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
 return int(d.timestamp()),raw

def load(url):
 req=urllib.request.Request(url,headers={'User-Agent':'trading-api-v4-btc-refine'})
 with urllib.request.urlopen(req,timeout=120) as r:text=r.read().decode('utf-8-sig')
 out=[]
 for x in csv.DictReader(io.StringIO(text)):
  try:
   ts,dt=parse_ts(x); out.append(Bar(ts,dt,float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
  except Exception: pass
 out.sort(key=lambda z:z.ts)
 cutoff=out[-1].ts-int(timedelta(days=183).total_seconds()); out=[b for b in out if b.ts>=cutoff]
 if not out or out[-1].ts-out[0].ts<int(timedelta(days=170).total_seconds()):raise RuntimeError('insufficient six-month coverage')
 return out

def ema(v,n):
 a=2/(n+1); out=[v[0]]
 for x in v[1:]:out.append(a*x+(1-a)*out[-1])
 return out

def atr(b,n=14):
 tr=[]
 for i,x in enumerate(b):
  p=b[i-1].c if i else x.c; tr.append(max(x.h-x.l,abs(x.h-p),abs(x.l-p)))
 out=[]
 for i,x in enumerate(tr):
  if i==0:out.append(x)
  elif i<n:out.append(sum(tr[:i+1])/(i+1))
  else:out.append((out[-1]*(n-1)+x)/n)
 return out

def rsi(v,n=14):
 out=[50.]*len(v)
 if len(v)<=n:return out
 g=[max(v[i]-v[i-1],0) for i in range(1,len(v))]; l=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
 ag=sum(g[:n])/n; al=sum(l[:n])/n; out[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(v)):
  ag=(ag*(n-1)+g[i-1])/n; al=(al*(n-1)+l[i-1])/n; out[i]=100 if al==0 else 100-100/(1+ag/al)
 return out

def indicators(bars):
 c=[x.c for x in bars]; periods=[3,5,8,9,12,20,21,30,36,50,60,100,150,240,600]
 return {'ema':{p:ema(c,p) for p in periods},'atr':atr(bars),'rsi':rsi(c)}

def allowed(direction,d):return direction=='both' or (direction=='long' and d>0) or (direction=='short' and d<0)

def sig(i,b,cfg,ind):
 if i<max(620,cfg.lookback+2):return 0
 E=ind['ema']; rr=ind['rsi']; aa=ind['atr']; x=b[i]; p=b[i-1]
 local_up=E[cfg.fast][i]>E[cfg.slow][i] and E[cfg.fast][i]>E[cfg.fast][i-2]
 local_dn=E[cfg.fast][i]<E[cfg.slow][i] and E[cfg.fast][i]<E[cfg.fast][i-2]
 m15_up=E[60][i]>E[150][i] and E[60][i]>E[60][i-3]; m15_dn=E[60][i]<E[150][i] and E[60][i]<E[60][i-3]
 h1_up=E[240][i]>E[600][i] and E[240][i]>E[240][i-6]; h1_dn=E[240][i]<E[600][i] and E[240][i]<E[240][i-6]
 up=local_up and (m15_up if cfg.htf>=1 else True) and (h1_up if cfg.htf>=2 else True)
 dn=local_dn and (m15_dn if cfg.htf>=1 else True) and (h1_dn if cfg.htf>=2 else True)
 rlong=cfg.rsi_lo<=rr[i]<=cfg.rsi_hi; rshort=(100-cfg.rsi_hi)<=rr[i]<=(100-cfg.rsi_lo)
 body=x.c-x.o; strength=abs(body)/max(aa[i],1e-9)
 if cfg.kind=='trend':
  if up and body>0 and x.c>E[cfg.fast][i] and strength>=cfg.body_atr and rlong and allowed(cfg.direction,1):return 1
  if dn and body<0 and x.c<E[cfg.fast][i] and strength>=cfg.body_atr and rshort and allowed(cfg.direction,-1):return -1
 elif cfg.kind=='breakout':
  hi=max(z.h for z in b[i-cfg.lookback:i]); lo=min(z.l for z in b[i-cfg.lookback:i])
  if up and x.c>hi and rlong and allowed(cfg.direction,1):return 1
  if dn and x.c<lo and rshort and allowed(cfg.direction,-1):return -1
 elif cfg.kind=='pullback':
  if up and p.l<=E[cfg.fast][i-1] and x.c>p.h and rlong and allowed(cfg.direction,1):return 1
  if dn and p.h>=E[cfg.fast][i-1] and x.c<p.l and rshort and allowed(cfg.direction,-1):return -1
 elif cfg.kind=='rejection':
  rng=max(x.h-x.l,1e-9); lowwick=(min(x.o,x.c)-x.l)/rng; hiwick=(x.h-max(x.o,x.c))/rng
  if up and lowwick>=.35 and x.c>x.o and x.c>E[cfg.fast][i] and rlong and allowed(cfg.direction,1):return 1
  if dn and hiwick>=.35 and x.c<x.o and x.c<E[cfg.fast][i] and rshort and allowed(cfg.direction,-1):return -1
 return 0

def run(symbol,bars,cfg,ind):
 m=DATA[symbol]; tp=m['tp']; contract=m['contract']; balance=START_EQUITY; peak=balance; maxdd=worst=0.; tps=trades=maxhold=0; lot=START_LOT; pos=None; cooldown=-1; when=bars[0].dt
 for i in range(622,len(bars)):
  b=bars[i]
  if pos is None:
   if i<=cooldown:continue
   d=sig(i-1,bars,cfg,ind)
   if not d:continue
   pos=(d,b.o,lot,i); trades+=1
  d,entry,L,ei=pos; held=i-ei+1; maxhold=max(maxhold,held); target=entry+d*tp
  adverse=max(0.,entry-b.l) if d>0 else max(0.,b.h-entry); worst=max(worst,adverse)
  floating=balance-adverse*contract*L; maxdd=max(maxdd,(peak-floating)/peak if peak else 1.)
  if floating<=0:return Res(cfg,tps,False,True,0.,maxdd*100,trades,maxhold,L,b.dt,worst)
  hit=b.h>=target if d>0 else b.l<=target
  if hit:
   balance+=tp*contract*L; peak=max(peak,balance); tps+=1; when=b.dt
   if L>=MAX_LOT-1e-9:return Res(cfg,tps,True,False,balance,maxdd*100,trades,maxhold,L,b.dt,worst)
   lot=round(min(MAX_LOT,L+LOT_STEP)+1e-12,2); pos=None; cooldown=i+COOLDOWN_BARS
 return Res(cfg,tps,False,False,balance,maxdd*100,trades,maxhold,lot,when,worst)

def btc_cfgs():
 # strongest HTF-confirmed families first; broaden only if they fail
 for kind in ['breakout','pullback','rejection','trend']:
  for fast,slow in [(5,20),(8,21),(9,30),(12,36),(20,50)]:
   for lb in [5,8,12,20,30,48]:
    for band in [(50,68),(52,65),(48,70),(45,72)]:
     for body in ([0.,.15,.30,.50] if kind=='trend' else [0.]):
      for htf in [2,1]:
       for direction in ['both','long','short']:
        yield Cfg(kind,fast,slow,lb,band[0],band[1],body,htf,direction)
def rank(r):return (1 if r.finished else 0,r.tps,0 if r.busted else 1,-r.maxdd,-r.maxhold,r.equity)

def main():
 print('=== V4 BTC MTF REFINEMENT / NO SL / NO CUT ===')
 print('Rules unchanged: $20, 0.02->1.00 +0.01 only TP, XAU target 3 price, BTC target 300 price, one position, M5 cooldown.\n')
 # revalidate the XAU V3 winner exactly on current six-month data
 xb=load(DATA['XAUUSD']['url']); xi=indicators(xb); xcfg=Cfg('trend',20,100,3,48,70,0.,0,'both'); xr=run('XAUUSD',xb,xcfg,xi)
 print(f'[XAUUSD_REVALIDATE] {xb[0].dt} -> {xb[-1].dt} TP={xr.tps}/99 finish={xr.finished} bust={xr.busted} eq=${xr.equity:.2f} DD={xr.maxdd:.2f}% lot={xr.lot:.2f} completion={xr.when}')
 bb=load(DATA['BTCUSD']['url']); bi=indicators(bb); best=None; tested=0
 print(f'[BTCUSD] {bb[0].dt} -> {bb[-1].dt} bars={len(bb)}')
 for c in btc_cfgs():
  tested+=1; r=run('BTCUSD',bb,c,bi)
  if best is None or rank(r)>rank(best):best=r
  if r.finished:
   print(f'  COMPLETE_FOUND after {tested} configs: {r.cfg}')
   print(f'  TP={r.tps}/99 eq=${r.equity:.2f} DD={r.maxdd:.2f}% trades={r.trades} maxHoldBars={r.maxhold} worstAdversePrice={r.worst_adverse:.2f} completion={r.when}')
   return
 r=best
 print(f'  NO_COMPLETE_PATH after {tested} configs')
 print(f'  BEST={r.cfg}')
 print(f'  TP={r.tps}/99 finish={r.finished} bust={r.busted} eq=${r.equity:.2f} DD={r.maxdd:.2f}% trades={r.trades} maxHoldBars={r.maxhold} lastLot={r.lot:.2f} lastTime={r.when} worstAdversePrice={r.worst_adverse:.2f}')

if __name__=='__main__':main()
