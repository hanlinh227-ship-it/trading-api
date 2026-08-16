#!/usr/bin/env python3
import json, math, urllib.parse, urllib.request
from datetime import datetime, timezone

OKX_BASE = "https://www.okx.com"

TESTS = [
    ("BTCUSDT", "2026-08-01T12:00:00Z"),
    ("ETHUSDT", "2026-08-02T16:00:00Z"),
    ("SOLUSDT", "2026-08-03T08:00:00Z"),
    ("XRPUSDT", "2026-08-04T12:00:00Z"),
    ("AAVEUSDT", "2026-08-05T16:00:00Z"),
    ("SUIUSDT", "2026-08-06T08:00:00Z"),
    ("PENGUUSDT", "2026-08-07T12:00:00Z"),
    ("KAITOUSDT", "2026-08-08T08:00:00Z"),
    ("ETHUSDT", "2026-08-11T08:00:00Z"),
    ("SOLUSDT", "2026-08-12T12:00:00Z"),
]

TF = {"D1":"1Dutc", "H4":"4H", "H1":"1H", "M15":"15m", "M5":"5m"}
TF_MS = {"D1":86400000, "H4":14400000, "H1":3600000, "M15":900000, "M5":300000}


def iso_to_ms(s): return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
def ms_to_iso(ms): return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat().replace("+00:00", "Z")

def http_json(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"trading-api-blind-test/2.0"})
    with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode("utf-8"))

def f(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except:return None

def rows_to_candles(rows):
    out=[]
    for r in rows:
        ts=int(r[0]); out.append({"ts":ts,"datetime":ms_to_iso(ts),"open":f(r[1]),"high":f(r[2]),"low":f(r[3]),"close":f(r[4]),"volume":f(r[5])})
    out=[x for x in out if x["close"] is not None]; out.sort(key=lambda x:x["ts"]); return out

def fetch_history(inst,bar,cutoff_ms,limit=300):
    url=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={urllib.parse.quote(bar)}&after={cutoff_ms}&limit={limit}"
    return rows_to_candles((http_json(url).get("data") or []))

def fetch_future(inst,cutoff_ms,hours=12):
    end_ms=cutoff_ms+hours*3600*1000
    url=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={cutoff_ms}&after={end_ms}&limit=300"
    cs=rows_to_candles((http_json(url).get("data") or [])); return [x for x in cs if cutoff_ms<=x["ts"]<end_ms]

def ema(vals,p):
    if len(vals)<p:return None
    k=2/(p+1); v=sum(vals[:p])/p
    for x in vals[p:]:v=x*k+v*(1-k)
    return v

def rsi(vals,p=14):
    if len(vals)<=p:return None
    gains=losses=0.0
    for i in range(1,p+1):
        d=vals[i]-vals[i-1]; gains+=max(d,0); losses+=max(-d,0)
    ag,al=gains/p,losses/p
    for i in range(p+1,len(vals)):
        d=vals[i]-vals[i-1]; ag=(ag*(p-1)+max(d,0))/p; al=(al*(p-1)+max(-d,0))/p
    if al==0:return 100.0
    rs=ag/al; return 100-100/(1+rs)

def atr(cs,p=14):
    if len(cs)<=p:return None
    tr=[]
    for i in range(1,len(cs)):
        c,pr=cs[i],cs[i-1]; tr.append(max(c["high"]-c["low"],abs(c["high"]-pr["close"]),abs(c["low"]-pr["close"])))
    v=sum(tr[:p])/p
    for x in tr[p:]:v=(v*(p-1)+x)/p
    return v

def summary(cs):
    vals=[x["close"] for x in cs]; e20,e50,e200=ema(vals,20),ema(vals,50),ema(vals,200); rr=rsi(vals); aa=atr(cs); c=cs[-1]["close"]
    trend="neutral"
    if e20 is not None and e50 is not None:
        if c>e20>e50:trend="bullish"
        elif c<e20<e50:trend="bearish"
    dist=((c-e20)/aa) if e20 is not None and aa not in (None,0) else None
    return {"close":c,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rr,"atr14":aa,"trend":trend,"dist20ATR":dist}

def recent_structure(cs,lookback=12):
    recent=cs[-lookback:]; last=recent[-1]; prev=recent[:-1]
    return {"breakoutUp":last["close"]>max(x["high"] for x in prev),"breakoutDown":last["close"]<min(x["low"] for x in prev),"bullClose":last["close"]>last["open"],"bearClose":last["close"]<last["open"]}

def decide(sums,frames):
    weights={"D1":3.0,"H4":3.0,"H1":2.5,"M15":1.5,"M5":1.0}; score=0.0
    for k,w in weights.items():
        s=sums[k]; c=s["close"]
        if s["trend"]=="bullish":score+=w
        elif s["trend"]=="bearish":score-=w
        if s["ema200"] is not None:score+=(0.30*w if c>s["ema200"] else -0.30*w)
        if s["rsi14"] is not None:
            if s["rsi14"]>=55:score+=0.15*w
            elif s["rsi14"]<=45:score-=0.15*w
    d1,h4,h1,m15,m5=[sums[k] for k in ("D1","H4","H1","M15","M5")]; m5s=recent_structure(frames["M5"]); reasons=[]
    if (d1["trend"]=="bullish" and h4["trend"]=="bearish") or (d1["trend"]=="bearish" and h4["trend"]=="bullish"):
        return "WAIT",score,None,["D1/H4 conflict"]
    long_bias=h4["trend"]=="bullish" and h1["trend"] in ("bullish","neutral") and score>=6.5
    short_bias=h4["trend"]=="bearish" and h1["trend"] in ("bearish","neutral") and score<=-6.5
    if d1["trend"]=="neutral":
        if long_bias and h1["trend"]!="bullish":long_bias=False
        if short_bias and h1["trend"]!="bearish":short_bias=False
    if long_bias and m5["trend"]=="bearish":long_bias=False; reasons.append("M5 bearish blocks BUY")
    if short_bias and m5["trend"]=="bullish":short_bias=False; reasons.append("M5 bullish blocks SELL")
    if long_bias and m15["trend"]=="bearish":long_bias=False; reasons.append("M15 bearish blocks BUY")
    if short_bias and m15["trend"]=="bullish":short_bias=False; reasons.append("M15 bullish blocks SELL")
    for key,s in (("H1",h1),("M15",m15)):
        d=s.get("dist20ATR")
        if long_bias and d is not None and d>1.15:long_bias=False; reasons.append(f"BUY stretched {key}")
        if short_bias and d is not None and d<-1.15:short_bias=False; reasons.append(f"SELL stretched {key}")
    if long_bias and ((m15["rsi14"] or 50)>68 or (m5["rsi14"] or 50)>70):long_bias=False; reasons.append("LTF overbought")
    if short_bias and ((m15["rsi14"] or 50)<32 or (m5["rsi14"] or 50)<30):short_bias=False; reasons.append("LTF oversold")
    long_trigger=(m5s["bullClose"] and m5["close"]>=m5["ema20"]) or m5s["breakoutUp"]
    short_trigger=(m5s["bearClose"] and m5["close"]<=m5["ema20"]) or m5s["breakoutDown"]
    if long_bias and not long_trigger:long_bias=False; reasons.append("No M5 long trigger")
    if short_bias and not short_trigger:short_bias=False; reasons.append("No M5 short trigger")
    side="BUY" if long_bias else "SELL" if short_bias else "WAIT"; entry=frames["M5"][-1]["close"]
    if side=="WAIT":return side,score,None,reasons
    a=m15["atr14"] or entry*0.01; recent=frames["M15"][-10:]
    sl=min(min(x["low"] for x in recent),entry-1.35*a) if side=="BUY" else max(max(x["high"] for x in recent),entry+1.35*a)
    return side,score,sl,reasons

def evaluate(side,entry,sl,tp,future):
    if side=="WAIT":
        if not future:return {"result":"WAIT_NO_DATA"}
        return {"result":"WAIT","maxUp":max(x["high"] for x in future)-entry,"maxDown":entry-min(x["low"] for x in future)}
    mfe=mae=0.0
    for x in future:
        if side=="BUY":mfe=max(mfe,x["high"]-entry); mae=max(mae,entry-x["low"]); hit_sl=x["low"]<=sl; hit_tp=x["high"]>=tp
        else:mfe=max(mfe,entry-x["low"]); mae=max(mae,x["high"]-entry); hit_sl=x["high"]>=sl; hit_tp=x["low"]<=tp
        if hit_sl and hit_tp:return {"result":"AMBIGUOUS_SAME_CANDLE","mfe":mfe,"mae":mae}
        if hit_sl:return {"result":"SL","mfe":mfe,"mae":mae}
        if hit_tp:return {"result":"TP2R","mfe":mfe,"mae":mae}
    return {"result":"OPEN_12H","mfe":mfe,"mae":mae}

def run_one(symbol,cutoff):
    base=symbol[:-4] if symbol.endswith("USDT") else symbol; inst=f"{base}-USDT"; cutoff_ms=iso_to_ms(cutoff); frames={}; sums={}
    for key,bar in TF.items():
        cs=fetch_history(inst,bar,cutoff_ms,300); cs=[x for x in cs if x["ts"]+TF_MS[key]<=cutoff_ms]
        if len(cs)<50:raise RuntimeError(f"{symbol} {key}: insufficient candles {len(cs)}")
        frames[key]=cs; sums[key]=summary(cs)
    entry=frames["M5"][-1]["close"]; side,score,sl,reasons=decide(sums,frames); tp=None
    if side=="BUY" and sl is not None:tp=entry+2*(entry-sl)
    elif side=="SELL" and sl is not None:tp=entry-2*(sl-entry)
    future=fetch_future(inst,cutoff_ms,12); out=evaluate(side,entry,sl,tp,future)
    return {"symbol":symbol,"cutoff":cutoff,"source":"OKX historical REST","blind":True,"decision":side,"score":round(score,2),"entry":entry,"sl":sl,"tp2R":tp,"filters":reasons,"snapshot":{k:{kk:(round(vv,8) if isinstance(vv,float) else vv) for kk,vv in s.items()} for k,s in sums.items()},"outcome12h":out,"futureCandles":len(future)}

def main():
    results=[]
    for s,t in TESTS:
        try:results.append(run_one(s,t))
        except Exception as e:results.append({"symbol":s,"cutoff":t,"error":str(e)})
    trades=[r for r in results if r.get("decision") in ("BUY","SELL")]; wins=sum(1 for r in trades if r.get("outcome12h",{}).get("result")=="TP2R"); losses=sum(1 for r in trades if r.get("outcome12h",{}).get("result")=="SL"); open12=sum(1 for r in trades if r.get("outcome12h",{}).get("result")=="OPEN_12H"); waits=sum(1 for r in results if r.get("decision")=="WAIT")
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V2 strict blind: HTF bias + M15/M5 confirmation + anti-chase ATR filter + exhaustion guard; only closed candles; 12h M5 forward check; 2R target","tests":results,"summary":{"cases":len(results),"trades":len(trades),"wins":wins,"losses":losses,"open12h":open12,"waits":waits,"winRateClosed":round(100*wins/(wins+losses),2) if wins+losses else None}}
    with open("data/blind_backtest.json","w",encoding="utf-8") as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps(payload["summary"],indent=2))

if __name__=="__main__":main()
