#!/usr/bin/env python3
import json, math, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

OKX_BASE = "https://www.okx.com"

TESTS = [
    ("BTCUSDT", "2026-08-08T12:00:00Z"),
    ("ETHUSDT", "2026-08-09T16:00:00Z"),
    ("SOLUSDT", "2026-08-10T08:00:00Z"),
    ("XRPUSDT", "2026-08-11T12:00:00Z"),
    ("AAVEUSDT", "2026-08-12T16:00:00Z"),
    ("SUIUSDT", "2026-08-13T08:00:00Z"),
    ("PENGUUSDT", "2026-08-14T12:00:00Z"),
    ("KAITOUSDT", "2026-08-15T08:00:00Z"),
]

TF = {"D1":"1Dutc", "H4":"4H", "H1":"1H", "M15":"15m", "M5":"5m"}


def iso_to_ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def ms_to_iso(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat().replace("+00:00", "Z")


def http_json(url):
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"trading-api-blind-test/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def f(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except: return None


def fetch_history(inst, bar, cutoff_ms, limit=300):
    # OKX 'after' returns records older than the supplied timestamp.
    url = f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={urllib.parse.quote(bar)}&after={cutoff_ms}&limit={limit}"
    data=http_json(url)
    rows=data.get("data") or []
    out=[]
    for r in rows:
        ts=int(r[0]);
        out.append({"ts":ts,"datetime":ms_to_iso(ts),"open":f(r[1]),"high":f(r[2]),"low":f(r[3]),"close":f(r[4]),"volume":f(r[5])})
    out=[x for x in out if x["close"] is not None]
    out.sort(key=lambda x:x["ts"])
    return out


def fetch_future(inst, cutoff_ms, hours=12):
    # use current/history endpoint and page backwards from end horizon, then filter after cutoff
    end_ms = cutoff_ms + hours*3600*1000
    url = f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={end_ms}&limit=300"
    data=http_json(url)
    rows=data.get("data") or []
    out=[]
    for r in rows:
        ts=int(r[0])
        if cutoff_ms <= ts <= end_ms:
            out.append({"ts":ts,"datetime":ms_to_iso(ts),"open":f(r[1]),"high":f(r[2]),"low":f(r[3]),"close":f(r[4]),"volume":f(r[5])})
    out.sort(key=lambda x:x["ts"])
    return out


def ema(vals,p):
    if len(vals)<p:return None
    k=2/(p+1); v=sum(vals[:p])/p
    for x in vals[p:]: v=x*k+v*(1-k)
    return v


def rsi(vals,p=14):
    if len(vals)<=p:return None
    gains=losses=0.0
    for i in range(1,p+1):
        d=vals[i]-vals[i-1]
        gains += max(d,0); losses += max(-d,0)
    ag,al=gains/p,losses/p
    for i in range(p+1,len(vals)):
        d=vals[i]-vals[i-1]; g=max(d,0); l=max(-d,0)
        ag=(ag*(p-1)+g)/p; al=(al*(p-1)+l)/p
    if al==0:return 100.0
    rs=ag/al; return 100-100/(1+rs)


def atr(cs,p=14):
    if len(cs)<=p:return None
    tr=[]
    for i in range(1,len(cs)):
        c,pr=cs[i],cs[i-1]
        tr.append(max(c["high"]-c["low"],abs(c["high"]-pr["close"]),abs(c["low"]-pr["close"])))
    v=sum(tr[:p])/p
    for x in tr[p:]:v=(v*(p-1)+x)/p
    return v


def summary(cs):
    vals=[x["close"] for x in cs]
    e20,e50,e200=ema(vals,20),ema(vals,50),ema(vals,200)
    rr=rsi(vals,14); aa=atr(cs,14); c=cs[-1]["close"]
    trend="neutral"
    if e20 is not None and e50 is not None:
        if c>e20>e50:trend="bullish"
        elif c<e20<e50:trend="bearish"
    return {"close":c,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rr,"atr14":aa,"trend":trend}


def decide(sums, m15_cs):
    # frozen scoring: HTF weighted highest; market only when alignment is strong.
    weights={"D1":3.0,"H4":3.0,"H1":2.0,"M15":1.5,"M5":1.0}
    score=0.0; aligned={"bull":0,"bear":0}
    for k,w in weights.items():
        s=sums[k]; c=s["close"]
        if s["trend"]=="bullish": score+=w; aligned["bull"]+=1
        elif s["trend"]=="bearish": score-=w; aligned["bear"]+=1
        if s["ema200"] is not None:
            score += (0.35*w if c>s["ema200"] else -0.35*w)
        if s["rsi14"] is not None:
            if s["rsi14"]>=55: score+=0.20*w
            elif s["rsi14"]<=45: score-=0.20*w
    d1=sums["D1"]["trend"]; h4=sums["H4"]["trend"]
    # Severe HTF disagreement means wait.
    if (d1=="bullish" and h4=="bearish") or (d1=="bearish" and h4=="bullish"):
        return "WAIT",score,None,None
    side="WAIT"
    if score>=5.2 and aligned["bull"]>=3: side="BUY"
    elif score<=-5.2 and aligned["bear"]>=3: side="SELL"
    entry=m15_cs[-1]["close"]
    a=sums["M15"]["atr14"] or (entry*0.01)
    swing_low=min(x["low"] for x in m15_cs[-8:]); swing_high=max(x["high"] for x in m15_cs[-8:])
    if side=="BUY":
        sl=min(swing_low, entry-1.15*a); risk=entry-sl; tp=entry+2*risk
    elif side=="SELL":
        sl=max(swing_high, entry+1.15*a); risk=sl-entry; tp=entry-2*risk
    else:
        sl=tp=None
    return side,score,sl,tp


def evaluate(side,entry,sl,tp,future):
    if side=="WAIT":
        if not future:return {"result":"WAIT_NO_DATA"}
        max_up=max(x["high"] for x in future)-entry; max_dn=entry-min(x["low"] for x in future)
        return {"result":"WAIT","maxUp":max_up,"maxDown":max_dn}
    mfe=mae=0.0
    for x in future:
        if side=="BUY":
            mfe=max(mfe,x["high"]-entry); mae=max(mae,entry-x["low"])
            hit_sl=x["low"]<=sl; hit_tp=x["high"]>=tp
        else:
            mfe=max(mfe,entry-x["low"]); mae=max(mae,x["high"]-entry)
            hit_sl=x["high"]>=sl; hit_tp=x["low"]<=tp
        if hit_sl and hit_tp:return {"result":"AMBIGUOUS_SAME_CANDLE","mfe":mfe,"mae":mae}
        if hit_sl:return {"result":"SL","mfe":mfe,"mae":mae}
        if hit_tp:return {"result":"TP2R","mfe":mfe,"mae":mae}
    return {"result":"OPEN_12H","mfe":mfe,"mae":mae}


def run_one(symbol,cutoff):
    base=symbol[:-4] if symbol.endswith("USDT") else symbol
    inst=f"{base}-USDT"; cutoff_ms=iso_to_ms(cutoff)
    frames={}; sums={}
    for key,bar in TF.items():
        cs=fetch_history(inst,bar,cutoff_ms,300)
        # only candles opened before cutoff; enough history for indicators
        cs=[x for x in cs if x["ts"]<cutoff_ms]
        if len(cs)<50: raise RuntimeError(f"{symbol} {key}: insufficient candles {len(cs)}")
        frames[key]=cs; sums[key]=summary(cs)
    entry=frames["M5"][-1]["close"]
    side,score,sl,tp=decide(sums,frames["M15"])
    # force entry to exact last M5 close available at cutoff
    if side=="BUY" and sl is not None:
        risk=entry-sl; tp=entry+2*risk
    elif side=="SELL" and sl is not None:
        risk=sl-entry; tp=entry-2*risk
    future=fetch_future(inst,cutoff_ms,12)
    out=evaluate(side,entry,sl,tp,future)
    return {
        "symbol":symbol,"cutoff":cutoff,"source":"OKX historical REST","blind":True,
        "decision":side,"score":round(score,2),"entry":entry,
        "sl":sl,"tp2R":tp,
        "snapshot":{k:{kk:(round(vv,8) if isinstance(vv,float) else vv) for kk,vv in s.items()} for k,s in sums.items()},
        "outcome12h":out,
        "futureCandles":len(future)
    }


def main():
    results=[]
    for s,t in TESTS:
        try: results.append(run_one(s,t))
        except Exception as e: results.append({"symbol":s,"cutoff":t,"error":str(e)})
    trades=[r for r in results if r.get("decision") in ("BUY","SELL")]
    wins=sum(1 for r in trades if r.get("outcome12h",{}).get("result")=="TP2R")
    losses=sum(1 for r in trades if r.get("outcome12h",{}).get("result")=="SL")
    waits=sum(1 for r in results if r.get("decision")=="WAIT")
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"Frozen blind technical engine; no future candles used in decision; 12h forward check; 2R target","tests":results,"summary":{"cases":len(results),"trades":len(trades),"wins":wins,"losses":losses,"waits":waits,"winRateClosed":round(100*wins/(wins+losses),2) if wins+losses else None}}
    with open("data/blind_backtest.json","w",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps(payload["summary"],indent=2))

if __name__=="__main__": main()
