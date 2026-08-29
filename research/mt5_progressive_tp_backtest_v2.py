#!/usr/bin/env python3
"""Research-only V2: progressive TP backtest with adaptive Smart Cut.

Fixed rules:
- Initial equity $20
- Lot 0.02, +0.01 ONLY after true TP, max 1.00
- Finish only after the 1.00 lot trade itself reaches TP (99 TP stages)
- One position at a time per symbol
- Wait one complete M5 bar after TP/cut before a new entry
- XAUUSD TP = 3.00 price units; BTCUSDT TP = 300.00 price units

V2 improvement after V1 blew up:
- entry-bar TP is evaluated correctly (signal uses previous closed bar, entry at next open)
- no fixed-price SL is added
- adaptive equity Smart Cut can close a wrong trade before account ruin; a CUT never
  increments lot and the same lot level must still earn a true TP
- optimization is separated from an untouched chronological OOS segment
"""
from __future__ import annotations
import csv, io, urllib.request
from dataclasses import dataclass
from itertools import product

START_EQUITY=20.0
START_LOT=0.02
LOT_STEP=0.01
MAX_LOT=1.00
TARGET_TPS=99
COOLDOWN_BARS=1
MIN_EQUITY=0.01

DATA={
 "XAUUSD": {"url":"https://raw.githubusercontent.com/simom1/XAUUSD-history/main/TradingView_Deep_Datasets/OANDA_XAUUSD/OANDA_XAUUSD_5.csv","tp":3.0,"contract":100.0},
 "BTCUSDT":{"url":"https://raw.githubusercontent.com/simom1/XAUUSD-history/main/TradingView_Deep_Datasets/BINANCE_BTCUSDT/BINANCE_BTCUSDT_5.csv","tp":300.0,"contract":1.0},
}

@dataclass
class Bar:
 ts:int; dt:str; o:float; h:float; l:float; c:float

@dataclass(frozen=True)
class Cfg:
 kind:str; fast:int; slow:int; body_atr:float; cut_pct:float; timeout:int; flip_exit:bool

@dataclass
class Res:
 cfg:Cfg; tps:int; finished:bool; busted:bool; equity:float; maxdd:float; cuts:int; scratch:int; trades:int; maxhold:int; lot:float; when:str


def load(url):
 req=urllib.request.Request(url,headers={"User-Agent":"trading-api-research-v2"})
 with urllib.request.urlopen(req,timeout=60) as r: text=r.read().decode()
 out=[]
 for x in csv.DictReader(io.StringIO(text)):
  try: out.append(Bar(int(float(x['timestamp'])),x['datetime'],float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
  except Exception: pass
 out.sort(key=lambda z:z.ts); return out


def ema(v,n):
 a=2/(n+1); out=[v[0]]
 for x in v[1:]: out.append(a*x+(1-a)*out[-1])
 return out


def atr(b,n=14):
 tr=[]
 for i,x in enumerate(b):
  p=b[i-1].c if i else x.c
  tr.append(max(x.h-x.l,abs(x.h-p),abs(x.l-p)))
 out=[]
 for i,x in enumerate(tr):
  if i==0: out.append(x)
  elif i<n: out.append(sum(tr[:i+1])/(i+1))
  else: out.append((out[-1]*(n-1)+x)/n)
 return out


def rsi(v,n=14):
 out=[50.0]*len(v)
 if len(v)<=n:return out
 g=[max(v[i]-v[i-1],0) for i in range(1,len(v))]
 l=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
 ag=sum(g[:n])/n; al=sum(l[:n])/n
 out[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(v)):
  ag=(ag*(n-1)+g[i-1])/n; al=(al*(n-1)+l[i-1])/n
  out[i]=100 if al==0 else 100-100/(1+ag/al)
 return out


def prep(bars,cfg):
 c=[x.c for x in bars]
 return ema(c,cfg.fast),ema(c,cfg.slow),atr(bars),rsi(c)


def sig(i,b,cfg,ef,es,aa,rr):
 if i<max(cfg.slow,15):return 0
 x=b[i]; p=b[i-1]; body=x.c-x.o
 strength=abs(body)/max(aa[i],1e-9)
 if cfg.kind=='candle':
  if strength>=cfg.body_atr:
   if body>0 and x.c>ef[i] and rr[i]>=50:return 1
   if body<0 and x.c<ef[i] and rr[i]<=50:return -1
 if cfg.kind=='trend':
  if ef[i]>es[i] and x.c>ef[i] and body>0 and strength>=cfg.body_atr:return 1
  if ef[i]<es[i] and x.c<ef[i] and body<0 and strength>=cfg.body_atr:return -1
 if cfg.kind=='pullback':
  if ef[i]>es[i] and p.l<=ef[i-1] and x.c>p.h and rr[i]>=50:return 1
  if ef[i]<es[i] and p.h>=ef[i-1] and x.c<p.l and rr[i]<=50:return -1
 if cfg.kind=='microbreak':
  hi=max(z.h for z in b[i-3:i]); lo=min(z.l for z in b[i-3:i])
  if x.c>hi and ef[i]>=es[i]:return 1
  if x.c<lo and ef[i]<=es[i]:return -1
 return 0


def run(symbol,bars,cfg,start,end):
 m=DATA[symbol]; tp=m['tp']; contract=m['contract']; ef,es,aa,rr=prep(bars,cfg)
 equity=START_EQUITY; peak=equity; maxdd=0.; tps=cuts=scratch=trades=maxhold=0; lot=START_LOT
 pos=None; cooldown=-1; when=bars[start].dt
 begin=max(start,cfg.slow+2); end=min(end,len(bars))
 for i in range(begin,end):
  b=bars[i]
  if pos is None:
   if i<=cooldown:continue
   d=sig(i-1,bars,cfg,ef,es,aa,rr)
   if not d:continue
   pos=(d,b.o,lot,i); trades+=1
  # IMPORTANT: evaluate the entry bar too. Signal is prior closed bar, so no lookahead.
  d,entry,L,ei=pos; held=i-ei+1; maxhold=max(maxhold,held)
  target=entry+d*tp
  # Adaptive Smart Cut: percentage of CURRENT realized equity, converted to price distance.
  risk=max(equity*cfg.cut_pct,0.01)
  cutdist=risk/(contract*L)
  cutpx=entry-d*cutdist
  # Conservative intrabar ordering: if TP and CUT are both inside one OHLC bar, CUT wins.
  cut_hit=(b.l<=cutpx) if d>0 else (b.h>=cutpx)
  tp_hit=(b.h>=target) if d>0 else (b.l<=target)
  if cut_hit:
   equity-=risk; cuts+=1
   dd=(peak-equity)/peak if peak else 1.; maxdd=max(maxdd,dd)
   if equity<=MIN_EQUITY:
    return Res(cfg,tps,False,True,equity,maxdd*100,cuts,scratch,trades,maxhold,L,b.dt)
   pos=None; cooldown=i+COOLDOWN_BARS; continue
  if tp_hit:
   equity+=tp*contract*L; peak=max(peak,equity); tps+=1; when=b.dt
   if L>=MAX_LOT-1e-9:
    return Res(cfg,tps,True,False,equity,maxdd*100,cuts,scratch,trades,maxhold,L,b.dt)
   lot=round(min(MAX_LOT,L+LOT_STEP)+1e-12,2)
   pos=None; cooldown=i+COOLDOWN_BARS; continue
  # Thesis invalidation/timeout cut at bar close; same lot is retained.
  opposite=sig(i,bars,cfg,ef,es,aa,rr)==-d if cfg.flip_exit else False
  if held>=cfg.timeout or opposite:
   pnl=(b.c-entry)*d*contract*L
   equity+=pnl; scratch+=1
   if equity<=MIN_EQUITY:
    return Res(cfg,tps,False,True,equity,100.0,cuts,scratch,trades,maxhold,L,b.dt)
   peak=max(peak,equity); maxdd=max(maxdd,(peak-equity)/peak if peak else 1.)
   pos=None; cooldown=i+COOLDOWN_BARS
 return Res(cfg,tps,False,False,equity,maxdd*100,cuts,scratch,trades,maxhold,lot,when)


def cfgs():
 # Broad but bounded search. Cut is adaptive equity protection, not a fixed SL.
 for kind in ['candle','trend','pullback','microbreak']:
  for fast,slow in [(3,12),(5,20),(8,21),(9,30),(12,36),(20,50)]:
   for body in ([0.0,0.15,0.3,0.5,0.75] if kind in ('candle','trend') else [0.0]):
    for cut in [0.10,0.15,0.20,0.25,0.30,0.40,0.50]:
     for timeout in [3,6,12,24,48]:
      for flip in [False,True]:
       yield Cfg(kind,fast,slow,body,cut,timeout,flip)


def rank(r):
 return (1 if r.finished else 0,r.tps,0 if r.busted else 1,r.equity,-r.maxdd,-r.cuts)


def main():
 print('=== PROGRESSIVE TP V2 / ADAPTIVE SMART CUT ===')
 print('equity=$20 | lot=0.02..1.00 +0.01 ONLY ON TP | XAU TP=3.00 price | BTC TP=300.00 price | M5 cooldown=1 full bar')
 print('Smart Cut keeps same lot; CUT is never counted as TP. Same-bar ambiguity is conservative: CUT before TP.\n')
 for symbol in ['XAUUSD','BTCUSDT']:
  bars=load(DATA[symbol]['url']); n=len(bars); oos0=int(n*.85); train=bars[:oos0]
  print(f'[{symbol}] bars={n} {bars[0].dt} -> {bars[-1].dt} | optimize first 85%, untouched OOS last 15%')
  tested=[]
  for c in cfgs():
   r=run(symbol,bars,c,0,oos0); tested.append(r)
  tested.sort(key=rank,reverse=True)
  for k,r in enumerate(tested[:8],1):
   print(f'  OPT{k}: {r.cfg} | TP={r.tps}/99 finish={r.finished} bust={r.busted} eq=${r.equity:.2f} DD={r.maxdd:.1f}% cuts={r.cuts} scratch={r.scratch}')
  best=tested[0]
  oos=run(symbol,bars,best.cfg,oos0,n)
  full=run(symbol,bars,best.cfg,0,n)
  print(f'  SELECTED={best.cfg}')
  print(f'  OOS: TP={oos.tps}/99 finish={oos.finished} bust={oos.busted} eq=${oos.equity:.2f} DD={oos.maxdd:.1f}% cuts={oos.cuts} lot={oos.lot:.2f}')
  print(f'  FULL: TP={full.tps}/99 finish={full.finished} bust={full.busted} eq=${full.equity:.2f} DD={full.maxdd:.1f}% cuts={full.cuts} scratch={full.scratch} trades={full.trades} maxHold={full.maxhold} lastLot={full.lot:.2f} when={full.when}')
  # diagnostic best across full data: explicitly optimization-biased, not OOS proof
  diag=[]
  for c in cfgs():diag.append(run(symbol,bars,c,0,n))
  diag.sort(key=rank,reverse=True); d=diag[0]
  print(f'  BEST_FULL_DIAGNOSTIC_NOT_OOS: {d.cfg} | TP={d.tps}/99 finish={d.finished} bust={d.busted} eq=${d.equity:.2f} DD={d.maxdd:.1f}% cuts={d.cuts} lastLot={d.lot:.2f} when={d.when}\n')

if __name__=='__main__':main()
