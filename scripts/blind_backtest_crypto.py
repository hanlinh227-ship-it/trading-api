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

TF = {"D1":"1Dutc","H4":"4H","H1":"1H","M15":"15m","M5":"5m"}
TF_MS = {"D1":86400000,"H4":14400000,"H1":3600000,"M15":900000,"M5":300000}
BYBIT_TF = {"D1":"D","H4":"240","H1":"60","M15":"15","M5":"5"}

# OLD is a regression/in-sample comparison because its outcome has already been inspected.
# NEW is a fresh cutoff not used by V3-V6 when V7 rules were written.
CUTOFFS = [
    ("OLD_REGRESSION_2026-08-13_12UTC", "2026-08-13T12:00:00Z", False),
    ("NEW_BLIND_2026-08-14_00UTC", "2026-08-14T00:00:00Z", True),
]
MAX_FORWARD_HOURS = 72


def iso_ms(s): return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
def ms_iso(ms): return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")

def http(url):
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"breakout-blind-v7"})
    for n in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r: return json.loads(r.read().decode())
        except Exception:
            if n == 3: raise
            time.sleep(0.65 * (n + 1))

def fv(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except Exception: return None

def rows_okx(rs):
    out=[]
    for r in rs:
        ts=int(r[0]); out.append({"ts":ts,"datetime":ms_iso(ts),"open":fv(r[1]),"high":fv(r[2]),"low":fv(r[3]),"close":fv(r[4]),"volume":fv(r[5])})
    return sorted([x for x in out if x["close"] is not None], key=lambda x:x["ts"])

def rows_bybit(rs):
    out=[]
    for r in rs:
        ts=int(r[0]); out.append({"ts":ts,"datetime":ms_iso(ts),"open":fv(r[1]),"high":fv(r[2]),"low":fv(r[3]),"close":fv(r[4]),"volume":fv(r[5])})
    return sorted([x for x in out if x["close"] is not None], key=lambda x:x["ts"])

def okx_hist(inst,bar,cut,limit=300):
    u=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={bar}&after={cut}&limit={limit}"
    return rows_okx(http(u).get("data") or [])

def okx_future(inst,start,end):
    out=[]; cursor=start
    while cursor<end:
        nxt=min(end,cursor+24*3600000)
        u=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={cursor}&after={nxt}&limit=300"
        try: data=rows_okx(http(u).get("data") or [])
        except Exception: data=[]
        out.extend([x for x in data if cursor<=x["ts"]<nxt]); cursor=nxt
    return sorted({x["ts"]:x for x in out}.values(),key=lambda x:x["ts"])

def bybit_hist(sym,interval,cut,limit=1000):
    u=f"{BYBIT_BASE}/v5/market/kline?category=linear&symbol={urllib.parse.quote(sym+'USDT')}&interval={interval}&end={cut}&limit={limit}"
    d=http(u)
    if d.get("retCode")!=0:return []
    return rows_bybit(((d.get("result") or {}).get("list")) or [])

def bybit_future(sym,start,end):
    u=f"{BYBIT_BASE}/v5/market/kline?category=linear&symbol={urllib.parse.quote(sym+'USDT')}&interval=5&start={start}&end={end}&limit=1000"
    d=http(u)
    if d.get("retCode")!=0:return []
    return rows_bybit(((d.get("result") or {}).get("list")) or [])

def ema(v,p):
    if len(v)<p:return None
    x=sum(v[:p])/p; k=2/(p+1)
    for z in v[p:]:x=z*k+x*(1-k)
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
        cur,pr=c[i],c[i-1]; tr.append(max(cur["high"]-cur["low"],abs(cur["high"]-pr["close"]),abs(cur["low"]-pr["close"])))
    x=sum(tr[:p])/p
    for z in tr[p:]:x=(x*(p-1)+z)/p
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
    for z in dx[p:]:a=(a*(p-1)+z)/p
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

def sweep(c,n=16):
    if len(c)<n+2:return 0
    prev=c[-n-1:-1]; last=c[-1]; ph=max(x["high"] for x in prev); pl=min(x["low"] for x in prev)
    if last["low"]<pl and last["close"]>pl:return 1
    if last["high"]>ph and last["close"]<ph:return -1
    return 0

def range_position(c,n=48):
    x=c[-n:]; hi=max(z["high"] for z in x); lo=min(z["low"] for z in x); cl=x[-1]["close"]
    return 0.5 if hi<=lo else (cl-lo)/(hi-lo)

def vwap(c,n=96):
    x=c[-n:]; num=den=0.0
    for z in x:
        vol=z.get("volume") or 0; typ=(z["high"]+z["low"]+z["close"])/3; num+=typ*vol; den+=vol
    return num/den if den else None

def pivot_levels(c,left=2,right=2,lookback=80):
    x=c[-lookback:]; highs=[]; lows=[]
    for i in range(left,len(x)-right):
        h=x[i]["high"]; l=x[i]["low"]
        if h>=max(z["high"] for z in x[i-left:i+right+1]):highs.append(h)
        if l<=min(z["low"] for z in x[i-left:i+right+1]):lows.append(l)
    return highs,lows

def summ(c):
    vals=[x["close"] for x in c]; cl=vals[-1]; e20,e50,e200=ema(vals,20),ema(vals,50),ema(vals,200); rr=rsi(vals); aa=atr(c); ax=adx(c)
    trend="neutral"
    if e20 is not None and e50 is not None:
        if cl>e20>e50:trend="bullish"
        elif cl<e20<e50:trend="bearish"
    vv=[x["volume"] or 0 for x in c[-21:]]; base=sum(vv[:-1])/max(1,len(vv)-1); vr=vv[-1]/base if base else 1
    dist=(cl-e20)/aa if e20 is not None and aa else 0
    return {"close":cl,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rr,"atr14":aa,"adx14":ax,"trend":trend,"dist20ATR":dist,"volumeRatio":vr,"atrPct":aa/cl if aa and cl else 0}

def load_frames(sym,cut):
    attempts=[("OKX spot",f"{sym}-USDT","okx"),("OKX USDT-SWAP",f"{sym}-USDT-SWAP","okx")]
    for name,inst,venue in attempts:
        try:
            frames={}; sums={}; ok=True
            for k,b in TF.items():
                c=[x for x in okx_hist(inst,b,cut) if x["ts"]+TF_MS[k]<=cut]
                if len(c)<60:ok=False; break
                frames[k]=c; sums[k]=summ(c)
            if ok:return name,inst,frames,sums
        except Exception:pass
    try:
        frames={}; sums={}
        for k in TF:
            c=[x for x in bybit_hist(sym,BYBIT_TF[k],cut) if x["ts"]+TF_MS[k]<=cut]
            if len(c)<60:raise RuntimeError(f"{k} bybit insufficient:{len(c)}")
            frames[k]=c; sums[k]=summ(c)
        return "Bybit linear",sym+"USDT",frames,sums
    except Exception as e:raise RuntimeError(f"no stable history source: {e}")

def profile(sym):
    if sym in MEMES:return {"type":"meme","stopBuf":0.24,"rsWeight":0.15}
    if sym in NEW_HIGH_BETA:return {"type":"new_high_beta","stopBuf":0.22,"rsWeight":0.14}
    if sym in AI:return {"type":"ai_high_beta","stopBuf":0.20,"rsWeight":0.14}
    if sym in DEFI:return {"type":"defi","stopBuf":0.16,"rsWeight":0.10}
    if sym in L1_L2:return {"type":"l1_l2","stopBuf":0.17,"rsWeight":0.11}
    if sym in MAJORS:return {"type":"major","stopBuf":0.12,"rsWeight":0.07}
    return {"type":"alt","stopBuf":0.18,"rsWeight":0.11}

def regime(sums):
    h4,h1=sums["H4"],sums["H1"]; aligned=h4["trend"]==h1["trend"] and h4["trend"]!="neutral"
    if aligned and (h4["adx14"] or 0)>=20 and (h1["adx14"] or 0)>=18:return "trend"
    if (h4["adx14"] or 99)<18 and (h1["adx14"] or 99)<18:return "range"
    return "transition"

def directional_score(sym,sums,frames,btc_frames,btc_sums):
    p=profile(sym); rg=regime(sums); h4,h1,m15,m5=[sums[k] for k in ("H4","H1","M15","M5")]
    htf=0.0
    for k,wt in (("D1",1.9),("H4",3.25),("H1",2.65)):
        s=sums[k]; q=(1 if s["trend"]=="bullish" else -1 if s["trend"]=="bearish" else 0)+0.60*structure(frames[k])
        if s["ema200"] is not None:q+=0.20 if s["close"]>s["ema200"] else -0.20
        if s["rsi14"] is not None:q+=0.12 if s["rsi14"]>=55 else -0.12 if s["rsi14"]<=45 else 0
        htf+=wt*q
    ltf=0.0
    for k,wt in (("M15",1.9),("M5",1.15)):
        s=sums[k]; q=(1 if s["trend"]=="bullish" else -1 if s["trend"]=="bearish" else 0)
        q+=0.45*structure(frames[k])+0.35*breakout(frames[k],16 if k=="M15" else 20)+0.65*sweep(frames[k],16 if k=="M15" else 20)
        q+=0.16*(1 if s["close"]>=s["ema20"] else -1)*min(2.0,max(0.4,s["volumeRatio"]))
        ltf+=wt*q
    mv=vwap(frames["M15"],96)
    if mv:ltf+=0.30 if m15["close"]>mv else -0.30
    pos=range_position(frames["H1"],48); mr=0.0
    if rg=="range":
        if pos>=0.82:mr-=1.8
        elif pos<=0.18:mr+=1.8
        for s,wt in ((h1,0.8),(m15,1.2),(m5,0.7)):
            if s["dist20ATR"]>1.25:mr-=wt
            elif s["dist20ATR"]<-1.25:mr+=wt
            if (s["rsi14"] or 50)>72:mr-=0.50*wt
            elif (s["rsi14"] or 50)<28:mr+=0.50*wt
    rs=0.0
    if sym!="BTC":
        rs1=ret(frames["H1"],12)-ret(btc_frames["H1"],12); rs4=ret(frames["H4"],6)-ret(btc_frames["H4"],6)
        rs=max(-2,min(2,rs1/0.025))+max(-1.5,min(1.5,rs4/0.05))
    btc_bias=0.0
    if sym!="BTC":
        btc_bias+=(1 if btc_sums["H4"]["trend"]=="bullish" else -1 if btc_sums["H4"]["trend"]=="bearish" else 0)
        btc_bias+=(0.7 if btc_sums["H1"]["trend"]=="bullish" else -0.7 if btc_sums["H1"]["trend"]=="bearish" else 0)
    chase=0.0
    for s,wt in ((h1,0.75),(m15,1.0),(m5,0.45)):
        if s["dist20ATR"]>1.45:chase-=wt
        elif s["dist20ATR"]<-1.45:chase+=wt
    if m15["volumeRatio"]>=2.2 and abs(m15["dist20ATR"])>=1.25:chase+=(-1.15 if m15["dist20ATR"]>0 else 1.15)
    if m5["volumeRatio"]>=2.8 and abs(m5["dist20ATR"])>=1.35:chase+=(-0.65 if m5["dist20ATR"]>0 else 0.65)
    # Strong rejection candle: favor reclaim/reject direction in forced-market mode.
    last=frames["M5"][-1]; rng=max(1e-12,last["high"]-last["low"]); closepos=(last["close"]-last["low"])/rng
    rejection=0.0
    if closepos>0.78 and last["low"]<min(x["low"] for x in frames["M5"][-8:-1]):rejection=0.8
    elif closepos<0.22 and last["high"]>max(x["high"] for x in frames["M5"][-8:-1]):rejection=-0.8
    if rg=="trend":final=0.66*htf+0.31*ltf+p["rsWeight"]*rs+0.04*btc_bias+chase+rejection
    elif rg=="range":final=0.22*htf+0.18*ltf+0.52*mr+p["rsWeight"]*rs+0.05*btc_bias+0.45*chase+rejection
    else:final=0.47*htf+0.36*ltf+p["rsWeight"]*rs+0.07*btc_bias+0.82*chase+rejection
    if abs(final)<0.50:
        if rg=="range":final=0.51 if pos<=0.5 else -0.51
        else:
            core=(1 if h4["trend"]=="bullish" else -1 if h4["trend"]=="bearish" else 0)+(0.7 if h1["trend"]=="bullish" else -0.7 if h1["trend"]=="bearish" else 0)
            final=0.51 if core>=0 else -0.51
    return final,{"profile":p["type"],"regime":rg,"htfScore":htf,"ltfScore":ltf,"meanReversionScore":mr,"relativeStrengthScore":rs,"btcBias":btc_bias,"chaseAdjustment":chase,"rejectionScore":rejection,"rangePositionH1":pos,"m15Sweep":sweep(frames["M15"]),"m5Sweep":sweep(frames["M5"]),"m15VWAP":mv}

def local_atr(c,i,p=14):
    if i<p+1:return None
    return atr(c[max(0,i-p-5):i+1],p)

def calibrate_barriers(m15,side):
    # Per-coin, per-direction walk-back calibration uses ONLY candles before cutoff.
    stops=[0.8,1.0,1.2,1.4,1.6,1.9,2.2]; tps=[0.6,0.8,1.0,1.2,1.5,1.8,2.2]
    candidates=[]
    for sm in stops:
        for tm in tps:
            rr=tm/sm
            if rr<0.70 or rr>2.20:continue
            w=l=0
            for i in range(65,len(m15)-10,3):
                hist=m15[:i+1]; vals=[x["close"] for x in hist]; e20=ema(vals,20); e50=ema(vals,50); rrsi=rsi(vals); a=local_atr(m15,i)
                if not a or not e20 or not e50:continue
                cl=m15[i]["close"]
                aligned=(cl>=e20 and (rrsi or 50)>=48) if side=="BUY" else (cl<=e20 and (rrsi or 50)<=52)
                if not aligned:continue
                sl=cl-sm*a if side=="BUY" else cl+sm*a; tp=cl+tm*a if side=="BUY" else cl-tm*a
                result=None
                for z in m15[i+1:i+9]:
                    hs=z["low"]<=sl if side=="BUY" else z["high"]>=sl
                    ht=z["high"]>=tp if side=="BUY" else z["low"]<=tp
                    if hs and ht:result="SL"; break
                    if hs:result="SL"; break
                    if ht:result="TP"; break
                if result=="TP":w+=1
                elif result=="SL":l+=1
            n=w+l
            if n>=18:
                wr=w/n; exp=(w*rr-l)/n
                if exp>=0.02:candidates.append((wr,exp,n,sm,tm,rr))
    if candidates:
        candidates.sort(key=lambda x:(x[0],x[1],x[2]),reverse=True); x=candidates[0]
        return {"stopATR":x[3],"tpATR":x[4],"rr":x[5],"histWinRate":x[0],"histExpectancyR":x[1],"samples":x[2],"mode":"positive_expectancy_max_win"}
    # Conservative fallback: not identical across categories later because structure still controls stop/TP.
    return {"stopATR":1.35,"tpATR":1.10,"rr":1.10/1.35,"histWinRate":None,"histExpectancyR":None,"samples":0,"mode":"fallback"}

def choose_target_level(side,entry,desired,m15,h1):
    levels=[]
    for c in (m15,h1):
        highs,lows=pivot_levels(c,2,2,80)
        levels.extend(highs if side=="BUY" else lows)
    if side=="BUY":
        valid=sorted(x for x in levels if x>entry+0.45*desired)
        near=[x for x in valid if x<=entry+1.35*desired]
        return near[0] if near else entry+desired
    valid=sorted((x for x in levels if x<entry-0.45*desired),reverse=True)
    near=[x for x in valid if x>=entry-1.35*desired]
    return near[0] if near else entry-desired

def choose(sym,sums,frames,btc_frames,btc_sums):
    sc,model=directional_score(sym,sums,frames,btc_frames,btc_sums); side="BUY" if sc>=0 else "SELL"; entry=frames["M5"][-1]["close"]
    p=profile(sym); a=sums["M15"]["atr14"] or entry*0.01; cal=calibrate_barriers(frames["M15"],side)
    highs,lows=pivot_levels(frames["M15"],2,2,64); buf=p["stopBuf"]*a
    if side=="BUY":
        piv=sorted([x for x in lows if x<entry],reverse=True); structural=(entry-(piv[0]-buf)) if piv else 1.2*a
    else:
        piv=sorted([x for x in highs if x>entry]); structural=((piv[0]+buf)-entry) if piv else 1.2*a
    # Stop is invalidation-aware but not absurdly wide. Historical adverse-excursion floor is coin-specific.
    risk=max(cal["stopATR"]*a,structural)
    max_mult=2.35 if p["type"] in ("meme","new_high_beta","ai_high_beta") else 2.10
    risk=min(risk,max_mult*a)
    sl=entry-risk if side=="BUY" else entry+risk
    desired=max(cal["tpATR"]*a,0.70*risk)
    # Strong clean trend may justify farther objective; exhausted/chased entry gets a nearer objective.
    if model["regime"]=="trend" and abs(sc)>=4.5 and abs(model["chaseAdjustment"])<1.0:desired*=1.20
    if abs(model["chaseAdjustment"])>=1.5:desired*=0.88
    tp=choose_target_level(side,entry,desired,frames["M15"],frames["H1"])
    reward=abs(tp-entry)
    # Reasonable bounds: avoid microscopic targets and fantasy targets while keeping TP fully adaptive.
    min_rr=0.68 if p["type"] in ("meme","new_high_beta") else 0.72
    max_rr=2.20 if model["regime"]=="trend" else 1.75
    rr=reward/risk if risk else 0
    if rr<min_rr:
        reward=min_rr*risk; tp=entry+reward if side=="BUY" else entry-reward; rr=min_rr
    elif rr>max_rr:
        reward=max_rr*risk; tp=entry+reward if side=="BUY" else entry-reward; rr=max_rr
    return side,sc,entry,sl,tp,rr,cal,model

def evaluate(source,inst,sym,side,entry,sl,tp,cut):
    end=cut+MAX_FORWARD_HOURS*3600000; mfe=mae=0.0; seen=0
    try:cs=bybit_future(sym,cut,end) if source.startswith("Bybit") else okx_future(inst,cut,end)
    except Exception:cs=[]
    for x in cs:
        seen+=1
        if side=="BUY":mfe=max(mfe,x["high"]-entry);mae=max(mae,entry-x["low"]);hs=x["low"]<=sl;ht=x["high"]>=tp
        else:mfe=max(mfe,entry-x["low"]);mae=max(mae,x["high"]-entry);hs=x["high"]>=sl;ht=x["low"]<=tp
        if hs and ht:return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
        if hs:return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
        if ht:return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
    return {"result":"UNRESOLVED_72H","mfe":mfe,"mae":mae,"candles":seen}

def run_cutoff(label,cutoff,is_blind):
    cut=iso_ms(cutoff); btc_source,btc_inst,btc_frames,btc_sums=load_frames("BTC",cut); results=[]
    for sym in COINS:
        try:
            source,inst,frames,sums=(btc_source,btc_inst,btc_frames,btc_sums) if sym=="BTC" else load_frames(sym,cut)
            side,sc,en,sl,tp,rr,cal,model=choose(sym,sums,frames,btc_frames,btc_sums); out=evaluate(source,inst,sym,side,en,sl,tp,cut)
            results.append({"symbol":sym+"USDT","cutoff":cutoff,"source":source,"blind":is_blind,"decision":side,"score":round(sc,3),"entry":en,"sl":sl,"tp":tp,"plannedRR":round(rr,3),"barrierCalibration":cal,"model":model,"snapshot":sums,"outcome":out})
        except Exception as e:results.append({"symbol":sym+"USDT","cutoff":cutoff,"error":str(e)})
    usable=[r for r in results if r.get("decision") in ("BUY","SELL")]; resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")]
    wins=[r for r in resolved if r["outcome"]["result"]=="TP"]; losses=[r for r in resolved if r["outcome"]["result"]=="SL"]
    total_r=sum(r["plannedRR"] if r["outcome"]["result"]=="TP" else -1 for r in resolved)
    summary={"label":label,"cutoff":cutoff,"isTrueBlind":is_blind,"requested":len(COINS),"marketTrades":len(usable),"dataErrors":len(results)-len(usable),"resolved":len(resolved),"wins":len(wins),"losses":len(losses),"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*len(wins)/len(resolved),2) if resolved else None,"avgPlannedRR":round(sum(r["plannedRR"] for r in resolved)/len(resolved),3) if resolved else None,"expectancyR":round(total_r/len(resolved),3) if resolved else None}
    return {"summary":summary,"tests":results}

def main():
    samples={}
    for label,cutoff,is_blind in CUTOFFS:samples[label]=run_cutoff(label,cutoff,is_blind)
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V7 forced-market: per-coin regime/structure scoring plus free TP/SL. SL = nearest M15 pivot invalidation + coin-specific ATR buffer + empirical adverse-excursion floor. TP = per-coin pre-cutoff barrier calibration + nearest M15/H1 liquidity target, bounded only for reasonableness. Calibration maximizes historical win rate subject to positive expectancy and uses no post-cutoff candles. OLD is regression, NEW is true blind. OKX spot->OKX swap->Bybit fallback; 72h outcome window.","samples":samples}
    with open("data/blind_backtest.json","w",encoding="utf-8") as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v["summary"] for k,v in samples.items()},indent=2))

if __name__=="__main__":main()
