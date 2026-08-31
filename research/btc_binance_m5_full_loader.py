#!/usr/bin/env python3
from __future__ import annotations
import json,time,urllib.parse,urllib.request
from dataclasses import dataclass
from datetime import datetime,timezone

BASE='https://data-api.binance.vision/api/v3/klines'
INTERVAL_MS=300_000

@dataclass
class B:
    ts:int; dt:str; o:float; h:float; l:float; c:float; v:float

def _get(params,retries=6):
    url=BASE+'?'+urllib.parse.urlencode(params)
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'btc-research-complete-m5/1.0'})
            with urllib.request.urlopen(req,timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last=e;time.sleep(min(2.0,0.25*(2**n)))
    raise RuntimeError(f'Binance fetch failed after retries: {last}')

def load(start='2023-01-01 00:00:00', end=None):
    st=int(datetime.strptime(start,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()*1000)
    if end is None:
        now=int(time.time()*1000)
        en=(now//INTERVAL_MS)*INTERVAL_MS-1
    else:
        en=int(datetime.strptime(end,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()*1000)
    rows=[];cur=st
    while cur<=en:
        batch=_get({'symbol':'BTCUSDT','interval':'5m','startTime':cur,'endTime':en,'limit':1000})
        if not batch:break
        rows.extend(batch)
        nxt=int(batch[-1][0])+INTERVAL_MS
        if nxt<=cur:raise RuntimeError('pagination stalled')
        cur=nxt
        time.sleep(0.015)
    uniq={int(x[0]):x for x in rows if st<=int(x[0])<=en}
    xs=[uniq[k] for k in sorted(uniq)]
    bars=[B(int(x[0])//1000,datetime.fromtimestamp(int(x[0])/1000,tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])) for x in xs]
    audit(bars,hard=True)
    return bars

def audit(bars,hard=True):
    if not bars:raise RuntimeError('empty BTCUSDT M5 dataset')
    bad=[]
    for a,b in zip(bars,bars[1:]):
        d=b.ts-a.ts
        if d!=300:bad.append((a.dt,b.dt,d))
    expected=(bars[-1].ts-bars[0].ts)//300+1
    coverage=100*len(bars)/expected
    print(f'DATA_AUDIT source=BinanceSpot BTCUSDT M5 range={bars[0].dt}->{bars[-1].dt} bars={len(bars)} expected={expected} coverage={coverage:.6f}% gaps={len(bad)}',flush=True)
    if bad:
        for g in bad[:20]:print('DATA_GAP',g,flush=True)
        if hard:raise RuntimeError(f'incomplete Binance M5 history: gaps={len(bad)} coverage={coverage:.6f}%')
    return {'bars':len(bars),'expected':expected,'coverage':coverage,'gaps':len(bad)}

if __name__=='__main__':
    b=load();print('DATA_OK',len(b),b[0].dt,b[-1].dt)
