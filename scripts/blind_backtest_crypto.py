#!/usr/bin/env python3
import json, math, statistics, time, urllib.parse, urllib.request
from datetime import datetime, timezone

OKX_BASE = "https://www.okx.com"
BYBIT_BASE = "https://api.bybit.com"

COINS = "BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC".split()

MAJORS = set("BTC ETH SOL XRP ADA BCH LTC TRX".split())
MEMES = set("SHIB BONK DOGE FLOKI MOODENG PENGU PEPE PNUT POPCAT TRUMP WIF FARTCOIN PUMP".split())
DEFI = set("AAVE CRV JTO JUP LDO LINK ONDO UNI".split())
AI = set("RENDER TAO AIXBT VIRTUAL GRASS".split())
L1_L2 = set("HYPE ALGO APT ARB ATOM AVAX DOT ETC FIL HBAR INJ NEAR OP POL S STX SUI TIA TON WLD IP".split())
NEW_HIGH_BETA = set("KAITO ASTER LIT XPL".split())
BTC_ECO = set("ORDI STX".split())

TF = {"D1":"1Dutc","H4":"4H","H1":"1H","M15":"15m","M5":"5m"}
TF_MS = {"D1":86400000,"H4":14400000,"H1":3600000,"M15":900000,"M5":300000}
BYBIT_TF = {"D1":"D","H4":"240","H1":"60","M15":"15","M5":"5"}

# OLD = same timestamp used by V5; NEW = untouched later timestamp.
CUTOFFS = [
    ("OLD_2026-08-13_12UTC", "2026-08-13T12:00:00Z"),
    ("NEW_2026-08-14_08UTC", "2026-08-14T08:00:00Z"),
]
MAX_FORWARD_HOURS = 72


def iso_ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def ms_iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def http(url):
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"breakout-blind-v6"})
    for n in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            if n == 3:
                raise
            time.sleep(0.7 * (n + 1))


def fv(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def rows_okx(rs):
    out = []
    for r in rs:
        ts = int(r[0])
        out.append({"ts":ts,"datetime":ms_iso(ts),"open":fv(r[1]),"high":fv(r[2]),"low":fv(r[3]),"close":fv(r[4]),"volume":fv(r[5])})
    return sorted([x for x in out if x["close"] is not None], key=lambda x:x["ts"])


def rows_bybit(rs):
    out = []
    for r in rs:
        ts = int(r[0])
        out.append({"ts":ts,"datetime":ms_iso(ts),"open":fv(r[1]),"high":fv(r[2]),"low":fv(r[3]),"close":fv(r[4]),"volume":fv(r[5])})
    return sorted([x for x in out if x["close"] is not None], key=lambda x:x["ts"])


def okx_hist(inst, bar, cut, limit=300):
    u = f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={bar}&after={cut}&limit={limit}"
    return rows_okx(http(u).get("data") or [])


def okx_future_page(inst, before, after):
    u = f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={before}&after={after}&limit=300"
    return rows_okx(http(u).get("data") or [])


def bybit_hist(symbol, interval, cut, limit=1000):
    # Kline endpoint returns data <= end timestamp, newest first.
    u = f"{BYBIT_BASE}/v5/market/kline?category=linear&symbol={urllib.parse.quote(symbol+'USDT')}&interval={interval}&end={cut}&limit={limit}"
    d = http(u)
    if d.get("retCode") != 0:
        return []
    return rows_bybit(((d.get("result") or {}).get("list")) or [])


def bybit_future(symbol, start, end):
    u = f"{BYBIT_BASE}/v5/market/kline?category=linear&symbol={urllib.parse.quote(symbol+'USDT')}&interval=5&start={start}&end={end}&limit=1000"
    d = http(u)
    if d.get("retCode") != 0:
        return []
    return rows_bybit(((d.get("result") or {}).get("list")) or [])


def ema(v, p):
    if len(v) < p: return None
    x = sum(v[:p]) / p
    k = 2 / (p + 1)
    for z in v[p:]: x = z * k + x * (1 - k)
    return x


def rsi(v, p=14):
    if len(v) <= p: return None
    g = l = 0.0
    for i in range(1, p + 1):
        d = v[i] - v[i-1]; g += max(d,0); l += max(-d,0)
    g /= p; l /= p
    for i in range(p + 1, len(v)):
        d = v[i] - v[i-1]
        g = (g*(p-1)+max(d,0))/p; l = (l*(p-1)+max(-d,0))/p
    return 100.0 if l == 0 else 100 - 100/(1 + g/l)


def atr(c, p=14):
    if len(c) <= p: return None
    tr = []
    for i in range(1, len(c)):
        cur, prev = c[i], c[i-1]
        tr.append(max(cur["high"]-cur["low"], abs(cur["high"]-prev["close"]), abs(cur["low"]-prev["close"])))
    x = sum(tr[:p])/p
    for z in tr[p:]: x = (x*(p-1)+z)/p
    return x


def adx(c, p=14):
    if len(c) < p*2+2: return None
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
    for z in dx[p:]:a=(a*(p-1)+z)/p
    return a


def ret(c, n):
    if len(c) <= n or c[-n-1]["close"] == 0: return 0.0
    return c[-1]["close"] / c[-n-1]["close"] - 1


def structure(c, n=20):
    x=c[-n:]; m=max(2,n//2); a=x[:m]; b=x[m:]
    hh=max(z["high"] for z in b)>max(z["high"] for z in a); hl=min(z["low"] for z in b)>min(z["low"] for z in a)
    lh=max(z["high"] for z in b)<max(z["high"] for z in a); ll=min(z["low"] for z in b)<min(z["low"] for z in a)
    return 1 if hh and hl else -1 if lh and ll else 0


def breakout(c, n=20):
    if len(c)<n+1:return 0
    prev=c[-n-1:-1]; last=c[-1]
    if last["close"]>max(x["high"] for x in prev):return 1
    if last["close"]<min(x["low"] for x in prev):return -1
    return 0


def sweep(c, n=16):
    if len(c) < n + 2: return 0
    prev = c[-n-1:-1]; last = c[-1]
    ph = max(x["high"] for x in prev); pl = min(x["low"] for x in prev)
    # +1 = sweep lows and reclaim; -1 = sweep highs and reject.
    if last["low"] < pl and last["close"] > pl: return 1
    if last["high"] > ph and last["close"] < ph: return -1
    return 0


def range_position(c, n=48):
    x=c[-n:]; hi=max(z["high"] for z in x); lo=min(z["low"] for z in x); cl=x[-1]["close"]
    return 0.5 if hi<=lo else (cl-lo)/(hi-lo)


def vwap(c, n=96):
    x=c[-n:]; num=den=0.0
    for z in x:
        vol=z.get("volume") or 0.0; typ=(z["high"]+z["low"]+z["close"])/3
        num += typ*vol; den += vol
    return num/den if den else None


def summ(c):
    vals=[x["close"] for x in c]; cl=vals[-1]
    e20,e50,e200=ema(vals,20),ema(vals,50),ema(vals,200); rr=rsi(vals); aa=atr(c); ax=adx(c)
    trend="neutral"
    if e20 is not None and e50 is not None:
        if cl>e20>e50:trend="bullish"
        elif cl<e20<e50:trend="bearish"
    vv=[x["volume"] or 0 for x in c[-21:]]; base=sum(vv[:-1])/max(1,len(vv)-1); vr=vv[-1]/base if base else 1
    dist=(cl-e20)/aa if e20 is not None and aa else 0
    atrpct=(aa/cl) if aa and cl else 0
    return {"close":cl,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rr,"atr14":aa,"adx14":ax,"trend":trend,"dist20ATR":dist,"volumeRatio":vr,"atrPct":atrpct}


def load_frames(sym, cut):
    # Preserve OKX as primary for comparability; use Bybit linear only when OKX lacks sufficient history.
    inst=f"{sym}-USDT"; frames={}; sums={}; ok=True
    for k,b in TF.items():
        c=[x for x in okx_hist(inst,b,cut) if x["ts"]+TF_MS[k]<=cut]
        if len(c)<60:
            ok=False; break
        frames[k]=c; sums[k]=summ(c)
    if ok:
        return "OKX spot", frames, sums
    frames={}; sums={}
    for k in TF:
        c=[x for x in bybit_hist(sym,BYBIT_TF[k],cut) if x["ts"]+TF_MS[k]<=cut]
        if len(c)<60: raise RuntimeError(f"{k} insufficient on OKX/Bybit:{len(c)}")
        frames[k]=c; sums[k]=summ(c)
    return "Bybit linear fallback", frames, sums


def profile(sym):
    if sym in MEMES:return {"type":"meme","stopBase":1.50,"rrTrend":1.55,"rrTransition":1.30,"rrRange":1.15,"rsWeight":0.14}
    if sym in NEW_HIGH_BETA:return {"type":"new_high_beta","stopBase":1.45,"rrTrend":1.55,"rrTransition":1.30,"rrRange":1.15,"rsWeight":0.13}
    if sym in AI:return {"type":"ai_high_beta","stopBase":1.40,"rrTrend":1.60,"rrTransition":1.35,"rrRange":1.20,"rsWeight":0.13}
    if sym in DEFI:return {"type":"defi","stopBase":1.30,"rrTrend":1.65,"rrTransition":1.35,"rrRange":1.20,"rsWeight":0.10}
    if sym in L1_L2:return {"type":"l1_l2","stopBase":1.30,"rrTrend":1.65,"rrTransition":1.35,"rrRange":1.20,"rsWeight":0.10}
    if sym in MAJORS:return {"type":"major","stopBase":1.18,"rrTrend":1.70,"rrTransition":1.40,"rrRange":1.25,"rsWeight":0.07}
    return {"type":"alt","stopBase":1.33,"rrTrend":1.60,"rrTransition":1.35,"rrRange":1.20,"rsWeight":0.10}


def regime(sums):
    h4,h1=sums["H4"],sums["H1"]
    aligned=h4["trend"]==h1["trend"] and h4["trend"]!="neutral"
    if aligned and (h4["adx14"] or 0)>=20 and (h1["adx14"] or 0)>=18:return "trend"
    if (h4["adx14"] or 99)<18 and (h1["adx14"] or 99)<18:return "range"
    return "transition"


def directional_score(sym,sums,frames,btc_frames,btc_sums):
    p=profile(sym); rg=regime(sums)
    d1,h4,h1,m15,m5=[sums[k] for k in ("D1","H4","H1","M15","M5")]

    # HTF bias: structure is primary; moving averages are filters, RSI is speed.
    htf=0.0
    for k,wt in (("D1",2.0),("H4",3.2),("H1",2.5)):
        s=sums[k]; q=0.0
        q += 1.0 if s["trend"]=="bullish" else -1.0 if s["trend"]=="bearish" else 0
        q += 0.55*structure(frames[k])
        if s["ema200"] is not None:q += 0.22 if s["close"]>s["ema200"] else -0.22
        if s["rsi14"] is not None:q += 0.15 if s["rsi14"]>=55 else -0.15 if s["rsi14"]<=45 else 0
        htf += wt*q

    # Execution: M15 controls setup, M5 trigger. Add liquidity sweep and VWAP location.
    ltf=0.0
    for k,wt in (("M15",1.8),("M5",1.0)):
        s=sums[k]; q=0.0
        q += 1.0 if s["trend"]=="bullish" else -1.0 if s["trend"]=="bearish" else 0
        q += 0.40*structure(frames[k])
        q += 0.35*breakout(frames[k],16 if k=="M15" else 20)
        q += 0.55*sweep(frames[k],16 if k=="M15" else 20)
        direction=1 if s["close"]>=s["ema20"] else -1
        q += 0.18*direction*min(2.0,max(0.4,s["volumeRatio"]))
        ltf += wt*q

    mvwap=vwap(frames["M15"],96)
    if mvwap:
        ltf += 0.35 if m15["close"]>mvwap else -0.35

    # Range location only matters in range; in trend, being near edge is not automatically reversal.
    pos=range_position(frames["H1"],48)
    meanrev=0.0
    if rg=="range":
        if pos>=0.80:meanrev-=1.6
        elif pos<=0.20:meanrev+=1.6
        for s,wt in ((h1,0.7),(m15,1.1),(m5,0.6)):
            if s["dist20ATR"]>1.3:meanrev-=wt
            elif s["dist20ATR"]<-1.3:meanrev+=wt
            if (s["rsi14"] or 50)>72:meanrev-=0.45*wt
            elif (s["rsi14"] or 50)<28:meanrev+=0.45*wt

    # Relative strength to BTC is more important for high-beta alts than majors.
    rs=0.0
    if sym!="BTC":
        rs1=ret(frames["H1"],12)-ret(btc_frames["H1"],12)
        rs4=ret(frames["H4"],6)-ret(btc_frames["H4"],6)
        rs=max(-2,min(2,rs1/0.025))+max(-1.5,min(1.5,rs4/0.05))

    # BTC market beta is a soft filter.
    btc_bias=0.0
    if sym!="BTC":
        b=btc_sums
        btc_bias += 1 if b["H4"]["trend"]=="bullish" else -1 if b["H4"]["trend"]=="bearish" else 0
        btc_bias += 0.7 if b["H1"]["trend"]=="bullish" else -0.7 if b["H1"]["trend"]=="bearish" else 0

    # Post-displacement guard: huge volume + stretched price often mean poor MARKET continuation entry.
    chase=0.0
    for s,wt in ((h1,0.8),(m15,1.0),(m5,0.45)):
        if s["dist20ATR"]>1.5:chase-=wt
        elif s["dist20ATR"]<-1.5:chase+=wt
    if m15["volumeRatio"]>=2.5 and abs(m15["dist20ATR"])>=1.4:
        chase += -1.0 if m15["dist20ATR"]>0 else 1.0
    if m5["volumeRatio"]>=3.0 and abs(m5["dist20ATR"])>=1.5:
        chase += -0.6 if m5["dist20ATR"]>0 else 0.6

    if rg=="trend":final=0.65*htf+0.30*ltf+p["rsWeight"]*rs+0.04*btc_bias+chase
    elif rg=="range":final=0.24*htf+0.18*ltf+0.50*meanrev+p["rsWeight"]*rs+0.05*btc_bias+0.5*chase
    else:final=0.48*htf+0.34*ltf+p["rsWeight"]*rs+0.07*btc_bias+0.8*chase

    # Forced-market fallback when score is near zero: use regime-specific tie breaker instead of random sign.
    if abs(final)<0.55:
        if rg=="range":
            final = 0.56 if pos<=0.5 else -0.56
        else:
            core=(1 if h4["trend"]=="bullish" else -1 if h4["trend"]=="bearish" else 0)+(0.6 if h1["trend"]=="bullish" else -0.6 if h1["trend"]=="bearish" else 0)
            final = 0.56 if core>=0 else -0.56

    return final,{"profile":p["type"],"regime":rg,"htfScore":htf,"ltfScore":ltf,"meanReversionScore":meanrev,"relativeStrengthScore":rs,"btcBias":btc_bias,"chaseAdjustment":chase,"rangePositionH1":pos,"m15Sweep":sweep(frames["M15"]),"m5Sweep":sweep(frames["M5"]),"m15VWAP":mvwap}


def choose(sym,sums,frames,btc_frames,btc_sums):
    sc,model=directional_score(sym,sums,frames,btc_frames,btc_sums); side="BUY" if sc>=0 else "SELL"; entry=frames["M5"][-1]["close"]
    p=profile(sym); rg=model["regime"]; a=sums["M15"]["atr14"] or entry*0.01; recent=frames["M15"][-12:]
    # Volatility-aware stop widening. Structure first, ATR is a minimum floor.
    atrpct=sums["M15"].get("atrPct") or 0
    vol_extra=0.12 if atrpct>0.012 else 0.06 if atrpct>0.007 else 0
    mult=p["stopBase"]+vol_extra
    if side=="BUY":sl=min(min(x["low"] for x in recent),entry-mult*a)
    else:sl=max(max(x["high"] for x in recent),entry+mult*a)
    risk=abs(entry-sl)
    rr=p["rrTrend"] if rg=="trend" else p["rrRange"] if rg=="range" else p["rrTransition"]
    # If entry is post-displacement/chasing, shorten target rather than pretending 2R is realistic.
    if abs(model["chaseAdjustment"])>=1.2:rr=max(1.05,rr-0.15)
    # Strong score earns a slightly larger target; weak forced-market setup uses realistic target.
    if abs(sc)>=5.0:rr=min(1.85,rr+0.10)
    elif abs(sc)<1.2:rr=max(1.05,rr-0.10)
    tp=entry+rr*risk if side=="BUY" else entry-rr*risk
    return side,sc,entry,sl,tp,rr,model


def evaluate(source,sym,side,entry,sl,tp,cut):
    end=cut+MAX_FORWARD_HOURS*3600000; mfe=mae=0.0; seen=0
    if source.startswith("Bybit"):
        cs=bybit_future(sym,cut,end)
        pages=[cs]
    else:
        pages=[]; cursor=cut
        while cursor<end:
            nxt=min(end,cursor+24*3600000); pages.append([x for x in okx_future_page(f"{sym}-USDT",cursor,nxt) if cursor<=x["ts"]<nxt]); cursor=nxt
    for cs in pages:
        seen+=len(cs)
        for x in cs:
            if side=="BUY":mfe=max(mfe,x["high"]-entry);mae=max(mae,entry-x["low"]);hs=x["low"]<=sl;ht=x["high"]>=tp
            else:mfe=max(mfe,entry-x["low"]);mae=max(mae,x["high"]-entry);hs=x["high"]>=sl;ht=x["low"]<=tp
            if hs and ht:return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
            if hs:return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
            if ht:return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
    return {"result":"UNRESOLVED_72H","mfe":mfe,"mae":mae,"candles":seen}


def run_cutoff(label,cutoff):
    cut=iso_ms(cutoff); btc_source,btc_frames,btc_sums=load_frames("BTC",cut); results=[]
    for sym in COINS:
        try:
            source,frames,sums=(btc_source,btc_frames,btc_sums) if sym=="BTC" else load_frames(sym,cut)
            side,sc,en,sl,tp,rr,model=choose(sym,sums,frames,btc_frames,btc_sums); out=evaluate(source,sym,side,en,sl,tp,cut)
            results.append({"symbol":sym+"USDT","cutoff":cutoff,"source":source,"blind":True,"decision":side,"score":round(sc,3),"entry":en,"sl":sl,"tp":tp,"plannedRR":round(rr,3),"model":model,"snapshot":sums,"outcome":out})
        except Exception as e:
            results.append({"symbol":sym+"USDT","cutoff":cutoff,"error":str(e)})
    usable=[r for r in results if r.get("decision") in ("BUY","SELL")]; resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")]
    wins=[r for r in resolved if r["outcome"]["result"]=="TP"]; losses=[r for r in resolved if r["outcome"]["result"]=="SL"]
    total_r=sum(r["plannedRR"] if r["outcome"]["result"]=="TP" else -1 for r in resolved)
    summary={"label":label,"cutoff":cutoff,"requested":len(COINS),"marketTrades":len(usable),"dataErrors":len(results)-len(usable),"resolved":len(resolved),"wins":len(wins),"losses":len(losses),"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*len(wins)/len(resolved),2) if resolved else None,"avgPlannedRR":round(sum(r["plannedRR"] for r in resolved)/len(resolved),3) if resolved else None,"expectancyR":round(total_r/len(resolved),3) if resolved else None}
    return {"summary":summary,"tests":results}


def main():
    samples={};
    for label,cutoff in CUTOFFS:samples[label]=run_cutoff(label,cutoff)
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V6 forced-market strict blind: per-coin profiles (major/L1-DeFi/AI/meme/new-high-beta), regime-first D1/H4/H1 structure+EMA50/200+RSI, M15/M5 structure+breakout+liquidity-sweep+volume+VWAP, BTC relative strength, post-displacement guard, volatility-aware structure SL, adaptive TP/RR; OKX primary + Bybit linear fallback; future hidden until decision; max 72h","samples":samples}
    with open("data/blind_backtest.json","w",encoding="utf-8") as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v["summary"] for k,v in samples.items()},indent=2))

if __name__=="__main__":main()
