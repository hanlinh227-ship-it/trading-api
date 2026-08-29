#!/usr/bin/env python3
"""Research-only V3 no-SL progressive TP optimizer for XAUUSD and BTCUSDT.

Fixed user rules:
- independent starting equity $20 per symbol
- one open position at a time per symbol
- start lot 0.02; +0.01 only after true TP; max lot 1.00
- finish only after the 1.00-lot trade reaches TP (99 TP stages)
- no SL, no Smart Cut, no timeout close, no manual/scratch close
- XAUUSD TP distance = 3.00 price units
- BTCUSDT TP distance = 300.00 price units
- after TP, skip one full M5 bar before another entry
- if mark-to-market equity reaches <= 0 from adverse movement, path is BUST
- optimize on the latest six months only; failed configs are discarded and next configs are tested

Important: this is an in-sample search requested by the user. Completion on this same six-month
window is NOT proof of future/live profitability. Signals use only closed bars; entry is next M5 open.
"""
from __future__ import annotations
import csv, io, urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product

START_EQUITY=20.0
START_LOT=0.02
LOT_STEP=0.01
MAX_LOT=1.00
TARGET_TPS=99
COOLDOWN_BARS=1

DATA={
 "XAUUSD":{"url":"https://raw.githubusercontent.com/simom1/XAUUSD-history/main/TradingView_Deep_Datasets/OANDA_XAUUSD/OANDA_XAUUSD_5.csv","tp":3.0,"contract":100.0},
 "BTCUSDT":{"url":"https://raw.githubusercontent.com/simom1/XAUUSD-history/main/TradingView_Deep_Datasets/BINANCE_BTCUSDT/BINANCE_BTCUSDT_5.csv","tp":300.0,"contract":1.0},
}

@dataclass
class Bar:
 ts:int; dt:str; o:float; h:float; l:float; c:float

@dataclass(frozen=True)
class Cfg:
 kind:str
 fast:int
 slow:int
 lookback:int
 rsi_lo:int
 rsi_hi:int
 body_atr:float
 slope_bars:int

@dataclass
class Res:
 cfg:Cfg; tps:int; finished:bool; busted:bool; equity:float; maxdd:float
 trades:int; maxhold:int; lot:float; when:str; worst_adverse:float


def load(url:str)->list[Bar]:
 req=urllib.request.Request(url,headers={"User-Agent":"trading-api-v3-no-sl-backtest"})
 with urllib.request.urlopen(req,timeout=90) as r: text=r.read().decode("utf-8")
 out=[]
 for x in csv.DictReader(io.StringIO(text)):
  try:
   ts=int(float(x['timestamp']))
   if ts>10_000_000_000: ts//=1000
   out.append(Bar(ts,x.get('datetime',''),float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
  except Exception: pass
 out.sort(key=lambda z:z.ts)
 if not out: raise RuntimeError('no bars loaded')
 # exact latest-six-month research window, approximated as 183 days from last bar
 cutoff=out[-1].ts-int(timedelta(days=183).total_seconds())
 return [b for b in out if b.ts>=cutoff]


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


def signal(i,b,cfg,ef,es,aa,rr):
 if i<max(cfg.slow,cfg.lookback,cfg.slope_bars,15):return 0
 x=b[i]; p=b[i-1]
 slope_fast=ef[i]-ef[i-cfg.slope_bars]
 slope_slow=es[i]-es[i-cfg.slope_bars]
 body=x.c-x.o; strength=abs(body)/max(aa[i],1e-9)
 trend_up=ef[i]>es[i] and slope_fast>0 and slope_slow>=0
 trend_dn=ef[i]<es[i] and slope_fast<0 and slope_slow<=0
 rlong=cfg.rsi_lo<=rr[i]<=cfg.rsi_hi
 rshort=(100-cfg.rsi_hi)<=rr[i]<=(100-cfg.rsi_lo)
 if cfg.kind=='trend':
  if trend_up and x.c>ef[i] and body>0 and strength>=cfg.body_atr and rlong:return 1
  if trend_dn and x.c<ef[i] and body<0 and strength>=cfg.body_atr and rshort:return -1
 elif cfg.kind=='breakout':
  hi=max(z.h for z in b[i-cfg.lookback:i]); lo=min(z.l for z in b[i-cfg.lookback:i])
  if trend_up and x.c>hi and rlong:return 1
  if trend_dn and x.c<lo and rshort:return -1
 elif cfg.kind=='pullback':
  if trend_up and p.l<=ef[i-1] and x.c>p.h and rlong:return 1
  if trend_dn and p.h>=ef[i-1] and x.c<p.l and rshort:return -1
 elif cfg.kind=='rejection':
  rng=max(x.h-x.l,1e-9); lower=(min(x.o,x.c)-x.l)/rng; upper=(x.h-max(x.o,x.c))/rng
  if trend_up and lower>=0.35 and x.c>x.o and x.c>ef[i] and rlong:return 1
  if trend_dn and upper>=0.35 and x.c<x.o and x.c<ef[i] and rshort:return -1
 return 0


def run(symbol,bars,cfg):
 m=DATA[symbol]; tp=m['tp']; contract=m['contract']; ef,es,aa,rr=prep(bars,cfg)
 balance=START_EQUITY; peak=balance; maxdd=0.; worst_adv=0.; tps=trades=maxhold=0; lot=START_LOT
 pos=None; cooldown=-1; when=bars[0].dt
 for i in range(max(cfg.slow,cfg.lookback,20)+2,len(bars)):
  b=bars[i]
  if pos is None:
   if i<=cooldown:continue
   d=signal(i-1,bars,cfg,ef,es,aa,rr)
   if not d:continue
   pos=(d,b.o,lot,i); trades+=1
  d,entry,L,ei=pos; held=i-ei+1; maxhold=max(maxhold,held)
  target=entry+d*tp
  adverse=max(0.,entry-b.l) if d>0 else max(0.,b.h-entry)
  worst_adv=max(worst_adv,adverse)
  floating=balance-adverse*contract*L
  if peak>0:maxdd=max(maxdd,(peak-floating)/peak)
  # conservative OHLC ordering: if same candle can both bust and TP, bust is counted first
  if floating<=0:
   return Res(cfg,tps,False,True,0.,maxdd*100,trades,maxhold,L,b.dt,worst_adv)
  hit=(b.h>=target) if d>0 else (b.l<=target)
  if hit:
   balance+=tp*contract*L; peak=max(peak,balance); tps+=1; when=b.dt
   if L>=MAX_LOT-1e-9:
    return Res(cfg,tps,True,False,balance,maxdd*100,trades,maxhold,L,b.dt,worst_adv)
   lot=round(min(MAX_LOT,L+LOT_STEP)+1e-12,2)
   pos=None; cooldown=i+COOLDOWN_BARS
 return Res(cfg,tps,False,False,balance,maxdd*100,trades,maxhold,lot,when,worst_adv)


def cfgs():
 # Search from stricter trend continuation toward broader setups.
 kinds=['trend','breakout','pullback','rejection']
 ma=[(3,12),(5,20),(8,21),(9,30),(12,36),(20,50),(20,100)]
 lookbacks=[3,5,8,12,20]
 rsi_bands=[(50,68),(52,65),(48,70),(45,72)]
 bodies=[0.0,0.15,0.30,0.50]
 slopes=[1,2,3,5]
 for kind,(f,s),lb,(rl,rh),body,sl in product(kinds,ma,lookbacks,rsi_bands,bodies,slopes):
  if kind not in ('trend',) and body!=0.0: continue
  yield Cfg(kind,f,s,lb,rl,rh,body,sl)


def rank(r):
 return (1 if r.finished else 0,r.tps,0 if r.busted else 1,-r.maxdd,-r.maxhold,r.equity)


def main():
 print('=== MT5 PROGRESSIVE TP V3 / STRICT NO-SL NO-CUT ===')
 print('Independent equity=$20 each | lot 0.02 -> 1.00, +0.01 ONLY after TP | one position/symbol')
 print('XAU TP=+/-3.00 PRICE | BTC TP=+/-300.00 PRICE | no SL | no Smart Cut | no timeout close')
 print('After TP: one full M5 bar cooldown. BUST if adverse mark-to-market equity <= 0.\n')
 for symbol in ('XAUUSD','BTCUSDT'):
  bars=load(DATA[symbol]['url'])
  print(f'[{symbol}] six_month_bars={len(bars)} range={bars[0].dt} -> {bars[-1].dt}')
  best=None; tested=0; first_finish=None
  for c in cfgs():
   tested+=1; r=run(symbol,bars,c)
   if best is None or rank(r)>rank(best): best=r
   if r.finished:
    first_finish=r
    print(f'  COMPLETE_FOUND after {tested} configs: {r.cfg}')
    print(f'  TP={r.tps}/99 equity=${r.equity:.2f} maxDD={r.maxdd:.2f}% trades={r.trades} maxHoldBars={r.maxhold} worstAdversePrice={r.worst_adverse:.2f} completion={r.when}')
    break
  if first_finish is None:
   r=best
   print(f'  NO_COMPLETE_PATH after {tested} configs')
   print(f'  BEST={r.cfg}')
   print(f'  TP={r.tps}/99 finished={r.finished} bust={r.busted} equity=${r.equity:.2f} maxDD={r.maxdd:.2f}% trades={r.trades} maxHoldBars={r.maxhold} lastLot={r.lot:.2f} lastTime={r.when} worstAdversePrice={r.worst_adverse:.2f}')
  print()

if __name__=='__main__': main()
