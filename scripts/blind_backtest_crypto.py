#!/usr/bin/env python3
import json, math, urllib.parse, urllib.request, time, statistics
from datetime import datetime, timezone

OKX_BASE="https://www.okx.com"
COINS="BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC".split()
MEMES=set("SHIB BONK DOGE FLOKI MOODENG ORDI PENGU PEPE PNUT POPCAT TRUMP WIF AIXBT FARTCOIN PUMP".split())
MAJORS=set("BTC ETH SOL XRP ADA BNB".split())
TF={"D1":"1Dutc","H4":"4H","H1":"1H","M15":"15m","M5":"5m"}
TF_MS={"D1":86400000,"H4":14400000,"H1":3600000,"M15":900000,"M5":300000}
CUTOFF="2026-08-12T12:00:00Z"
MAX_FORWARD_HOURS=72
RR_TARGET=1.5

def iso_ms(s): return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
def ms_iso(ms): return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat().replace("+00:00","Z")
def http(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"breakout-blind-v4"})
    for n in range(4):
        try:
            with urllib.request.urlopen(req,timeout=25) as r: return json.loads(r.read().decode())
        except Exception:
            if n==3: raise
            time.sleep(0.8*(n+1))
def fv(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except: return None
def rows(rs):
    out=[]
    for r in rs:
        ts=int(r[0]); out.append({"ts":ts,"datetime":ms_iso(ts),"open":fv(r[1]),"high":fv(r[2]),"low":fv(r[3]),"close":fv(r[4]),"volume":fv(r[5])})
    return sorted([x for x in out if x["close"] is not None],key=lambda x:x["ts"])
def hist(inst,bar,cut,limit=300):
    u=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={bar}&after={cut}&limit={limit}"
    return rows(http(u).get("data") or [])
def future_page(inst,before,after):
    u=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={before}&after={after}&limit=300"
    return rows(http(u).get("data") or [])
def ema(v,p):
    if len(v)<p:return None
    x=sum(v[:p])/p; k=2/(p+1)
    for z in v[p:]: x=z*k+x*(1-k)
    return x
def rsi(v,p=14):
    if len(v)<=p:return None
    g=l=0.0
    for i in range(1,p+1):
        d=v[i]-v[i-1]; g+=max(d,0); l+=max(-d,0)
    g/=p; l/=p
    for i in range(p+1,len(v)):
        d=v[i]-v[i-1]; g=(g*(p-1)+max(d,0))/p; l=(l*(p-1)+max(-d,0))/p
    return 100.0 if l==0 else 100-100/(1+g/l)
def atr(c,p=14):
    if len(c)<=p:return None
    tr=[]
    for i in range(1,len(c)):
        cur,pr=c[i],c[i-1]
        tr.append(max(cur["high"]-cur["low"],abs(cur["high"]-pr["close"]),abs(cur["low"]-pr["close"])))
    x=sum(tr[:p])/p
    for z in tr[p:]: x=(x*(p-1)+z)/p
    return x
def adx(c,p=14):
    if len(c)<p*2+2:return None
    trs=[]; plus=[]; minus=[]
    for i in range(1,len(c)):
        up=c[i]["high"]-c[i-1]["high"]; dn=c[i-1]["low"]-c[i]["low"]
        plus.append(up if up>dn and up>0 else 0.0); minus.append(dn if dn>up and dn>0 else 0.0)
        trs.append(max(c[i]["high"]-c[i]["low"],abs(c[i]["high"]-c[i-1]["close"]),abs(c[i]["low"]-c[i-1]["close"])))
    atrs=sum(trs[:p]); ps=sum(plus[:p]); ms=sum(minus[:p]); dx=[]
    for i in range(p,len(trs)):
        if i>p:
            atrs=atrs-atrs/p+trs[i]; ps=ps-ps/p+plus[i]; ms=ms-ms/p+minus[i]
        pdi=100*ps/atrs if atrs else 0; mdi=100*ms/atrs if atrs else 0
        dx.append(100*abs(pdi-mdi)/(pdi+mdi) if pdi+mdi else 0)
    if len(dx)<p:return None
    a=sum(dx[:p])/p
    for z in dx[p:]: a=(a*(p-1)+z)/p
    return a
def ret(c,n):
    if len(c)<=n or c[-n-1]["close"]==0:return 0.0
    return c[-1]["close"]/c[-n-1]["close"]-1
def structure(c,n=20):
    x=c[-n:]; m=max(2,n//2); a=x[:m]; b=x[m:]
    hh=max(z["high"] for z in b)>max(z["high"] for z in a); hl=min(z["low"] for z in b)>min(z["low"] for z in a)
    lh=max(z["high"] for z in b)<max(z["high"] for z in a); ll=min(z["low"] for z in b)<min(z["low"] for z in a)
    return 1 if hh and hl else -1 if lh and ll else 0
def breakout(c,n=20):
    if len(c)<n+1:return 0
    prev=c[-n-1:-1]; last=c[-1]
    if last["close"]>max(x["high"] for x in prev):return 1
    if last["close"]<min(x["low"] for x in prev):return -1
    return 0
def summ(c):
    v=[x["close"] for x in c]; cl=v[-1]; e20,e50,e200=ema(v,20),ema(v,50),ema(v,200); rr=rsi(v); aa=atr(c); ax=adx(c)
    trend="neutral"
    if e20 is not None and e50 is not None:
        if cl>e20>e50: trend="bullish"
        elif cl<e20<e50: trend="bearish"
    vv=[x["volume"] or 0 for x in c[-21:]]; base=sum(vv[:-1])/max(1,len(vv)-1); vr=vv[-1]/base if base else 1
    dist=(cl-e20)/aa if e20 is not None and aa else 0
    closes=v[-20:]; mid=sum(closes)/len(closes); sd=statistics.pstdev(closes) if len(closes)>1 else 0
    bbw=(4*sd/mid) if mid else 0
    return {"close":cl,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rr,"atr14":aa,"adx14":ax,"trend":trend,"dist20ATR":dist,"volumeRatio":vr,"bbWidth":bbw}
def load_frames(sym,cut):
    inst=f"{sym}-USDT"; frames={}; sums={}
    for k,b in TF.items():
        c=[x for x in hist(inst,b,cut) if x["ts"]+TF_MS[k]<=cut]
        if len(c)<60: raise RuntimeError(f"{k} insufficient:{len(c)}")
        frames[k]=c; sums[k]=summ(c)
    return frames,sums
def regime(sums):
    h4,h1=sums["H4"],sums["H1"]
    if (h4["adx14"] or 0)>=23 and (h1["adx14"] or 0)>=20 and h4["trend"]!="neutral":return "trend"
    if (h4["adx14"] or 99)<18 and (h1["adx14"] or 99)<18:return "range"
    return "transition"
def market_score(sums,frames):
    w={"D1":2.5,"H4":3.0,"H1":2.3,"M15":1.2,"M5":0.6}; sc=0
    for k,wt in w.items():
        s=sums[k]; q=0
        q += 1 if s["trend"]=="bullish" else -1 if s["trend"]=="bearish" else 0
        if s["ema200"] is not None:q += .30 if s["close"]>s["ema200"] else -.30
        if s["rsi14"] is not None:q += .20 if s["rsi14"]>=55 else -.20 if s["rsi14"]<=45 else 0
        q += .35*structure(frames[k])
        sc += wt*q
    return sc
def strategy_scores(sym,sums,frames,btc_sums,btc_frames):
    rg=regime(sums); h4,h1,m15,m5=sums["H4"],sums["H1"],sums["M15"],sums["M5"]
    # Trend continuation: trend+ADX+structure+momentum, penalize chasing.
    trend=0.0
    for k,wt in (("D1",1.6),("H4",2.6),("H1",2.0)):
        s=sums[k]; trend += wt*(1 if s["trend"]=="bullish" else -1 if s["trend"]=="bearish" else 0)
        trend += .45*wt*structure(frames[k])
        if (s["adx14"] or 0)>=25: trend += .35*wt*(1 if s["close"]>=s["ema20"] else -1)
    trend += .8*(1 if ret(frames["H1"],6)>0 else -1)
    # Breakout/impulse: price break + volume confirmation + M5/M15 agreement.
    bo=2.2*breakout(frames["M15"],16)+1.2*breakout(frames["M5"],20)
    bo += .8*(1 if m15["close"]>=m15["ema20"] else -1)*min(2,max(.5,m15["volumeRatio"]))
    bo += .5*(1 if m5["close"]>=m5["ema20"] else -1)*min(2,max(.5,m5["volumeRatio"]))
    # Mean reversion: only useful in range/transition; fade extremes toward EMA20.
    mr=0.0
    for s,wt in ((h1,1.0),(m15,1.5),(m5,.8)):
        if s["dist20ATR"]>1.2:mr-=wt
        elif s["dist20ATR"]<-1.2:mr+=wt
        if (s["rsi14"] or 50)>70:mr-=.7*wt
        elif (s["rsi14"] or 50)<30:mr+=.7*wt
    # Relative strength vs BTC: strongest useful for alts.
    rs=0.0
    if sym!="BTC":
        rs1=ret(frames["H1"],12)-ret(btc_frames["H1"],12)
        rs4=ret(frames["H4"],6)-ret(btc_frames["H4"],6)
        rs=3.0*max(-1,min(1,rs1/0.03))+2.0*max(-1,min(1,rs4/0.06))
    # BTC regime is a soft market beta filter, not a hard veto.
    btc_beta=max(-3,min(3,market_score(btc_sums,btc_frames)/5))
    if sym=="BTC": btc_beta=0
    if rg=="trend": final=.58*trend+.25*bo+.08*mr+.09*rs
    elif rg=="range": final=.22*trend+.18*bo+.48*mr+.12*rs
    else: final=.40*trend+.23*bo+.22*mr+.15*rs
    final += .45*btc_beta
    # Anti-chase/exhaustion remains a score adjustment instead of WAIT.
    for s,pen in ((h1,1.0),(m15,.7)):
        if s["dist20ATR"]>1.5:final-=pen
        elif s["dist20ATR"]<-1.5:final+=pen
    return final,{"regime":rg,"trendScore":trend,"breakoutScore":bo,"meanReversionScore":mr,"relativeStrengthScore":rs,"btcBeta":btc_beta}
def choose(sym,sums,frames,btc_sums,btc_frames):
    sc,parts=strategy_scores(sym,sums,frames,btc_sums,btc_frames); side="BUY" if sc>=0 else "SELL"; entry=frames["M5"][-1]["close"]
    a=sums["M15"]["atr14"] or entry*.01; recent=frames["M15"][-12:]
    mult=1.45 if sym in MEMES else 1.30 if sym not in MAJORS else 1.20
    if side=="BUY": sl=min(min(x["low"] for x in recent),entry-mult*a); tp=entry+RR_TARGET*(entry-sl)
    else: sl=max(max(x["high"] for x in recent),entry+mult*a); tp=entry-RR_TARGET*(sl-entry)
    return side,sc,entry,sl,tp,parts
def evaluate(inst,side,entry,sl,tp,cut):
    end=cut+MAX_FORWARD_HOURS*3600000; cursor=cut; mfe=mae=0; seen=0
    while cursor<end:
        nxt=min(end,cursor+24*3600000); cs=[x for x in future_page(inst,cursor,nxt) if cursor<=x["ts"]<nxt]; seen+=len(cs)
        for x in cs:
            if side=="BUY":mfe=max(mfe,x["high"]-entry);mae=max(mae,entry-x["low"]);hs=x["low"]<=sl;ht=x["high"]>=tp
            else:mfe=max(mfe,entry-x["low"]);mae=max(mae,x["high"]-entry);hs=x["high"]>=sl;ht=x["low"]<=tp
            if hs and ht:return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
            if hs:return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
            if ht:return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
        cursor=nxt
    return {"result":"UNRESOLVED_72H","mfe":mfe,"mae":mae,"candles":seen}
def main():
    cut=iso_ms(CUTOFF); btc_frames,btc_sums=load_frames("BTC",cut); res=[]
    for sym in COINS:
        try:
            frames,sums=(btc_frames,btc_sums) if sym=="BTC" else load_frames(sym,cut)
            side,sc,en,sl,tp,parts=choose(sym,sums,frames,btc_sums,btc_frames); out=evaluate(f"{sym}-USDT",side,en,sl,tp,cut)
            res.append({"symbol":sym+"USDT","cutoff":CUTOFF,"source":"OKX historical REST","blind":True,"decision":side,"score":round(sc,3),"entry":en,"sl":sl,"tp1_5R":tp,"model":parts,"snapshot":sums,"outcome":out})
        except Exception as e: res.append({"symbol":sym+"USDT","cutoff":CUTOFF,"error":str(e)})
    usable=[r for r in res if r.get("decision") in ("BUY","SELL")]; resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")]; wins=sum(r["outcome"]["result"]=="TP" for r in resolved); losses=sum(r["outcome"]["result"]=="SL" for r in resolved)
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V4 forced-market strict blind: regime classifier (ADX), multi-timeframe structure/EMA/RSI/ATR/volume, breakout, mean-reversion, relative strength vs BTC, BTC beta, adaptive meme/major stops; no WAIT/LIMIT; TP=1.5R; hidden future up to 72h","universeRequested":len(COINS),"tests":res,"summary":{"requested":len(COINS),"marketTrades":len(usable),"dataErrors":len(res)-len(usable),"resolved":len(resolved),"wins":wins,"losses":losses,"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*wins/len(resolved),2) if resolved else None,"expectancyR":round((wins*RR_TARGET-losses)/len(resolved),3) if resolved else None}}
    with open("data/blind_backtest.json","w") as f: json.dump(payload,f,indent=2)
    print(json.dumps(payload["summary"],indent=2))
if __name__=="__main__":main()
