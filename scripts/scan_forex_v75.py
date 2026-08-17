#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures as cf
import json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import twelvedata_market as td

PAIRS="EURUSD GBPUSD USDJPY USDCHF USDCAD AUDUSD NZDUSD EURJPY EURGBP EURCHF EURAUD EURNZD EURCAD GBPJPY GBPCHF GBPAUD GBPNZD GBPCAD AUDJPY AUDNZD AUDCAD AUDCHF NZDJPY NZDCAD NZDCHF CADJPY CADCHF CHFJPY".split()


def par(items, fn, workers=16):
    out={}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        jobs={ex.submit(fn,x):x for x in items}
        for f in cf.as_completed(jobs):
            x=jobs[f]
            try: out[x]=f.result()
            except Exception as e: out[x]={"status":"error","error":str(e)}
    return out


def broad_one(sym):
    r=td.resolve_symbol(sym)
    if r.get("status")!="ok": return {"status":"DATA_BLOCK","resolution":r}
    fr=td.fetch_frame(r,"H1")
    return {"status":fr.get("status"),"resolution":r,"frame":fr}


def ranking(broad):
    rows=[]
    for sym in PAIRS:
        fr=broad[sym]["frame"]; s=fr.get("summary") or {}
        c,e20,e50,e200,rsi,atr=[s.get(k) for k in ("close","ema20","ema50","ema200","rsi14","atr14")]
        hi,lo=s.get("recent50High"),s.get("recent50Low")
        if any(v is None for v in (c,e20,e50,rsi,atr)): raise RuntimeError(f"Incomplete H1 {sym}")
        side,score="NEUTRAL",0.0
        if c>e20>e50: side,score="BUY",3.0
        elif c<e20<e50: side,score="SELL",3.0
        if e200 is not None and ((side=="BUY" and c>e200) or (side=="SELL" and c<e200)): score+=2
        if side=="BUY": score+=2 if 52<=rsi<=68 else 1 if 68<rsi<=72 else 0
        elif side=="SELL": score+=2 if 32<=rsi<=48 else 1 if 28<=rsi<32 else 0
        if rsi>=75 or rsi<=25: score-=3
        if side=="BUY" and hi and abs(hi-c)/abs(hi)<.001: score-=1
        if side=="SELL" and lo and abs(c-lo)/abs(lo)<.001: score-=1
        target=60 if side=="BUY" else 40 if side=="SELL" else 50
        rows.append({"symbol":sym,"marketSymbol":broad[sym]["resolution"]["marketSymbol"],"direction":side,"broadScore":round(score,3),"momentumQuality":round(-abs(rsi-target),3),"close":c,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rsi,"atr14":atr,"recent50High":hi,"recent50Low":lo,"h1ClosedCandleTime":(fr.get("latestCandle") or {}).get("datetime")})
    rows.sort(key=lambda x:(x["broadScore"],x["momentumQuality"],x["atr14"]),reverse=True)
    return rows


def deep(finalists,broad):
    out={s:{"resolution":broad[s]["resolution"],"frames":{"H1":broad[s]["frame"]}} for s in finalists}
    with cf.ThreadPoolExecutor(max_workers=15) as ex:
        jobs={}
        for s in finalists:
            r=out[s]["resolution"]
            for tf in ("D1","H4","M15","M5"): jobs[ex.submit(td.fetch_frame,r,tf)]=(s,tf)
            jobs[ex.submit(td.fetch_quote,r)]=(s,"Q")
        for f in cf.as_completed(jobs):
            s,k=jobs[f]
            try: v=f.result()
            except Exception as e: v={"status":"error","error":str(e)}
            if k=="Q": out[s]["quote"]=v
            else: out[s]["frames"][k]=v
    for s,row in out.items():
        bad=[k for k in ("D1","H4","H1","M15","M5") if row["frames"].get(k,{}).get("status")!="ok"]
        if bad or row.get("quote",{}).get("status")!="ok": raise RuntimeError(f"Deep validation failed {s}: {bad} {row.get('quote',{}).get('error')}")
    return out


def fdir(fr):
    x=fr.get("summary") or {}; c,a,b=x.get("close"),x.get("ema20"),x.get("ema50")
    if None in (c,a,b): return "NEUTRAL"
    return "BUY" if c>a>b else "SELL" if c<a<b else "NEUTRAL"


def build(finalists,rank,deep_rows,updated):
    rm={x["symbol"]:x for x in rank}; full=[]; fast=[]
    for sym in finalists:
        p=rm[sym]; row=deep_rows[sym]; frames=row["frames"]; q=row["quote"]; side=p["direction"]
        states={tf:fdir(frames[tf]) for tf in ("D1","H4","H1","M15","M5")}; score=float(p["broadScore"])
        for tf,w in {"D1":1,"H4":2,"H1":2,"M15":2,"M5":2}.items():
            if side!="NEUTRAL": score += w if states[tf]==side else -w if states[tf]!="NEUTRAL" else 0
        m15=(frames["M15"].get("summary") or {}).get("rsi14"); m5=(frames["M5"].get("summary") or {}).get("rsi14")
        if side=="BUY": score+=(.5 if m15 is not None and 48<=m15<=68 else 0)+(.5 if m5 is not None and 50<=m5<=70 else 0)
        elif side=="SELL": score+=(.5 if m15 is not None and 32<=m15<=52 else 0)+(.5 if m5 is not None and 30<=m5<=50 else 0)
        cand={"symbol":sym,"marketSymbol":row["resolution"]["marketSymbol"],"marketType":"forex","directionPrior":side,"broadScore":p["broadScore"],"deepScore":round(score,3),"frameDirection":states,"currentPrice":q.get("currentPrice"),"currentPriceTime":q.get("quoteTimestampISO"),"quoteAgeMs":q.get("quoteAgeMs"),"strictV74PriceFresh":q.get("strictV74PriceFresh"),"spreadVerified":False,"frames":frames}
        full.append(cand)
        st={"status":"ok","requestedSymbol":sym,"marketSymbol":cand["marketSymbol"],"marketType":"forex","provider":"Twelve Data","currentPrice":cand["currentPrice"],"currentPriceTime":cand["currentPriceTime"],"quoteAgeMs":cand["quoteAgeMs"],"strictV74PriceFresh":cand["strictV74PriceFresh"],"executionSpreadVerified":False,"executionReady":False,"analysisReady":True,"frames":frames,"updatedAt":updated}
        d=td.build_decision(st); d["rankScore"]=cand["deepScore"]; d["directionPrior"]=side; fast.append(d)
    full.sort(key=lambda x:x["deepScore"],reverse=True); fast.sort(key=lambda x:x.get("rankScore",-999),reverse=True)
    return full,fast


def main(out_dir="data"):
    t0=time.perf_counter(); broad=par(PAIRS,broad_one,16)
    failed=[s for s in PAIRS if broad.get(s,{}).get("status")!="ok"]
    if failed and len(failed)<=9:
        time.sleep(.5); retry=par(failed,broad_one,min(9,len(failed))); broad.update(retry); failed=[s for s in failed if broad[s].get("status")!="ok"]
    if failed: raise RuntimeError(f"Broad failures: {failed}")
    rank=ranking(broad); finalists=[x["symbol"] for x in rank[:3]]; dr=deep(finalists,broad); updated=datetime.now(timezone.utc).isoformat(); full,fast=build(finalists,rank,dr,updated)
    elapsed=round(time.perf_counter()-t0,3)
    result={"updatedAt":updated,"dataPolicy":"TWELVE_DATA_GROW55_DIRECT_FAST_V75","clientVersion":td.VERSION,"creditBudget":{"apiCreditsPerMinute":55,"normalEstimatedTotal":46,"reserveEstimated":9},"scanComplete":True,"pairsScanned":28,"broadTop10":rank[:10],"deepCandidates":full,"bestCandidateForV74Review":full[0]["symbol"] if full else None,"executionRule":"Ranking only; V74 still requires current news/context, strict M5 confirmation and execution-venue spread."}
    small={"updatedAt":updated,"source":"Twelve Data Grow55 direct","pairsScanned":28,"elapsedDataSeconds":elapsed,"best":fast[0]["symbol"] if fast else None,"top3":fast,"rule":"Fast read snapshot only; refresh finalist price/news/spread before MARKET."}
    os.makedirs(out_dir,exist_ok=True)
    for name,obj in (("forex-scan.json",result),("forex-fast.json",small)):
        with open(os.path.join(out_dir,name),"w",encoding="utf-8") as f: json.dump(obj,f,ensure_ascii=False,separators=(",",":"))
    print(json.dumps({"pairsScanned":28,"elapsedDataSeconds":elapsed,"finalists":finalists,"top":[{"symbol":x["symbol"],"bias":x.get("technicalBias"),"score":x.get("rankScore"),"price":x.get("currentPrice"),"ageMs":x.get("quoteAgeMs"),"m5":x.get("m5TriggerPrefilter")} for x in fast]},ensure_ascii=False))
    return 0

if __name__=="__main__": raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else "data"))
