#!/usr/bin/env python3
"""V11 legacy-learned 4-month per-symbol walk-forward backtest.

Learns the strongest ideas from the historical V62/V63/V73 research engines:
- Forex H1 cross-currency strength/coherence features.
- Crypto 4H cross-universe regime/breadth/relative-strength features.
- Per-symbol ML meta-labeling (HistGradientBoosting / ExtraTrees).
- Style selection BEFORE the four-month evaluation window.
- Monthly expanding-window refits using only past data.
- Forced-daily ranking with 1..3 entries/day, RR exactly 1:1 or 1:2.
- Structural + ATR stop geometry, next-bar execution, conservative same-bar rule.
- No CUT logic in the score; timeout is a non-win.

This script is research/report-only. It never deploys, never trades and never
unlocks Telegram.
"""
from __future__ import annotations

import concurrent.futures as cf
import json, math, os, re, statistics, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "cloudflare-worker/v11/symbol-catalog.js"
V73 = ROOT / "data/nocut_intraday_allpass_v73.json"
OUT = ROOT / "data/v11_legacy_ml_backtest_4m.json"
GATE = ROOT / "data/v11_legacy_ml_backtest_gate.json"

VERSION = "V11-LEGACY-ML-WF-4M-R1"
EVAL_DAYS = int(os.environ.get("V11_BT_DAYS", "122"))
HISTORY_DAYS = int(os.environ.get("V11_HISTORY_DAYS", "330"))
REQUIRED_WR = float(os.environ.get("V11_REQUIRED_WR", "80"))
MIN_EVAL_TRADES = int(os.environ.get("V11_MIN_TOTAL_TRADES", "60"))
MIN_TUNE_DAYS = int(os.environ.get("V11_MIN_TUNE_DAYS", "18"))
MAX_WORKERS = int(os.environ.get("V11_OPT_WORKERS", "4"))

ALLOWED_RR = (1.0, 2.0)
MODEL_SPECS = (("HGB", 4, 12), ("HGB", 5, 20), ("ET", 10, 8))
THRESHOLDS = (0.55, 0.62, 0.70, 0.78)
MARGINS = (0.0, 0.06)
MAXTRADES = (1, 2, 3)
CFGS_FOREX = [(rr, rf, sw) for rr in ALLOWED_RR for rf in (0.60,0.75,1.0,1.25,1.5,2.0) for sw in (4,8,12)]
CFGS_CRYPTO = [(rr, rf, sw) for rr in ALLOWED_RR for rf in (0.60,0.75,1.0,1.25,1.5,2.0) for sw in (3,5,8)]
CFGS_OTHER = [(rr, rf, sw) for rr in ALLOWED_RR for rf in (0.60,0.75,1.0,1.25,1.5,2.0) for sw in (4,8,12)]
COST_ATR = {"forex":0.015, "crypto":0.020, "metal":0.020, "index":0.015}

FOREX_WINDOWS = {
    "ALL": (0,4,8,12,16,20), "ASIA": (0,4), "LONDON": (8,12),
    "NY": (12,16,20), "LONDON_NY": (8,12,16),
}
CRYPTO_WINDOWS = {"ALL": (0,4,8,12,16,20), "EARLY": (0,4), "MID": (8,12), "LATE": (12,16,20)}
METAL_WINDOWS = {"ALL": (0,4,8,12,16,20), "ASIA": (0,4), "LONDON": (8,12), "NY": (12,16,20), "CORE": (8,12,16)}
INDEX_WINDOWS = {"ALL": (0,4,8,12,16,20), "ASIA": (0,4,8), "EUROPE": (8,12,16), "US": (12,16,20)}
DIRS = ("BOTH","BUY","SELL")

CCY = ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
INDEX_Y = {"NAS100":"^NDX","US30":"^DJI","US500":"^GSPC","DEX":"^GDAXI","JP225":"^N225"}
USD_BASE = {"USDJPY":"JPY=X","USDCHF":"CHF=X","USDCAD":"CAD=X"}
METAL_Y = {"XAUUSD":"XAUUSD=X","XAGUSD":"XAGUSD=X"}

def now(): return datetime.now(timezone.utc)
def iso_dt(d): return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def norm(s): return re.sub(r"[^A-Z0-9]","",str(s).upper())
def safe_float(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None
def daystr(dt): return dt.date().isoformat()

def get_json(url, timeout=45, retries=4):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 TradingResearch/1.1","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last=e; time.sleep(0.6*(n+1))
    raise RuntimeError(f"HTTP_FAIL {last}")

def load_catalog():
    text=CATALOG.read_text(encoding="utf-8"); out={}
    for m in ("forex","crypto","metal","index"):
        z=re.search(rf"{m}:Object\.freeze\(\[(.*?)\]\)",text,re.S)
        if not z: raise RuntimeError("catalog parse "+m)
        out[m]=re.findall(r"'([^']+)'",z.group(1))
    return out

def legacy_prior(symbol, market):
    try: d=json.loads(V73.read_text(encoding="utf-8"))
    except Exception: return {}
    node=((d.get(market) or {}).get("symbols") or {}).get(symbol) or {}
    style=((node.get("method") or {}).get("style") or node.get("style") or {})
    return style if isinstance(style,dict) else {}

def yahoo_ticker(symbol,market):
    s=norm(symbol)
    if market=="forex": return USD_BASE.get(s,s+"=X")
    if market=="metal": return METAL_Y[s]
    if market=="index": return INDEX_Y[s]
    raise KeyError((s,market))

def yahoo_history(symbol,market,start_ts,end_ts):
    tickers=[yahoo_ticker(symbol,market)]
    if market=="metal": tickers += ["GC=F" if symbol=="XAUUSD" else "SI=F"]
    last=None
    for t in tickers:
        try:
            q=urllib.parse.urlencode({"period1":start_ts-3*86400,"period2":end_ts+3600,"interval":"1h","includePrePost":"true","events":"div,splits"})
            url="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(t,safe="^=")+"?"+q
            j=get_json(url); res=((j.get("chart") or {}).get("result") or [])
            if not res: raise RuntimeError("YAHOO_EMPTY")
            r=res[0]; ts=r.get("timestamp") or []; qd=((r.get("indicators") or {}).get("quote") or [{}])[0]
            O,H,L,C,V=[qd.get(k) or [] for k in ("open","high","low","close","volume")]
            rows=[]
            for i,t0 in enumerate(ts):
                t0=int(t0)
                if not(start_ts<=t0<=end_ts): continue
                vals=[safe_float(a[i]) if i<len(a) else None for a in (O,H,L,C)]
                if None in vals: continue
                vol=safe_float(V[i]) if i<len(V) else 0.0
                rows.append([t0,*vals,vol or 0.0])
            if rows:
                exact=(t==tickers[0]); return rows,("Yahoo Finance H1 "+t),exact
        except Exception as e: last=e
    raise RuntimeError(f"YAHOO_FAIL {last}")

def binance_history(symbol,start_ts,end_ts):
    cur=start_ts*1000; end=end_ts*1000; out=[]
    while cur<=end:
        q=urllib.parse.urlencode({"symbol":symbol,"interval":"1h","startTime":cur,"endTime":end,"limit":1000})
        j=get_json("https://api.binance.com/api/v3/klines?"+q,30,2)
        if not isinstance(j,list) or not j: break
        for x in j: out.append([int(x[0])//1000,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        nxt=int(j[-1][0])+3600000
        if nxt<=cur: break
        cur=nxt
        if len(j)<1000: break
        time.sleep(.02)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d: raise RuntimeError("BINANCE_EMPTY")
    return [d[k] for k in sorted(d)],"Binance Spot H1",True

def bybit_history(symbol,start_ts,end_ts):
    cursor=end_ts*1000; start=start_ts*1000; out=[]; guard=0
    while cursor>=start and guard<16:
        guard+=1
        q=urllib.parse.urlencode({"category":"spot","symbol":symbol,"interval":"60","start":start,"end":cursor,"limit":1000})
        j=get_json("https://api.bybit.com/v5/market/kline?"+q,30,2)
        arr=((j.get("result") or {}).get("list") or []) if isinstance(j,dict) else []
        if not arr: break
        ts=[]
        for x in arr:
            t=int(x[0])//1000; ts.append(t); out.append([t,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        nxt=min(ts)*1000-1
        if nxt>=cursor: break
        cursor=nxt; time.sleep(.02)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d: raise RuntimeError("BYBIT_EMPTY")
    return [d[k] for k in sorted(d)],"Bybit Spot H1",True

def fetch_one(symbol,market,start_ts,end_ts):
    try:
        if market=="crypto":
            try: rows,src,exact=binance_history(symbol,start_ts,end_ts)
            except Exception: rows,src,exact=bybit_history(symbol,start_ts,end_ts)
        else: rows,src,exact=yahoo_history(symbol,market,start_ts,end_ts)
        return symbol,rows,src,exact,None
    except Exception as e: return symbol,[],None,False,str(e)[:500]

def resample_4h(rows):
    b={}
    for r in rows:
        k=(r[0]//14400)*14400
        if k not in b: b[k]=[k,r[1],r[2],r[3],r[4],r[5]]
        else:
            z=b[k]; z[2]=max(z[2],r[2]); z[3]=min(z[3],r[3]); z[4]=r[4]; z[5]+=r[5]
    return [b[k] for k in sorted(b)]

def ema(v,n):
    out=[None]*len(v)
    if len(v)<n:return out
    e=sum(v[:n])/n;out[n-1]=e;k=2/(n+1)
    for i in range(n,len(v)): e=v[i]*k+e*(1-k);out[i]=e
    return out

def enrich(raw,bar_hours=1):
    rows=[{"ts":x[0],"dt":datetime.fromtimestamp(x[0],timezone.utc),"open":x[1],"high":x[2],"low":x[3],"close":x[4],"volume":x[5]} for x in raw]
    c=[x["close"] for x in rows];e20=ema(c,20);e50=ema(c,50)
    tr=[0.0]*len(rows);atr=[None]*len(rows);rsi=[None]*len(rows);adx=[None]*len(rows);plus=[0.0]*len(rows);minus=[0.0]*len(rows)
    for i in range(1,len(rows)):
        tr[i]=max(rows[i]["high"]-rows[i]["low"],abs(rows[i]["high"]-c[i-1]),abs(rows[i]["low"]-c[i-1]))
        up=rows[i]["high"]-rows[i-1]["high"];dn=rows[i-1]["low"]-rows[i]["low"]
        plus[i]=up if up>dn and up>0 else 0;minus[i]=dn if dn>up and dn>0 else 0
    if len(rows)>15:
        a=sum(tr[1:15])/14;pg=sum(plus[1:15])/14;mg=sum(minus[1:15])/14
        ag=sum(max(c[i]-c[i-1],0) for i in range(1,15))/14;al=sum(max(c[i-1]-c[i],0) for i in range(1,15))/14;dx=[]
        for i in range(14,len(rows)):
            if i>14:
                a=(a*13+tr[i])/14;pg=(pg*13+plus[i])/14;mg=(mg*13+minus[i])/14
                d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
            atr[i]=a;rsi[i]=100 if al==0 else 100-100/(1+ag/al)
            pdi=100*pg/a if a else 0;mdi=100*mg/a if a else 0;den=pdi+mdi;dxv=100*abs(pdi-mdi)/den if den else 0;dx.append(dxv)
            if len(dx)>=14:adx[i]=sum(dx[-14:])/14
    higher_n=4 if bar_hours==1 else 6; buckets=defaultdict(list)
    for i,r in enumerate(rows):
        key=r["dt"].replace(hour=(r["dt"].hour//4)*4,minute=0,second=0,microsecond=0) if bar_hours==1 else r["dt"].date().isoformat()
        buckets[key].append((i,r))
    higher=[]
    for key in sorted(buckets):
        z=buckets[key]
        if len(z)>=higher_n: higher.append({"last_i":z[-1][0],"close":z[-1][1]["close"]})
    hc=[x["close"] for x in higher];h20=ema(hc,20);h50=ema(hc,50);hmap={}
    for j,x in enumerate(higher):
        if h20[j] is not None and h50[j] is not None:
            st=1 if x["close"]>h20[j]>h50[j] else -1 if x["close"]<h20[j]<h50[j] else (1 if x["close"]>h20[j] else -1);hmap[x["last_i"]]=st
    lasth=0
    for i,r in enumerate(rows):
        if i in hmap:lasth=hmap[i]
        r.update({"ema20":e20[i],"ema50":e50[i],"atr":atr[i],"rsi":rsi[i],"adx":adx[i],"htf":lasth})
        if i>=72 and atr[i] and c[i]>0:
            mult=1 if bar_hours==1 else 4; hs=(3,6,12,24,72) if bar_hours==1 else (8,24,72)
            for h in hs:
                bars=max(1,h//mult)
                if i>=bars and c[i-bars]>0:r[f"ret{h}"]=math.log(c[i]/c[i-bars])
            lag=max(1,6//mult);r["mom"]=(c[i]-c[i-lag])/atr[i] if i>=lag else 0;r["dev"]=(c[i]-e20[i])/atr[i] if e20[i] else 0
            lag2=max(1,8//mult);r["session"]=(c[i]-c[i-lag2])/atr[i] if i>=lag2 else 0
    return rows

def exec_intraday(rows,i,side,cfg,market):
    rr,rf,sw=cfg
    if i+1>=len(rows) or rows[i].get("atr") is None:return None
    sig=rows[i];atr=sig["atr"];ei=i+1;entry=rows[ei]["open"]+side*COST_ATR[market]*atr;eday=rows[ei]["dt"].date()
    recent=rows[max(0,i-sw+1):i+1];swing=min(x["low"] for x in recent) if side==1 else max(x["high"] for x in recent)
    struct=entry-swing if side==1 else swing-entry;risk=max(rf*atr,struct+.05*atr,.20*atr)
    if risk<=0 or risk>4*atr:return None
    sl=entry-side*risk;tp=entry+side*rr*risk;lastj=ei
    for j in range(ei,len(rows)):
        if rows[j]["dt"].date()!=eday:break
        lastj=j;x=rows[j];hs=x["low"]<=sl if side==1 else x["high"]>=sl;ht=x["high"]>=tp if side==1 else x["low"]<=tp
        if hs and ht:return ("SL",-1.0,j-ei+1)
        if hs:return ("SL",-1.0,j-ei+1)
        if ht:return ("TP",rr,j-ei+1)
    return ("TIMEOUT",0.0,lastj-ei+1)

def forex_maps(data):
    maps={s:{r["dt"]:(i,r) for i,r in rows} for s,rows in data.items()}
    if not maps:return {},[]
    common=set.intersection(*(set(x) for x in maps.values()));return maps,sorted(t for t in common if t.hour in (0,4,8,12,16,20))

def forex_factor_pack(pairs,maps,t):
    packs={};disps={}
    for h in (3,6,12,24,72):
        vals={c:[] for c in CCY};pairret={}
        for p in pairs:
            q=maps[p].get(t);v=q[1].get(f"ret{h}") if q else None
            if v is not None:pairret[p]=v
        if len(pairret)<max(20,int(len(pairs)*.75)):return None
        mu=statistics.mean(pairret.values());sd=statistics.pstdev(pairret.values()) or 1
        for p,v in pairret.items():
            z=(v-mu)/sd;b,q=p[:3],p[3:];vals[b].append(z);vals[q].append(-z)
        strength={c:(statistics.mean(vals[c]) if vals[c] else 0) for c in CCY};coh={c:(abs(sum(1 if x>0 else -1 if x<0 else 0 for x in vals[c]))/len(vals[c]) if vals[c] else 0) for c in CCY}
        order=sorted(CCY,key=lambda c:strength[c],reverse=True);rank={c:i for i,c in enumerate(order)};packs[h]={"s":strength,"c":coh,"r":rank};disps[h]=statistics.pstdev(strength.values()) or 1
    return packs,disps

def forex_feature(pair,row,fp,side):
    b,q=pair[:3],pair[3:];packs,disp=fp;g={h:packs[h]["s"][b]-packs[h]["s"][q] for h in (3,6,12,24,72)}
    coh3=min(packs[3]["c"][b],packs[3]["c"][q]);coh24=min(packs[24]["c"][b],packs[24]["c"][q]);rank3=packs[3]["r"][q]-packs[3]["r"][b];rank24=packs[24]["r"][q]-packs[24]["r"][b]
    h1=1 if row["close"]>row["ema20"]>row["ema50"] else -1 if row["close"]<row["ema20"]<row["ema50"] else (1 if row["close"]>row["ema20"] else -1);ar=row["rsi"] if side==1 else 100-row["rsi"]
    grp=0 if "USD" in (b,q) else 1 if "JPY" in (b,q) else 2 if b in ("AUD","NZD","CAD") and q in ("AUD","NZD","CAD") else 3 if b in ("EUR","GBP","CHF") and q in ("EUR","GBP","CHF") else 4
    f=[*(side*g[h] for h in (3,6,12,24,72)),coh3,coh24,side*rank3/7,side*rank24/7,side*h1,side*row["htf"],row["adx"]/50,ar/100,side*row["mom"]/3,side*row["dev"]/3,side*row["session"]/3,abs(g[3])/(disp[3]+1e-9),abs(g[24])/(disp[24]+1e-9),row["dt"].hour/23,grp/4]
    f += [1.0 if b==c else 0.0 for c in CCY]+[1.0 if q==c else 0.0 for c in CCY];return f

def build_forex_raw(pairs,data):
    maps,times=forex_maps(data);raw={s:[] for s in pairs};baseline=(1.0,1.0,8)
    for t in times:
        fp=forex_factor_pack(pairs,maps,t)
        if not fp:continue
        for p in pairs:
            q=maps[p].get(t)
            if not q:continue
            i,row=q
            if row.get("adx") is None or row.get("rsi") is None or row.get("ema50") is None:continue
            for side in (1,-1):
                o=exec_intraday(data[p],i,side,baseline,"forex")
                if o:raw[p].append({"i":i,"time":t,"day":daystr(t),"side":side,"x":forex_feature(p,row,fp,side),"label":1 if o[0]=="TP" else 0})
    return raw

def crypto_regime(symbols,maps,t):
    eligible={}
    for s in symbols:
        q=maps[s].get(t)
        if q and q[1].get("ret24") is not None and q[1].get("adx") is not None:eligible[s]=q
    if len(eligible)<max(15,int(len(symbols)*.5)):return None
    rets=[q[1]["ret24"] for q in eligible.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);disp=statistics.pstdev(rets) or 1e-9
    btc=eligible.get("BTCUSDT");btc24=btc[1]["ret24"] if btc else med;btc72=btc[1].get("ret72",0) if btc else 0
    return eligible,{"breadth":breadth,"median24":med,"dispersion24":disp,"btc24":btc24,"btc72":btc72,"eligible":len(eligible)}

def crypto_feature(sym,row,reg,side):
    h4=1 if row["close"]>row["ema20"]>row["ema50"] else -1 if row["close"]<row["ema20"]<row["ema50"] else (1 if row["close"]>row["ema20"] else -1)
    ar=row["rsi"] if side==1 else 100-row["rsi"];ba=reg["breadth"] if side==1 else 1-reg["breadth"];rel24=side*(row.get("ret24",0)-reg["btc24"]);rel72=side*(row.get("ret72",0)-reg["btc72"])
    return [side*h4,side*row["htf"],row["adx"]/50,ar/100,side*row["mom"]/4,side*row["dev"]/3,ba,side*reg["btc24"]*20,side*reg["btc72"]*10,rel24*20,rel72*10,abs(reg["median24"])*20,reg["dispersion24"]*20,reg["eligible"]/100]

def build_crypto_raw(symbols,data):
    maps={s:{r["dt"]:(i,r) for i,r in rows} for s,rows in data.items()};times=sorted(set().union(*(set(x) for x in maps.values())));raw={s:[] for s in symbols};baseline=(1.0,1.0,5)
    for t in times:
        regpack=crypto_regime(symbols,maps,t)
        if not regpack:continue
        eligible,reg=regpack
        for s in symbols:
            q=eligible.get(s)
            if not q:continue
            i,row=q
            for side in (1,-1):
                o=exec_intraday(data[s],i,side,baseline,"crypto")
                if o:raw[s].append({"i":i,"time":t,"day":daystr(t),"side":side,"x":crypto_feature(s,row,reg,side),"label":1 if o[0]=="TP" else 0})
    return raw

def generic_feature(rows,i,side,peer_pack=None):
    r=rows[i];h1=1 if r["close"]>r["ema20"]>r["ema50"] else -1 if r["close"]<r["ema20"]<r["ema50"] else (1 if r["close"]>r["ema20"] else -1);ar=r["rsi"] if side==1 else 100-r["rsi"];rets=[r.get(f"ret{h}",0) for h in (3,6,12,24,72)];pp=peer_pack or (0,0,0)
    return [*(side*x*20 for x in rets),side*h1,side*r["htf"],r["adx"]/50,ar/100,side*r["mom"]/3,side*r["dev"]/3,side*r["session"]/3,*pp,r["dt"].hour/23]

def build_generic_raw(symbols,data,market):
    maps={s:{r["dt"]:(i,r) for i,r in rows} for s,rows in data.items()};raw={s:[] for s in symbols};baseline=(1.0,1.0,8);times=sorted(set().union(*(set(x) for x in maps.values())))
    for t in times:
        avail=[]
        for s in symbols:
            q=maps[s].get(t)
            if q and q[1].get("ret24") is not None:avail.append((s,q))
        vals=[q[1]["ret24"] for _,q in avail];med=statistics.median(vals) if vals else 0;disp=statistics.pstdev(vals) if len(vals)>1 else 0
        for s,q in avail:
            i,row=q
            if row.get("adx") is None or row.get("rsi") is None:continue
            rel=(row.get("ret24",0)-med)/(disp or 1)
            for side in (1,-1):
                o=exec_intraday(data[s],i,side,baseline,market)
                if o:raw[s].append({"i":i,"time":t,"day":daystr(t),"side":side,"x":generic_feature(data[s],i,side,(side*rel,abs(med)*20,disp*20)),"label":1 if o[0]=="TP" else 0})
    return raw

def fit_model(train,spec,seed):
    if len(train)<120:return None
    X=np.asarray([x["x"] for x in train],float);y=np.asarray([x["label"] for x in train],int)
    if len(set(y))<2:return None
    kind,d,l=spec
    if kind=="ET":m=ExtraTreesClassifier(n_estimators=180,max_depth=d,min_samples_leaf=l,max_features=.75,class_weight="balanced_subsample",n_jobs=1,random_state=seed)
    else:m=HistGradientBoostingClassifier(max_iter=140,max_leaf_nodes=2**d-1,min_samples_leaf=l,learning_rate=.05,l2_regularization=4.0,random_state=seed)
    m.fit(X,y);return m

def score_period(base,train_end,a,z,spec,seed):
    tr=[x for x in base if x["day"]<=train_end];te=[x for x in base if a<=x["day"]<=z];m=fit_model(tr,spec,seed)
    if m is None or not te:return []
    p=m.predict_proba(np.asarray([x["x"] for x in te],float))[:,1];return [dict(x,prob=float(v)) for x,v in zip(te,p)]

def choose_day(scored,window_hours,direction,thr,margin,maxtrades,market):
    hours=set(window_hours);g=defaultdict(lambda:defaultdict(list))
    for x in scored:
        if market!="crypto" and x["time"].weekday()>=5:continue
        if x["time"].hour not in hours:continue
        if direction=="BUY" and x["side"]!=1:continue
        if direction=="SELL" and x["side"]!=-1:continue
        g[x["day"]][x["time"]].append(x)
    out=[]
    for d,times in sorted(g.items()):
        chosen=[];ordered=sorted(times)
        for ti,t in enumerate(ordered):
            z=sorted(times[t],key=lambda q:q["prob"],reverse=True);best=z[0];other=z[1]["prob"] if len(z)>1 else 0.0;edge=best["prob"]-other;is_last=ti==len(ordered)-1
            if best["prob"]>=thr and edge>=margin:
                chosen.append(best)
                if len(chosen)>=maxtrades:break
            elif is_last and not chosen:chosen.append(best)
        if not chosen and ordered:chosen=[max(times[ordered[-1]],key=lambda q:q["prob"])]
        out.extend(chosen)
    return out

def expected_days(scored,window_hours,direction,market):
    h=set(window_hours);days=set()
    for x in scored:
        if market!="crypto" and x["time"].weekday()>=5:continue
        if x["time"].hour not in h:continue
        if direction=="BUY" and x["side"]!=1:continue
        if direction=="SELL" and x["side"]!=-1:continue
        days.add(x["day"])
    return len(days)

def event_key(e): return (int(e["i"]),int(e["side"]),int(e["time"].timestamp()))
def precompute_outcomes(rows,base,cfgs,market):
    out={}
    for e in base:
        k=event_key(e);out[k]={}
        for cfg in cfgs:out[k][cfg]=exec_intraday(rows,e["i"],e["side"],cfg,market)
    return out

def eval_sel(sel,rows,cfg,expected,market,outcomes=None):
    z=[];days=set();counts=defaultdict(int)
    for e in sel:
        o=outcomes.get(event_key(e),{}).get(cfg) if outcomes is not None else exec_intraday(rows,e["i"],e["side"],cfg,market)
        if not o:continue
        z.append(o);days.add(e["day"]);counts[e["day"]]+=1
    tp=sum(x[0]=="TP" for x in z);sl=sum(x[0]=="SL" for x in z);to=sum(x[0]=="TIMEOUT" for x in z);n=len(z);wr=100*tp/n if n else 0
    return {"trades":n,"daysTraded":len(days),"expectedDays":expected,"coveragePct":round(100*len(days)/expected,2) if expected else 0,"tp":tp,"sl":sl,"timeout":to,"winRate":round(wr,2),"meanR":round((tp*cfg[0]-sl)/n,3) if n else -9,"maxTradesInDay":max(counts.values(),default=0)}

def rank_tune(s):
    hit=s["coveragePct"]>=95 and s["trades"]>=s["expectedDays"] and s["trades"]<=3*s["expectedDays"] and s["winRate"]>=REQUIRED_WR and s["meanR"]>0
    return (int(hit),s["winRate"],s["meanR"],-s["timeout"],-s["trades"])

def windows_for(market,prior):
    base={"forex":FOREX_WINDOWS,"crypto":CRYPTO_WINDOWS,"metal":METAL_WINDOWS,"index":INDEX_WINDOWS}[market].copy();h=prior.get("signalHourUTC")
    if isinstance(h,(int,float)) and 0<=int(h)<=23:base["V73_HOUR"]=(int(h),)
    return base

def configs_for(market):return CFGS_CRYPTO if market=="crypto" else CFGS_FOREX if market=="forex" else CFGS_OTHER

def tune_symbol(symbol,market,base,rows,eval_start,prior,seed):
    tune_end=eval_start-timedelta(hours=1);tune_start=eval_start-timedelta(days=31);train_end=tune_start-timedelta(hours=1);a,z=daystr(tune_start),daystr(tune_end);te=daystr(train_end)
    cfgs=configs_for(market);tune_base=[x for x in base if a<=x["day"]<=z];outcomes=precompute_outcomes(rows,tune_base,cfgs,market);best=None;bp=None
    for mi,spec in enumerate(MODEL_SPECS):
        scored=score_period(base,te,a,z,spec,seed+mi)
        if not scored:continue
        for w,hours in windows_for(market,prior).items():
            for d in DIRS:
                exp=expected_days(scored,hours,d,market)
                if exp<MIN_TUNE_DAYS:continue
                for th in THRESHOLDS:
                    for ma in MARGINS:
                        for mt in MAXTRADES:
                            sel=choose_day(scored,hours,d,th,ma,mt,market)
                            for cfg in cfgs:
                                s=eval_sel(sel,rows,cfg,exp,market,outcomes);q=rank_tune(s)
                                if best is None or q>best:best=q;bp=(spec,w,hours,d,th,ma,mt,cfg,s)
    return bp

def month_chunks(start_dt,end_dt):
    cur=start_dt;out=[]
    while cur<end_dt:
        nxt=(cur.replace(day=28)+timedelta(days=4)).replace(day=1);z=min(end_dt,nxt);out.append((cur,z));cur=z
    return out

def walk_forward(symbol,market,base,rows,bp,eval_start,eval_end,seed):
    spec,w,hours,d,th,ma,mt,cfg,tune=bp;monthly=[];allsel=[]
    for j,(a_dt,z_dt) in enumerate(month_chunks(eval_start,eval_end)):
        train_end=a_dt-timedelta(hours=1);scored=score_period(base,daystr(train_end),daystr(a_dt),daystr(z_dt-timedelta(seconds=1)),spec,seed+100+j);exp=expected_days(scored,hours,d,market);sel=choose_day(scored,hours,d,th,ma,mt,market);s=eval_sel(sel,rows,cfg,exp,market);monthly.append({"start":daystr(a_dt),"end":daystr(z_dt-timedelta(seconds=1)),**s});allsel.extend(sel)
    expected=sum(x["expectedDays"] for x in monthly);full=eval_sel(allsel,rows,cfg,expected,market);return monthly,full

def optimize_symbol(symbol,market,base,rows,source,exact,err,eval_start,eval_end,seed):
    r={"symbol":symbol,"market":market,"source":source,"sourceExactInstrument":bool(exact),"dataError":err,"rows":len(rows),"rawCandidates":len(base)}
    if err or not rows:r.update({"pass":False,"reasons":["DATA_UNAVAILABLE"]});return r
    if len(base)<180:r.update({"pass":False,"reasons":["INSUFFICIENT_HISTORY_OR_CANDIDATES"]});return r
    prior=legacy_prior(symbol,market);bp=tune_symbol(symbol,market,base,rows,eval_start,prior,seed)
    if bp is None:r.update({"pass":False,"reasons":["NO_PRE_EVAL_STYLE"],"legacyPrior":prior});return r
    monthly,full=walk_forward(symbol,market,base,rows,bp,eval_start,eval_end,seed);spec,w,hours,d,th,ma,mt,cfg,tune=bp;reasons=[]
    if full["trades"]<MIN_EVAL_TRADES:reasons.append("MIN_EVAL_TRADES")
    if full["coveragePct"]<90:reasons.append("COVERAGE_BELOW_90")
    if full["maxTradesInDay"]>3:reasons.append("MAX3_BREACH")
    if full["winRate"]<REQUIRED_WR:reasons.append("WIN_RATE_BELOW_80")
    if full["meanR"]<=0:reasons.append("MEAN_R_NONPOSITIVE")
    if cfg[0] not in ALLOWED_RR:reasons.append("RR_INVALID")
    if not exact:reasons.append("NON_EXACT_DATA_FALLBACK")
    r.update({"pass":not reasons,"reasons":reasons,"legacyPrior":prior,"profile":{"model":{"kind":spec[0],"depth":spec[1],"leaf":spec[2]},"window":w,"hoursUTC":list(hours),"direction":d,"triggerProbability":th,"sideEdge":ma,"maxTradesPerDay":mt,"execution":{"rr":cfg[0],"riskFloorATR":cfg[1],"swingBars":cfg[2]}},"preEvalTune":tune,"monthlyWalkForward":monthly,"full4m":full});return r

def main():
    end_dt=now().replace(minute=0,second=0,microsecond=0);eval_start=end_dt-timedelta(days=EVAL_DAYS);history_start=end_dt-timedelta(days=HISTORY_DAYS);start_ts,end_ts=int(history_start.timestamp()),int(end_dt.timestamp());cat=load_catalog();items=[(s,m) for m in ("forex","crypto","metal","index") for s in cat[m]]
    fetched={}
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs={ex.submit(fetch_one,s,m,start_ts,end_ts):(s,m) for s,m in items}
        for fut in cf.as_completed(futs):
            s,m=futs[fut];ss,rows,src,exact,err=fut.result();fetched[ss]=(m,rows,src,exact,err);print("FETCH",m,ss,len(rows),src or err,flush=True)
    enriched={};meta={}
    for s,m in items:
        mm,raw,src,exact,err=fetched[s];rr=resample_4h(raw) if m=="crypto" else raw;enriched[s]=enrich(rr,4 if m=="crypto" else 1) if rr else [];meta[s]=(src,exact,err)
    forex_data={s:enriched[s] for s in cat["forex"] if enriched[s]};crypto_data={s:enriched[s] for s in cat["crypto"] if enriched[s]};metal_data={s:enriched[s] for s in cat["metal"] if enriched[s]};index_data={s:enriched[s] for s in cat["index"] if enriched[s]}
    print("BUILD RAW FOREX",flush=True);raw_forex=build_forex_raw(cat["forex"],forex_data) if len(forex_data)==len(cat["forex"]) else {s:[] for s in cat["forex"]}
    print("BUILD RAW CRYPTO",flush=True);raw_crypto=build_crypto_raw(cat["crypto"],crypto_data) if crypto_data else {s:[] for s in cat["crypto"]}
    print("BUILD RAW METAL",flush=True);raw_metal=build_generic_raw(cat["metal"],metal_data,"metal") if metal_data else {s:[] for s in cat["metal"]}
    print("BUILD RAW INDEX",flush=True);raw_index=build_generic_raw(cat["index"],index_data,"index") if index_data else {s:[] for s in cat["index"]};raws={**raw_forex,**raw_crypto,**raw_metal,**raw_index};results={}
    def job(idx,s,m):
        src,exact,err=meta[s];print("OPT",m,s,flush=True);return s,optimize_symbol(s,m,raws.get(s,[]),enriched[s],src,exact,err,eval_start,end_dt,110000+idx*100)
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs=[ex.submit(job,i,s,m) for i,(s,m) in enumerate(items)]
        for fut in cf.as_completed(futs):
            s,r=fut.result();results[s]=r;print("RESULT",s,"PASS" if r.get("pass") else "FAIL",(r.get("full4m") or {}).get("winRate"),r.get("reasons"),flush=True)
    results={s:results[s] for s,m in items};passed=[s for s,x in results.items() if x.get("pass")];failed=[s for s,x in results.items() if not x.get("pass")]
    meta_out={"version":VERSION,"generatedAt":iso_dt(now()),"historyStart":iso_dt(history_start),"evaluationStart":iso_dt(eval_start),"evaluationEnd":iso_dt(end_dt),"evaluationDays":EVAL_DAYS,"requiredWinRateInclusive":REQUIRED_WR,"allowedRR":[1,2],"maxEntriesPerEligibleDay":3,"totalSymbols":len(items),"passCount":len(passed),"allPassed":len(passed)==len(items),"method":"V62/V63/V73 learned: pre-eval style selection + monthly expanding walk-forward ML refits; no evaluation-window retuning","sameBarRule":"SL conservative","timeoutRule":"non-win","dataSources":{"forex":"Yahoo Finance exact FX H1","crypto":"Binance Spot H1 -> Bybit Spot H1; resampled closed 4H","metal":"Yahoo Finance spot H1; futures only flagged fallback","index":"Yahoo Finance exact cash index H1"}}
    OUT.write_text(json.dumps({"meta":meta_out,"markets":{k:len(v) for k,v in cat.items()},"symbols":results},ensure_ascii=False,indent=2),encoding="utf-8");GATE.write_text(json.dumps({**meta_out,"passingSymbols":passed,"failingSymbols":failed},ensure_ascii=False,indent=2),encoding="utf-8");print("SUMMARY",json.dumps({"passCount":len(passed),"totalSymbols":len(items),"allPassed":not failed,"failedCount":len(failed)},ensure_ascii=False),flush=True);return 0

if __name__=="__main__": raise SystemExit(main())
