#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures as cf
import json, math, os, sys, time
import urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

BASE="https://www.okx.com"
SYMS="BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC".split()
BARS={"D1":"1Dutc","H4":"4H","H1":"1H","M15":"15m","M5":"5m"}
SECS={"D1":86400,"H4":14400,"H1":3600,"M15":900,"M5":300}


def now(): return datetime.now(timezone.utc)
def get(path,params=None,timeout=8,retries=4):
    q=("?"+urllib.parse.urlencode(params)) if params else ""; last=None
    for n in range(retries+1):
        try:
            req=urllib.request.Request(BASE+path+q,headers={"Accept":"application/json","User-Agent":"trading-api-v75-crypto/1.1"})
            with urllib.request.urlopen(req,timeout=timeout) as r: obj=json.loads(r.read().decode())
            if obj.get("code")!="0": raise RuntimeError(obj.get("msg") or obj)
            return obj.get("data") or []
        except Exception as e:
            last=e
            if n<retries:
                is429=isinstance(e,urllib.error.HTTPError) and e.code==429
                time.sleep((.8 if is429 else .2)*(n+1))
    raise last

def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def ema(v,n):
    if len(v)<n:return None
    x=sum(v[:n])/n; a=2/(n+1)
    for y in v[n:]:x=a*y+(1-a)*x
    return x

def rsi(v,n=14):
    if len(v)<=n:return None
    ds=[v[i]-v[i-1] for i in range(1,len(v))]; up=sum(max(x,0) for x in ds[:n])/n; dn=sum(max(-x,0) for x in ds[:n])/n
    for x in ds[n:]:up=(up*(n-1)+max(x,0))/n; dn=(dn*(n-1)+max(-x,0))/n
    return 100.0 if dn==0 else 100-100/(1+up/dn)
def atr(rows,n=14):
    if len(rows)<=n:return None
    tr=[]
    for i in range(1,len(rows)):
        h,l,pc=rows[i][2],rows[i][3],rows[i-1][4]; tr.append(max(h-l,abs(h-pc),abs(l-pc)))
    x=sum(tr[:n])/n
    for y in tr[n:]:x=(x*(n-1)+y)/n
    return x

def closed_rows(raw,tf):
    out=[]; now_ms=int(now().timestamp()*1000)
    for x in raw:
        ts=int(x[0]); confirmed=str(x[-1])=="1" if len(x)>=9 else ts+SECS[tf]*1000<=now_ms
        if not confirmed: continue
        vals=[ts,f(x[1]),f(x[2]),f(x[3]),f(x[4]),f(x[5])]
        if None not in vals[1:5]: out.append(vals)
    out.sort(key=lambda x:x[0]); return out

def candles(sym,tf,limit=220):
    raw=get("/api/v5/market/candles",{"instId":sym+"-USDT","bar":BARS[tf],"limit":str(min(limit,300))})
    rows=closed_rows(raw,tf)
    if len(rows)<55: raise RuntimeError(f"{sym} {tf} insufficient:{len(rows)}")
    return rows

def met(rows):
    c=[x[4] for x in rows]; return {"close":c[-1],"ema20":ema(c,20),"ema50":ema(c,50),"ema200":ema(c,200),"rsi":rsi(c),"atr":atr(rows),"hi50":max(x[2] for x in rows[-50:]),"lo50":min(x[3] for x in rows[-50:])}
def h1_score(m):
    if None in (m["ema20"],m["ema50"],m["rsi"],m["atr"]): return 0,"NEUTRAL"
    c,a,b=m["close"],m["ema20"],m["ema50"]; side="LONG" if c>a>b else "SHORT" if c<a<b else "NEUTRAL"; sc=0.0
    if side!="NEUTRAL": sc=3.0
    if m["ema200"] is not None and ((side=="LONG" and c>m["ema200"]) or (side=="SHORT" and c<m["ema200"])): sc+=1.5
    if side=="LONG" and 50<=m["rsi"]<=70: sc+=1
    if side=="SHORT" and 30<=m["rsi"]<=50: sc+=1
    return sc,side

def sweep(rows,side):
    for j in range(max(10,len(rows)-8),len(rows)):
        p=rows[j-10:j]
        if side=="LONG":
            lv=min(x[3] for x in p)
            if rows[j][3]<lv and rows[j][4]>lv:return True,lv
        elif side=="SHORT":
            lv=max(x[2] for x in p)
            if rows[j][2]>lv and rows[j][4]<lv:return True,lv
    return False,None

def trigger(rows,side):
    last,prev=rows[-1],rows[-2]; a=atr(rows); body=abs(last[4]-last[1]); base=rows[-10:-2]
    if not a:return False,{"disp":False,"reclaim":False,"priorBreak":None}
    if side=="LONG":
        br=max(x[2] for x in base); disp=last[4]>br and last[4]>last[1] and body>=.4*a; low=min(x[3] for x in base); rec=prev[3]<low and prev[4]>prev[1] and last[4]>prev[4]
    else:
        br=min(x[3] for x in base); disp=last[4]<br and last[4]<last[1] and body>=.4*a; hi=max(x[2] for x in base); rec=prev[2]>hi and prev[4]<prev[1] and last[4]<prev[4]
    return bool(disp or rec),{"disp":bool(disp),"reclaim":bool(rec),"priorBreak":br}
def ticker_map():
    rows=get("/api/v5/market/tickers",{"instType":"SPOT"}); return {x.get("instId"):x for x in rows}
def qvol(t): return f(t.get("volCcy24h")) or 0.0

def par_tasks(tasks,workers=7):
    def once(items,w):
        out={}; errs={}
        with cf.ThreadPoolExecutor(max_workers=w) as ex:
            jobs={ex.submit(candles,s,tf):(s,tf) for s,tf in items}
            for fut in cf.as_completed(jobs):
                k=jobs[fut]
                try:out[k]=fut.result()
                except Exception as e:errs[k]=str(e)
        return out,errs
    out,errs=once(tasks,workers)
    if errs:
        time.sleep(1.0)
        retry,errs2=once(list(errs),min(4,len(errs)))
        out.update(retry); errs={k:errs2.get(k,errs[k]) for k in errs if k not in retry}
    return out,errs

def live(t):
    ts=int(t.get("ts") or 0); age=max(0,int(now().timestamp()*1000)-ts) if ts else None; bid=f(t.get("bidPx")); ask=f(t.get("askPx")); last=f(t.get("last")); mid=(bid+ask)/2 if bid is not None and ask is not None else last
    return {"bid":bid,"ask":ask,"last":last,"mid":mid,"tickerTs":ts,"quoteAgeMs":age,"spreadPct":((ask-bid)/mid*100 if bid is not None and ask is not None and mid else None),"volCcy24h":qvol(t),"strictQuoteFresh":bool(age is not None and age<=10000 and bid is not None and ask is not None)}


def main(out_dir="data"):
    t0=time.perf_counter(); tm=ticker_map(); available=[s for s in SYMS if s+"-USDT" in tm]
    h1,err=par_tasks([(s,"H1") for s in available],7)
    broad=[]
    for s in available:
        rows=h1.get((s,"H1"))
        if not rows:continue
        m=met(rows); sc,side=h1_score(m); broad.append({"symbol":s,"h1Score":sc,"side":side,"H1":m,"vol":qvol(tm[s+"-USDT"])})
    broad.sort(key=lambda x:(x["h1Score"],x["vol"]),reverse=True); top12=[x["symbol"] for x in broad[:12]]
    mid,err2=par_tasks([(s,tf) for s in top12 for tf in ("M15","M5")],7)
    stage=[]; bm={x["symbol"]:x for x in broad}
    for s in top12:
        if (s,"M15") not in mid or (s,"M5") not in mid:continue
        base=bm[s]; side=base["side"]
        if side=="NEUTRAL":
            m5=met(mid[(s,"M5")]); side="LONG" if m5["close"]>m5["ema20"] else "SHORT"
        sw,lv=sweep(mid[(s,"M15")],side); tr,tg=trigger(mid[(s,"M5")],side); m15=met(mid[(s,"M15")]); m5=met(mid[(s,"M5")]); score=base["h1Score"]+(1.7 if sw else 0)+(2.2 if tr else 0)+(.7 if (side=="LONG" and m15["close"]>m15["ema20"]) or (side=="SHORT" and m15["close"]<m15["ema20"]) else 0)
        stage.append({"symbol":s,"side":side,"score":score,"sweep":sw,"sweepLevel":lv,"trigger":tr,"triggerDetail":tg,"H1":base["H1"],"M15":m15,"M5":m5,"vol":base["vol"]})
    stage.sort(key=lambda x:(x["trigger"],x["sweep"],x["score"],x["vol"]),reverse=True); top5=[x["symbol"] for x in stage[:5]]
    ht,err3=par_tasks([(s,tf) for s in top5 for tf in ("D1","H4")],6); sm={x["symbol"]:x for x in stage}; out=[]
    for s in top5:
        if (s,"D1") not in ht or (s,"H4") not in ht:continue
        x=sm[s]; d1,h4=met(ht[(s,"D1")]),met(ht[(s,"H4")]); side=x["side"]; sign=1 if side=="LONG" else -1; score=x["score"]+(1.0 if sign*(d1["close"]-d1["ema20"])>0 else -.5)+(1.5 if sign*(h4["close"]-h4["ema20"])>0 else -.8); lv=live(tm[s+"-USDT"]); midp=lv["mid"]; a=x["M15"]["atr"]
        if side=="LONG": swing=min(r[3] for r in mid[(s,"M15")][-10:]); sl=min(swing-.12*a,midp-.65*a); risk=midp-sl; tp1=midp+risk; tp2=midp+2*risk; target=x["H1"]["hi50"]; room=(target-midp)/risk if risk>0 else -99
        else: swing=max(r[2] for r in mid[(s,"M15")][-10:]); sl=max(swing+.12*a,midp+.65*a); risk=sl-midp; tp1=midp-risk; tp2=midp-2*risk; target=x["H1"]["lo50"]; room=(midp-target)/risk if risk>0 else -99
        out.append({"symbol":s,"side":side,"score":round(score,3),**lv,"D1":d1,"H4":h4,"H1":x["H1"],"M15":x["M15"],"M5":x["M5"],"m15Sweep":x["sweep"],"sweepLevel":x["sweepLevel"],"m5Trigger":x["trigger"],**x["triggerDetail"],"strictM5Ready":bool(x["trigger"] and lv["strictQuoteFresh"]),"sl":sl,"tp1":tp1,"tp2":tp2,"roomToH1LiquidityR":room,"rr2EligibleByRoom":bool(room>=2.2)})
    out.sort(key=lambda x:(x["strictM5Ready"],x["m5Trigger"],x["m15Sweep"],x["score"],x["volCcy24h"]),reverse=True)
    errors=list(err.values())+list(err2.values())+list(err3.values()); result={"updatedAt":now().isoformat(),"source":"OKX public REST","universeRequested":len(SYMS),"universeAvailable":len(available),"broadAnalyzed":len(broad),"coveragePct":round(len(broad)/len(available)*100,2) if available else 0,"stage2":len(stage),"elapsedDataSeconds":round(time.perf_counter()-t0,3),"top":out,"errors":errors[:8],"rule":"V75 staged scan: all available V74 coins H1 -> top12 M15/M5 -> top5 D1/H4. Final news/context and quote refresh still required before MARKET."}
    os.makedirs(out_dir,exist_ok=True)
    with open(os.path.join(out_dir,"crypto-fast.json"),"w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,separators=(",",":"))
    print("CRYPTO_FAST_JSON_START"); print(json.dumps(result,ensure_ascii=False,separators=(",",":"))); print("CRYPTO_FAST_JSON_END"); return 0

if __name__=="__main__":raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else "data"))
