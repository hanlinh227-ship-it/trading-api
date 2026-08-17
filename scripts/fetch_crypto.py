#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures as cf
import json, math, os, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

VERSION="V2-CRYPTO-FAST-STRICT"
BINANCE="https://api.binance.com"; OKX="https://www.okx.com"; BYBIT="https://api.bybit.com"
QUOTES=["FDUSD","USDT","USDC","USD","BTC","ETH","BNB","EUR"]
FRAMES=[
    {"key":"D1","interval":"1day","fetchSize":220,"returnSize":12},
    {"key":"H4","interval":"4h","fetchSize":220,"returnSize":16},
    {"key":"H1","interval":"1h","fetchSize":220,"returnSize":20},
    {"key":"M15","interval":"15min","fetchSize":220,"returnSize":28},
    {"key":"M5","interval":"5min","fetchSize":220,"returnSize":36},
]
SECS={"1min":60,"5min":300,"15min":900,"1h":3600,"4h":14400,"1day":86400}


def now(): return datetime.now(timezone.utc)
def now_iso(): return now().isoformat().replace("+00:00","Z")
def clean(v): return str(v).upper().replace("/","").replace("-","").replace("_","").replace(":","").replace(" ","").strip()
def fnum(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def rnd(v,d=8): return None if v is None or not math.isfinite(v) else round(v,d)


def pair(sym):
    s=clean(sym)
    for q in QUOTES:
        if s.endswith(q):
            b=s[:-len(q)]
            if 2<=len(b)<=20 and b.isalnum() and b!=q:return b,q
    return None


def http(url,timeout=12):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"trading-api-v75/2.0"}); t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: raw=r.read().decode(); code=r.status
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors="replace")
        try:data=json.loads(raw)
        except Exception:data={"raw":raw[:500]}
        return {"ok":False,"httpStatus":e.code,"data":data,"latencyMs":int((time.time()-t)*1000)}
    except Exception as e:return {"ok":False,"error":str(e),"latencyMs":int((time.time()-t)*1000)}
    try:data=json.loads(raw)
    except Exception:return {"ok":False,"httpStatus":code,"error":"INVALID_JSON","latencyMs":int((time.time()-t)*1000)}
    return {"ok":200<=code<300,"httpStatus":code,"data":data,"latencyMs":int((time.time()-t)*1000)}


def ema(v,n):
    if len(v)<n:return None
    r=sum(v[:n])/n; k=2/(n+1)
    for x in v[n:]:r=x*k+r*(1-k)
    return r

def rsi(v,n=14):
    if len(v)<=n:return None
    ds=[v[i]-v[i-1] for i in range(1,len(v))]; g=sum(max(x,0) for x in ds[:n])/n; l=sum(max(-x,0) for x in ds[:n])/n
    for x in ds[n:]:g=(g*(n-1)+max(x,0))/n; l=(l*(n-1)+max(-x,0))/n
    return 100.0 if l==0 else 100-100/(1+g/l)
def atr(c,n=14):
    if len(c)<=n:return None
    tr=[max(c[i]["high"]-c[i]["low"],abs(c[i]["high"]-c[i-1]["close"]),abs(c[i]["low"]-c[i-1]["close"])) for i in range(1,len(c))]
    r=sum(tr[:n])/n
    for x in tr[n:]:r=(r*(n-1)+x)/n
    return r

def summary(c):
    if len(c)<20:return None
    v=[x["close"] for x in c]; x=c[-1]; e20,e50,e200=ema(v,20),ema(v,50),ema(v,200); rr=c[-50:]; trend="neutral"
    if e20 is not None and e50 is not None:
        if x["close"]>e20>e50:trend="bullish"
        elif x["close"]<e20<e50:trend="bearish"
    return {"close":rnd(x["close"]),"ema20":rnd(e20),"ema50":rnd(e50),"ema200":rnd(e200),"rsi14":rnd(rsi(v),2),"atr14":rnd(atr(c)),"recent50High":rnd(max(y["high"] for y in rr)),"recent50Low":rnd(min(y["low"] for y in rr)),"trend":trend}


def closed(dt,interval):
    try:t=datetime.fromisoformat(str(dt).replace("Z","+00:00")); return (t.timestamp()+SECS[interval])<=now().timestamp()
    except Exception:return True


def finalize(c,frame):
    c=[x for x in c if all(fnum(x.get(k)) is not None for k in ("open","high","low","close")) and closed(x.get("datetime"),frame["interval"])]
    c.sort(key=lambda x:x["datetime"])
    if not c:return {"status":"error","interval":frame["interval"],"error":"NO_CLOSED_CANDLES"}
    tail=[[x["datetime"],x["open"],x["high"],x["low"],x["close"],x.get("volume")] for x in c[-frame["returnSize"]:]]
    return {"status":"ok","interval":frame["interval"],"candleCount":len(c),"latestCandle":c[-1],"summary":summary(c),"candles":tail}


def bin_ticker(sym):
    r=http(f"{BINANCE}/api/v3/ticker/24hr?symbol={urllib.parse.quote(sym)}"); d=r.get("data") or {}
    if not r.get("ok") or fnum(d.get("lastPrice")) is None:return None,d.get("msg") or r.get("error") or "BINANCE_TICKER"
    ts=fnum(d.get("closeTime")); iso=datetime.fromtimestamp(ts/1000,timezone.utc).isoformat().replace("+00:00","Z") if ts else now_iso()
    return {"exchange":"Binance","symbol":sym,"lastPrice":fnum(d.get("lastPrice")),"bid":fnum(d.get("bidPrice")),"ask":fnum(d.get("askPrice")),"timestamp":iso,"latencyMs":r.get("latencyMs"),"volume24h":fnum(d.get("volume")),"quoteVolume24h":fnum(d.get("quoteVolume"))},None

def bin_k(sym,fr):
    iv={"5min":"5m","15min":"15m","1h":"1h","4h":"4h","1day":"1d"}.get(fr["interval"]); r=http(f"{BINANCE}/api/v3/klines?symbol={urllib.parse.quote(sym)}&interval={iv}&limit={min(fr['fetchSize'],1000)}")
    if not r.get("ok") or not isinstance(r.get("data"),list):return {"status":"error","error":"BINANCE_KLINE"}
    c=[{"datetime":datetime.fromtimestamp(float(x[0])/1000,timezone.utc).isoformat().replace("+00:00","Z"),"open":fnum(x[1]),"high":fnum(x[2]),"low":fnum(x[3]),"close":fnum(x[4]),"volume":fnum(x[5])} for x in r["data"]]
    return finalize(c,fr)


def okx_ticker(b,q):
    inst=f"{b}-{q}"; r=http(f"{OKX}/api/v5/market/ticker?instId={urllib.parse.quote(inst)}"); d=r.get("data") or {}; rows=d.get("data") if isinstance(d,dict) else None
    if not r.get("ok") or not rows:return None,(d.get("msg") if isinstance(d,dict) else None) or "OKX_TICKER"
    x=rows[0]; ts=fnum(x.get("ts")); iso=datetime.fromtimestamp(ts/1000,timezone.utc).isoformat().replace("+00:00","Z") if ts else now_iso()
    return {"exchange":"OKX","symbol":inst,"lastPrice":fnum(x.get("last")),"bid":fnum(x.get("bidPx")),"ask":fnum(x.get("askPx")),"timestamp":iso,"latencyMs":r.get("latencyMs"),"volume24h":fnum(x.get("vol24h")),"quoteVolume24h":fnum(x.get("volCcy24h"))},None

def okx_k(b,q,fr):
    inst=f"{b}-{q}"; bar={"5min":"5m","15min":"15m","1h":"1H","4h":"4H","1day":"1Dutc"}.get(fr["interval"]); r=http(f"{OKX}/api/v5/market/candles?instId={urllib.parse.quote(inst)}&bar={urllib.parse.quote(bar)}&limit={min(fr['fetchSize'],300)}"); d=r.get("data") or {}; rows=d.get("data") if isinstance(d,dict) else None
    if not r.get("ok") or not isinstance(rows,list):return {"status":"error","error":"OKX_KLINE"}
    c=[{"datetime":datetime.fromtimestamp(float(x[0])/1000,timezone.utc).isoformat().replace("+00:00","Z"),"open":fnum(x[1]),"high":fnum(x[2]),"low":fnum(x[3]),"close":fnum(x[4]),"volume":fnum(x[5])} for x in rows]
    return finalize(c,fr)


def by_ticker(sym):
    r=http(f"{BYBIT}/v5/market/tickers?category=spot&symbol={urllib.parse.quote(sym)}"); d=r.get("data") or {}; rows=((d.get("result") or {}).get("list")) if isinstance(d,dict) else None
    if not r.get("ok") or d.get("retCode")!=0 or not rows:return None,d.get("retMsg") or "BYBIT_TICKER"
    x=rows[0]; ts=fnum(d.get("time")); iso=datetime.fromtimestamp(ts/1000,timezone.utc).isoformat().replace("+00:00","Z") if ts else now_iso()
    return {"exchange":"Bybit","symbol":sym,"lastPrice":fnum(x.get("lastPrice")),"bid":fnum(x.get("bid1Price")),"ask":fnum(x.get("ask1Price")),"timestamp":iso,"latencyMs":r.get("latencyMs"),"volume24h":fnum(x.get("volume24h")),"quoteVolume24h":fnum(x.get("turnover24h"))},None

def by_k(sym,fr):
    iv={"5min":"5","15min":"15","1h":"60","4h":"240","1day":"D"}.get(fr["interval"]); r=http(f"{BYBIT}/v5/market/kline?category=spot&symbol={urllib.parse.quote(sym)}&interval={iv}&limit={min(fr['fetchSize'],1000)}"); d=r.get("data") or {}; rows=((d.get("result") or {}).get("list")) if isinstance(d,dict) else None
    if not r.get("ok") or d.get("retCode")!=0 or not isinstance(rows,list):return {"status":"error","error":"BYBIT_KLINE"}
    c=[{"datetime":datetime.fromtimestamp(float(x[0])/1000,timezone.utc).isoformat().replace("+00:00","Z"),"open":fnum(x[1]),"high":fnum(x[2]),"low":fnum(x[3]),"close":fnum(x[4]),"volume":fnum(x[5])} for x in rows]
    return finalize(c,fr)


def ticker(src,sym,b,q): return bin_ticker(sym) if src=="Binance" else okx_ticker(b,q) if src=="OKX" else by_ticker(sym)
def kline(src,sym,b,q,fr): return bin_k(sym,fr) if src=="Binance" else okx_k(b,q,fr) if src=="OKX" else by_k(sym,fr)


def choose(sym,b,q):
    attempts=[]; probe={"key":"M5","interval":"5min","fetchSize":25,"returnSize":4}
    for src in ("Binance","OKX","Bybit"):
        t,e=ticker(src,sym,b,q)
        if not t: attempts.append({"source":src,"ok":False,"error":e}); continue
        p=kline(src,sym,b,q,probe)
        if p.get("status")!="ok": attempts.append({"source":src,"ok":False,"error":p.get("error")}); continue
        attempts.append({"source":src,"ok":True}); return src,t,attempts
    return None,None,attempts


def age_ms(ts):
    try:return max(0,int((now()-datetime.fromisoformat(ts.replace("Z","+00:00"))).total_seconds()*1000))
    except Exception:return None

def spr(b,a): return None if b is None or a is None else a-b


def main():
    if len(sys.argv)<3:return 2
    sym=clean(sys.argv[1]); out=sys.argv[2].rstrip("/"); pq=pair(sym)
    if not pq:return 2
    b,q=pq; src,t,attempts=choose(sym,b,q)
    if not src:
        print(json.dumps({"status":"error","error":"CRYPTO_SOURCE_UNAVAILABLE","attempts":attempts}),file=sys.stderr); return 1

    results={}
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        jobs={ex.submit(kline,src,sym,b,q,fr):fr["key"] for fr in FRAMES}
        for f in cf.as_completed(jobs):
            key=jobs[f]
            try:results[key]=f.result()
            except Exception as e:results[key]={"status":"error","error":str(e)}
    if any(results.get(fr["key"],{}).get("status")!="ok" for fr in FRAMES):
        print(json.dumps({"status":"error","error":"ANALYSIS_FRAMES_FAILED","source":src}),file=sys.stderr); return 1

    fresh,e=ticker(src,sym,b,q)
    if fresh:t=fresh
    age=age_ms(t.get("timestamp")); stale=age is None or age>10000; bid,ask=t.get("bid"),t.get("ask"); spread_ok=bid is not None and ask is not None
    analysis={"status":"ok","workerVersion":VERSION,"provider":src,"sourceExchange":src,"sourceType":"github_runner_exchange_rest_fast","mode":"analysis","symbol":sym,"marketSymbol":f"{b}/{q}","marketType":"crypto","generatedAt":now_iso(),"symbolVerified":True,"priceType":"direct_exchange_last_price","currentPrice":t.get("lastPrice"),"currentPriceTime":t.get("timestamp"),"bid":bid,"ask":ask,"spread":spr(bid,ask),"quoteAgeMs":age,"stale":stale,"executionReady":bool(not stale and spread_ok),"analysisReady":True,"successfulFrames":5,"failedFrames":0,"timeframes":results,"sourceAttempts":attempts}
    refresh={"status":"ok","workerVersion":VERSION,"provider":src,"sourceExchange":src,"sourceType":"github_runner_exchange_rest_fast","mode":"refresh","symbol":sym,"marketSymbol":f"{b}/{q}","marketType":"crypto","generatedAt":now_iso(),"symbolVerified":True,"priceType":"direct_exchange_last_price","currentPrice":t.get("lastPrice"),"currentPriceTime":t.get("timestamp"),"bid":bid,"ask":ask,"spread":spr(bid,ask),"quoteAgeMs":age,"stale":stale,"executionReady":bool(not stale and spread_ok),"analysisReady":True,"successfulFrames":0,"failedFrames":0,"timeframes":{},"sourceAttempts":attempts}
    os.makedirs(out,exist_ok=True)
    with open(f"{out}/analysis.tmp.json","w",encoding="utf-8") as f:json.dump(analysis,f,ensure_ascii=False,separators=(",",":"))
    with open(f"{out}/refresh.tmp.json","w",encoding="utf-8") as f:json.dump(refresh,f,ensure_ascii=False,separators=(",",":"))
    print(json.dumps({"source":src,"symbol":sym,"price":t.get("lastPrice"),"bid":bid,"ask":ask,"quoteAgeMs":age,"executionReady":refresh["executionReady"],"frames":"5/5"},ensure_ascii=False))
    return 0

if __name__=="__main__":raise SystemExit(main())
