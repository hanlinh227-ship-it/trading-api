#!/usr/bin/env python3
"""CI adapter for V4.
Uses Binance Spot 5m OHLCV only when GitHub-hosted runners cannot reach Bybit V5.
The strategy, fixed RR gates, DEV/SHADOW/FINAL split and execution rules remain
those of bybit_multicoin_scalp_rr_v4.py. This is a research proxy only.
"""
from __future__ import annotations
import json,time,urllib.parse,urllib.request
import bybit_multicoin_scalp_rr_v4 as c

# Hard scalp-density gates requested for this research batch.
c.MIN_FINAL_TRADES=300
c.MIN_FINAL_WINDOW_TRADES=80
c.WORST_FINAL_WR=0.75

BASE_BINANCE='https://data-api.binance.vision/api/v3/klines'

def getj(url,retries=7):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'multicoin-scalp-v4-ci/1.0'})
            with urllib.request.urlopen(req,timeout=40) as r:return json.loads(r.read().decode())
        except Exception as e:
            last=e;time.sleep(min(5.0,0.35*(2**n)))
    raise RuntimeError(last)

def load_binance(sym):
    now=int(time.time()*1000)
    last_closed=(now//c.INTERVAL_MS)*c.INTERVAL_MS-c.INTERVAL_MS
    start=last_closed-c.HISTORY_DAYS*c.DAY_MS
    rows={};cur=start;calls=0
    while cur<=last_closed:
        q=urllib.parse.urlencode({'symbol':sym,'interval':'5m','startTime':cur,'endTime':last_closed+c.INTERVAL_MS-1,'limit':1000})
        batch=getj(BASE_BINANCE+'?'+q);calls+=1
        if not batch:break
        for z in batch:
            ts=int(z[0])
            if start<=ts<=last_closed:rows[ts]=z
        nxt=int(batch[-1][0])+c.INTERVAL_MS
        if nxt<=cur:raise RuntimeError('pagination stalled')
        cur=nxt;time.sleep(.01)
    xs=[rows[k] for k in sorted(rows)]
    b=[c.Bar(int(x[0]),float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])) for x in xs]
    if len(b)<100_000:raise RuntimeError(f'insufficient Binance 5m history bars={len(b)}')
    gaps=[(a.ts,z.ts) for a,z in zip(b,b[1:]) if z.ts-a.ts!=c.INTERVAL_MS]
    expected=(b[-1].ts-b[0].ts)//c.INTERVAL_MS+1
    return b,{'source':'BinanceSpotDataAPI','research_proxy_for':'BybitV5Linear','symbol':sym,'interval':'5m','first':c.iso(b[0].ts),'last':c.iso(b[-1].ts),'bars':len(b),'expected':expected,'coverage':len(b)/expected,'gaps':len(gaps),'gap_examples':[(c.iso(a),c.iso(z)) for a,z in gaps[:10]],'api_calls':calls,'native_bybit_replay_required':True}

def load(sym):
    try:return c.load(sym)
    except Exception as e:
        print(f'BYBIT_NATIVE_UNAVAILABLE {sym} {type(e).__name__}: {e}; FALLBACK=BinanceSpot5m research proxy',flush=True)
        return load_binance(sym)

c.load=load
if __name__=='__main__':c.main()
