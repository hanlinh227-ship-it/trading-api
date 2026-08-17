#!/usr/bin/env python3
"""V76 Forex entry research.

Research-only layer. It never modifies V73 and is not imported by V75 live data.

Protocol:
- fetch exact Twelve Data Forex M5 history in quota-safe 28-symbol batches;
- derive M15/H1/H4 from M5 without extra credits;
- fetch D1 separately for stable higher-timeframe context;
- detect six objective entry archetypes A-F with frozen thresholds;
- evaluate CLOSE / RETEST / LIMIT_FVG entries, structure / ATR-floor stops,
  RR1 / RR2;
- chronological 60/20/20 DEV / VALIDATION / untouched OOS split;
- select archetype/variant from DEV, gate on VALIDATION, and use OOS only as
  a promotion check. OOS never changes parameters or ranking;
- store only compact research summaries and locked per-symbol methods.

Historical broker bid/ask and a trustworthy historical macro-event calendar are
not available in the canonical feed. Results therefore apply a conservative
fixed round-trip cost in R and report news-window research as unavailable rather
than fabricating it. The live V74 news gate remains mandatory.
"""
from __future__ import annotations

import bisect
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
try:
    import twelvedata_market as td
except ModuleNotFoundError:
    td = None

VERSION = "V76-ENTRY-RESEARCH-R1"
PAIRS = "EURUSD GBPUSD USDJPY USDCHF USDCAD AUDUSD NZDUSD EURJPY EURGBP EURCHF EURAUD EURNZD EURCAD GBPJPY GBPCHF GBPAUD GBPNZD GBPCAD AUDJPY AUDNZD AUDCAD AUDCHF NZDJPY NZDCAD NZDCHF CADJPY CADCHF CHFJPY".split()
MARKET = {s: f"{s[:3]}/{s[3:]}" for s in PAIRS}
COST_R = 0.05
MAX_HOLD_BARS = 36
RETEST_BARS = 4
COOLDOWN_BARS = 6
LONDON_TZ = ZoneInfo("Europe/London")
NY_TZ = ZoneInfo("America/New_York")
SETUP_DEFS = {
    "A_SWEEP_MSS": "M15 sweeps previous 8-bar liquidity and closes back inside; within 6 M5 bars a >=0.50 ATR body closes beyond the previous 5-bar M5 swing in the reversal direction.",
    "B_H1_PULLBACK_RECLAIM": "H1 close/EMA20/EMA50 trend; latest closed M15 touches EMA20 and closes back with trend; M5 displacement closes beyond previous 5-bar swing.",
    "C_SWEEP_FVG": "M15 liquidity sweep as A, followed within 6 M5 bars by a same-direction 3-candle FVG >=0.05 M5 ATR.",
    "D_BREAK_RETEST_CONT": "H1 trend; M15 closes beyond previous 12-bar range by >=0.05 M15 ATR; within next 4 M15 bars price retests the breakout level and closes on breakout side; M5 displacement confirms continuation.",
    "E_FAILED_BREAK_REV": "M15 exceeds previous 12-bar extreme by >=0.15 ATR but closes back inside the prior range and beyond its midpoint; M5 displacement confirms reversal within 6 M5 bars.",
    "F_IFVG_RECLAIM": "A prior opposite-direction M5 FVG >=0.05 ATR is invalidated by a displacement close through the far edge; the inverted gap is the reclaim/retest zone.",
}
ENTRY_MODES = ("CLOSE", "RETEST", "LIMIT_FVG")
STOP_MODES = ("STRUCTURE", "STRUCTURE_ATR")
RR_VALUES = (1, 2)


def utcnow(): return datetime.now(timezone.utc)
def iso(dt): return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
def parse_dt(v):
    s = str(v).replace("Z", "+00:00").replace(" ", "T")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
def fnum(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except Exception: return None
def mean(xs): return sum(xs)/len(xs) if xs else None

def ema_series(vals,p):
    out=[None]*len(vals)
    if len(vals)<p:return out
    e=sum(vals[:p])/p;out[p-1]=e;k=2/(p+1)
    for i in range(p,len(vals)):e=vals[i]*k+e*(1-k);out[i]=e
    return out

def rsi_series(vals,p=14):
    out=[None]*len(vals)
    if len(vals)<=p:return out
    ag=al=0.0
    for i in range(1,p+1):
        d=vals[i]-vals[i-1];ag+=max(d,0);al+=max(-d,0)
    ag/=p;al/=p;out[p]=100.0 if al==0 else 100-100/(1+ag/al)
    for i in range(p+1,len(vals)):
        d=vals[i]-vals[i-1];ag=(ag*(p-1)+max(d,0))/p;al=(al*(p-1)+max(-d,0))/p
        out[i]=100.0 if al==0 else 100-100/(1+ag/al)
    return out

def atr_series(rows,p=14):
    out=[None]*len(rows)
    if len(rows)<=p:return out
    tr=[max(rows[i][2]-rows[i][3],abs(rows[i][2]-rows[i-1][4]),abs(rows[i][3]-rows[i-1][4])) for i in range(1,len(rows))]
    a=sum(tr[:p])/p;out[p]=a
    for i in range(p+1,len(rows)):a=(a*(p-1)+tr[i-1])/p;out[i]=a
    return out

@dataclass
class TF:
    rows:list;end_ts:list;ema20:list;ema50:list;ema200:list;rsi14:list;atr14:list

def enrich(rows,seconds):
    closes=[r[4] for r in rows]
    return TF(rows,[r[0]+seconds for r in rows],ema_series(closes,20),ema_series(closes,50),ema_series(closes,200),rsi_series(closes),atr_series(rows))
def resample(rows,seconds):
    b={}
    for r in rows:
        k=(r[0]//seconds)*seconds
        if k not in b:b[k]=[k,r[1],r[2],r[3],r[4],r[5] or 0.0]
        else:b[k][2]=max(b[k][2],r[2]);b[k][3]=min(b[k][3],r[3]);b[k][4]=r[4];b[k][5]+=(r[5] or 0.0)
    return [b[k] for k in sorted(b)]
def tf_idx(tf,ts):return bisect.bisect_right(tf.end_ts,ts)-1
def trend(tf,i):
    if i<0:return "NEUTRAL"
    c=tf.rows[i][4];a=tf.ema20[i];b=tf.ema50[i]
    if None in (a,b):return "NEUTRAL"
    return "LONG" if c>a>b else "SHORT" if c<a<b else "NEUTRAL"
def session_label(ts):
    dt=datetime.fromtimestamp(ts,tz=timezone.utc);lo=dt.astimezone(LONDON_TZ);ny=dt.astimezone(NY_TZ)
    l=lo.weekday()<5 and 7<=lo.hour<12;n=ny.weekday()<5 and 8<=ny.hour<12
    return "OVERLAP" if l and n else "LONDON" if l else "NEW_YORK" if n else "OFF_SESSION"
def vol_regime(h1,i):
    if i<30 or h1.atr14[i] is None:return "UNKNOWN"
    vals=[x for x in h1.atr14[max(0,i-30):i+1] if x is not None]
    if len(vals)<10:return "UNKNOWN"
    med=statistics.median(vals);a=h1.atr14[i]
    return "HIGH" if a>1.25*med else "LOW" if a<.8*med else "NORMAL"
def htf_alignment(side,d1,di,h4,h4i,h1,h1i):
    states=[trend(d1,di),trend(h4,h4i),trend(h1,h1i)];same=sum(x==side for x in states);opp=sum(x not in (side,"NEUTRAL") for x in states)
    return "ALIGNED_3" if same==3 else "ALIGNED_2" if same==2 and not opp else "CONFLICT" if opp else "MIXED"

def batch_request(symbols,interval,outputsize,end_date=None):
    if td is None:raise RuntimeError("twelvedata_market unavailable")
    p={"symbol":",".join(symbols),"interval":interval,"outputsize":outputsize,"timezone":"UTC","order":"ASC"}
    if end_date:p["end_date"]=end_date
    r=td.request_json("time_series",p,retries=3,timeout=90)
    if not r.get("ok"):raise RuntimeError(f"batch {interval} failed: {r}")
    return r.get("data") or {}
def extract_batch(data):
    if isinstance(data,dict) and "meta" in data and "values" in data:return {str((data.get("meta") or {}).get("symbol")):data}
    return {str(k):v for k,v in data.items() if isinstance(v,dict) and ("values" in v or "meta" in v)} if isinstance(data,dict) else {}
def parse_values(obj,expected):
    meta=obj.get("meta") or {}
    if str(meta.get("symbol","")).upper()!=expected.upper():raise RuntimeError(f"meta mismatch {expected}: {meta}")
    if meta.get("type")!="Physical Currency":raise RuntimeError(f"type mismatch {expected}: {meta.get('type')}")
    out=[]
    for x in obj.get("values") or []:
        o,h,l,c=[fnum(x.get(k)) for k in ("open","high","low","close")]
        if None in (o,h,l,c):continue
        out.append([int(parse_dt(x.get("datetime")).timestamp()),o,h,l,c,fnum(x.get("volume"))])
    return sorted(out,key=lambda r:r[0])
def get_obj(batch,s):
    ms=MARKET[s];return batch.get(ms) or batch.get(s) or batch.get(ms.replace("/",""))
def fetch_history(chunks=3,outputsize=5000,pause=62):
    market=[MARKET[s] for s in PAIRS];hist={s:[] for s in PAIRS};end=None;log=[]
    for n in range(chunks):
        batch=extract_batch(batch_request(market,"5min",outputsize,end));old=[];sizes=[]
        for s in PAIRS:
            obj=get_obj(batch,s)
            if obj is None:raise RuntimeError(f"missing M5 {MARKET[s]}; keys={list(batch)[:8]}")
            rows=parse_values(obj,MARKET[s]);hist[s].extend(rows);sizes.append(len(rows));old.extend([rows[0][0]] if rows else [])
        log.append({"kind":"M5","chunk":n+1,"endDate":end,"rowsMin":min(sizes)})
        end=iso(datetime.fromtimestamp(min(old)-300,tz=timezone.utc)) if old else None
        if n<chunks-1:time.sleep(pause)
    time.sleep(pause)
    db=extract_batch(batch_request(market,"1day",500));daily={}
    for s in PAIRS:
        obj=get_obj(db,s)
        if obj is None:raise RuntimeError(f"missing D1 {MARKET[s]}")
        daily[s]=parse_values(obj,MARKET[s])
        hist[s]=[dict((r[0],r) for r in hist[s])[k] for k in sorted(dict((r[0],r) for r in hist[s]))]
    return hist,daily,log

def m15_sweeps(tf,j):
    if j<8 or tf.atr14[j] is None:return []
    prev=tf.rows[j-8:j];cur=tf.rows[j];lo=min(x[3] for x in prev);hi=max(x[2] for x in prev);out=[]
    if cur[3]<lo and cur[4]>lo:out.append(("LONG",lo,cur[3]))
    if cur[2]>hi and cur[4]<hi:out.append(("SHORT",hi,cur[2]))
    return out
def displacement(m5,i,side):
    if i<5 or m5.atr14[i] is None:return None
    cur=m5.rows[i];prev=m5.rows[i-5:i];a=m5.atr14[i]
    if abs(cur[4]-cur[1])<.5*a:return None
    lv=max(x[2] for x in prev) if side=="LONG" else min(x[3] for x in prev)
    ok=cur[4]>lv and cur[4]>cur[1] if side=="LONG" else cur[4]<lv and cur[4]<cur[1]
    return lv if ok else None
def fvg_at(m5,i,side):
    if i<2 or m5.atr14[i] is None:return None
    a=m5.atr14[i];x=m5.rows[i-2];c=m5.rows[i]
    if side=="LONG" and c[3]>x[2] and c[3]-x[2]>=.05*a:return [x[2],c[3]]
    if side=="SHORT" and c[2]<x[3] and x[3]-c[2]>=.05*a:return [c[2],x[3]]
    return None
def opposite_gap(m5,i,side):
    opp="SHORT" if side=="LONG" else "LONG"
    for k in range(i-1,max(1,i-12)-1,-1):
        z=fvg_at(m5,k,opp)
        if z:return z
    return None

def generate_signals(symbol,rows,daily):
    m5=enrich(rows,300);m15=enrich(resample(rows,900),900);h1=enrich(resample(rows,3600),3600);h4=enrich(resample(rows,14400),14400);d1=enrich(daily,86400)
    out=[];last=defaultdict(lambda:-9999);sweeps={"LONG":None,"SHORT":None};breaks={"LONG":None,"SHORT":None};fails={"LONG":None,"SHORT":None};prev15=-1
    for i in range(250,len(rows)-MAX_HOLD_BARS-RETEST_BARS-2):
        ts=rows[i][0]+300;j15=tf_idx(m15,ts);j1=tf_idx(h1,ts);j4=tf_idx(h4,ts);jd=tf_idx(d1,ts)
        if min(j15,j1,j4,jd)<0:continue
        if j15!=prev15:
            prev15=j15
            for side,lv,ext in m15_sweeps(m15,j15):sweeps[side]=(ts,lv,ext)
            if j15>=12 and m15.atr14[j15] is not None:
                cur=m15.rows[j15];p=m15.rows[j15-12:j15];hi=max(x[2] for x in p);lo=min(x[3] for x in p);a=m15.atr14[j15];mid=(hi+lo)/2
                if cur[4]>hi+.05*a:breaks["LONG"]=(ts,hi)
                if cur[4]<lo-.05*a:breaks["SHORT"]=(ts,lo)
                if cur[2]>hi+.15*a and cur[4]<hi and cur[4]<mid:fails["SHORT"]=(ts,hi,cur[2])
                if cur[3]<lo-.15*a and cur[4]>lo and cur[4]>mid:fails["LONG"]=(ts,lo,cur[3])
        for side in ("LONG","SHORT"):
            disp=displacement(m5,i,side);gap=fvg_at(m5,i,side);h1side=trend(h1,j1)
            ctx={"session":session_label(ts),"htfAlignment":htf_alignment(side,d1,jd,h4,j4,h1,j1),"volRegime":vol_regime(h1,j1)}
            def emit(a,lv,st,z=None):
                if i-last[(a,side)]<COOLDOWN_BARS:return
                out.append({"symbol":symbol,"i":i,"ts":ts,"arch":a,"side":side,"level":lv,"structure":st,"fvg":z,"context":ctx});last[(a,side)]=i
            sw=sweeps[side]
            if sw and ts-sw[0]<=1800:
                if disp is not None:emit("A_SWEEP_MSS",disp,sw[2],gap)
                if gap is not None:emit("C_SWEEP_FVG",sum(gap)/2,sw[2],gap)
            if h1side==side and m15.ema20[j15] is not None and disp is not None:
                r=m15.rows[j15];e=m15.ema20[j15];ok=(side=="LONG" and r[3]<=e<r[4]) or (side=="SHORT" and r[2]>=e>r[4])
                if ok:emit("B_H1_PULLBACK_RECLAIM",disp,min(x[3] for x in rows[i-10:i+1]) if side=="LONG" else max(x[2] for x in rows[i-10:i+1]),gap)
            br=breaks[side]
            if br and 0<ts-br[0]<=3600 and h1side==side and disp is not None:
                r=m15.rows[j15];lv=br[1];ok=(side=="LONG" and r[3]<=lv<r[4]) or (side=="SHORT" and r[2]>=lv>r[4])
                if ok:emit("D_BREAK_RETEST_CONT",lv,min(x[3] for x in rows[i-12:i+1]) if side=="LONG" else max(x[2] for x in rows[i-12:i+1]),gap)
            fb=fails[side]
            if fb and ts-fb[0]<=1800 and disp is not None:emit("E_FAILED_BREAK_REV",disp,fb[2],gap)
            zg=opposite_gap(m5,i,side)
            if zg and disp is not None and ((side=="LONG" and rows[i][4]>zg[1]) or (side=="SHORT" and rows[i][4]<zg[0])):
                emit("F_IFVG_RECLAIM",sum(zg)/2,min(x[3] for x in rows[i-10:i+1]) if side=="LONG" else max(x[2] for x in rows[i-10:i+1]),zg)
    return out,m5

def entry_for(sig,m5,mode):
    i=sig["i"];side=sig["side"];a=m5.atr14[i]
    if a is None:return None
    if mode=="CLOSE":return i+1,m5.rows[i][4]
    if mode=="RETEST":
        lv=sig["level"]
        for k in range(i+1,min(len(m5.rows),i+5)):
            r=m5.rows[k];touch=r[3]<=lv+.15*a and r[2]>=lv-.15*a;ok=r[4]>=lv if side=="LONG" else r[4]<=lv
            if touch and ok:return k+1,r[4]
        return None
    z=sig.get("fvg")
    if not z:return None
    mid=sum(z)/2
    for k in range(i+1,min(len(m5.rows),i+5)):
        if m5.rows[k][3]<=mid<=m5.rows[k][2]:return k,mid
    return None
def simulate(sig,m5,entry_mode,stop_mode,rr):
    e=entry_for(sig,m5,entry_mode)
    if not e:return None
    ei,px=e
    if ei>=len(m5.rows)-1:return None
    side=sig["side"];a=m5.atr14[sig["i"]];st=float(sig["structure"]);raw=st-.05*a if side=="LONG" else st+.05*a;dist=px-raw if side=="LONG" else raw-px
    if dist<=0:return None
    if stop_mode=="STRUCTURE_ATR" and dist<.8*a:dist=.8*a
    sl=px-dist if side=="LONG" else px+dist;tp=px+rr*dist if side=="LONG" else px-rr*dist;mfe=mae=0.;result=None;outcome="TIMEOUT";xi=min(len(m5.rows)-1,ei+MAX_HOLD_BARS-1)
    for k in range(ei,min(len(m5.rows),ei+MAX_HOLD_BARS)):
        r=m5.rows[k];fav=(r[2]-px)/dist if side=="LONG" else (px-r[3])/dist;adv=(px-r[3])/dist if side=="LONG" else (r[2]-px)/dist;mfe=max(mfe,fav);mae=max(mae,adv)
        hit_sl=r[3]<=sl if side=="LONG" else r[2]>=sl;hit_tp=r[2]>=tp if side=="LONG" else r[3]<=tp
        if hit_sl:result=-1-COST_R;outcome="SL";xi=k;break
        if hit_tp:result=rr-COST_R;outcome="TP";xi=k;break
    if result is None:
        close=m5.rows[xi][4];mark=(close-px)/dist if side=="LONG" else (px-close)/dist;result=max(-1,min(rr,mark))-COST_R
    return {"r":result,"outcome":outcome,"mfe":mfe,"mae":mae,"entryI":ei,"exitI":xi,"session":sig["context"]["session"],"htfAlignment":sig["context"]["htfAlignment"],"volRegime":sig["context"]["volRegime"]}

def maxdd(rs):
    eq=peak=dd=0.
    for r in rs:eq+=r;peak=max(peak,eq);dd=max(dd,peak-eq)
    return dd
def streak(ts):
    best=cur=0
    for t in ts:
        cur=cur+1 if t["r"]<=0 else 0;best=max(best,cur)
    return best
def metrics(ts):
    if not ts:return {"n":0,"wr":0,"expectancyR":0,"profitFactor":0,"avgWinR":0,"avgLossR":0,"maxLosingStreak":0,"maxDrawdownR":0,"mfeR":0,"maeR":0,"hit1R":0,"hit2R":0,"timeoutRate":0}
    rs=[t["r"] for t in ts];pos=[r for r in rs if r>0];neg=[r for r in rs if r<0]
    return {"n":len(ts),"wr":round(100*sum(t["outcome"]=="TP" for t in ts)/len(ts),2),"expectancyR":round(mean(rs),4),"profitFactor":round(sum(pos)/abs(sum(neg)),3) if neg else 99.0,"avgWinR":round(mean(pos) or 0,4),"avgLossR":round(mean(neg) or 0,4),"maxLosingStreak":streak(ts),"maxDrawdownR":round(maxdd(rs),3),"mfeR":round(mean([t["mfe"] for t in ts]) or 0,3),"maeR":round(mean([t["mae"] for t in ts]) or 0,3),"hit1R":round(100*sum(t["mfe"]>=1 for t in ts)/len(ts),2),"hit2R":round(100*sum(t["mfe"]>=2 for t in ts)/len(ts),2),"timeoutRate":round(100*sum(t["outcome"]=="TIMEOUT" for t in ts)/len(ts),2)}
def grouped(ts,key):
    g=defaultdict(list)
    for t in ts:g[t[key]].append(t)
    return {k:metrics(v) for k,v in sorted(g.items())}
def vkey(a,e,s,r):return f"{a}|{e}|{s}|RR{r}"
def score(m):return -999 if m["n"]<20 else 3*m["expectancyR"]+.25*min(m["profitFactor"],3)+.002*m["wr"]-.03*m["maxDrawdownR"]-.01*m["maxLosingStreak"]

def research_pair(symbol,rows,daily):
    signals,m5=generate_signals(symbol,rows,daily);n=len(rows);c1=int(n*.6);c2=int(n*.8);variants={}
    for a in SETUP_DEFS:
      for e in ENTRY_MODES:
       for sm in STOP_MODES:
        for rr in RR_VALUES:
            trades=[];last_exit=-1
            for sig in signals:
                if sig["arch"]!=a or sig["i"]<last_exit:continue
                t=simulate(sig,m5,e,sm,rr)
                if t:trades.append(t);last_exit=t["exitI"]
            d=[t for t in trades if t["entryI"]<c1];v=[t for t in trades if c1<=t["entryI"]<c2];o=[t for t in trades if t["entryI"]>=c2]
            variants[vkey(a,e,sm,rr)]={"arch":a,"entry":e,"stop":sm,"rr":rr,"dev":metrics(d),"validation":metrics(v),"oos":metrics(o),"sessionValidation":grouped(v,"session"),"alignmentValidation":grouped(v,"htfAlignment"),"volValidation":grouped(v,"volRegime")}
    ordered=sorted(variants.values(),key=lambda x:score(x["dev"]),reverse=True);top=[{k:x[k] for k in ("arch","entry","stop","rr","dev","validation","oos")} for x in ordered[:5]]
    return {"symbol":symbol,"bars":n,"from":iso(datetime.fromtimestamp(rows[0][0],tz=timezone.utc)),"to":iso(datetime.fromtimestamp(rows[-1][0]+300,tz=timezone.utc)),"signalCount":len(signals),"variants":variants,"top5Dev":top}
def global_archetypes(results):
    stats={}
    for a in SETUP_DEFS:
        vals=[];dev=[]
        for r in results.values():
            choices=sorted([x for x in r["variants"].values() if x["arch"]==a],key=lambda x:score(x["dev"]),reverse=True)
            if not choices:continue
            x=choices[0];dev.append(x["dev"])
            if x["validation"]["n"]>=6:vals.append(x["validation"])
        good=sum(x["expectancyR"]>0 and x["profitFactor"]>1 for x in vals);ex=[x["expectancyR"] for x in vals]
        stats[a]={"symbolsWithValidation":len(vals),"validationPositive":good,"positiveShare":round(good/len(vals),3) if vals else 0,"medianValidationExpectancyR":round(statistics.median(ex),4) if ex else 0,"medianDevExpectancyR":round(statistics.median([x["expectancyR"] for x in dev]),4) if dev else 0}
    ranked=sorted(stats,key=lambda a:(stats[a]["positiveShare"],stats[a]["medianValidationExpectancyR"],stats[a]["symbolsWithValidation"]),reverse=True);keep=[a for a in ranked if stats[a]["symbolsWithValidation"]>=8 and stats[a]["positiveShare"]>=.5 and stats[a]["medianValidationExpectancyR"]>0][:4]
    return stats,keep or ranked[:2]
def lock_methods(results,retained):
    out={};counts=defaultdict(int)
    for s in PAIRS:
        choices=sorted([x for x in results[s]["variants"].values() if x["arch"] in retained],key=lambda x:score(x["dev"]),reverse=True);chosen=None
        for x in choices:
            d=x["dev"];v=x["validation"]
            if d["n"]>=20 and d["expectancyR"]>0 and d["profitFactor"]>1.05 and v["n"]>=6 and v["expectancyR"]>0 and v["profitFactor"]>1:chosen=x;break
        chosen=chosen or choices[0];v=chosen["validation"];o=chosen["oos"];live=v["n"]>=6 and v["expectancyR"]>0 and v["profitFactor"]>1 and o["n"]>=8 and o["expectancyR"]>.05 and o["profitFactor"]>=1.1 and o["maxDrawdownR"]<=8;status="OOS_PROMOTED" if live else "RESEARCH_ONLY";counts[status]+=1;counts[chosen["arch"]]+=1
        out[s]={"status":status,"liveEligible":live,"archetype":chosen["arch"],"entryMode":chosen["entry"],"stopMode":chosen["stop"],"rr":chosen["rr"],"selectedBy":"DEV_RANK_PLUS_VALIDATION_GATE","oosRole":"PROMOTION_CHECK_ONLY_NO_RETUNE","dev":chosen["dev"],"validation":v,"oos":o,"sessionValidation":chosen["sessionValidation"],"alignmentValidation":chosen["alignmentValidation"],"volValidation":chosen["volValidation"]}
    return out,dict(counts)

def self_test():
    assert len(PAIRS)==28 and len(SETUP_DEFS)==6 and len(ENTRY_MODES)*len(STOP_MODES)*len(RR_VALUES)==12
    print(json.dumps({"version":VERSION,"pairs":28,"setups":6,"variantsPerSetup":12,"selfTest":"PASS"}));return 0
def main(out_dir="data"):
    chunks=int(os.getenv("V76_CHUNKS","3"));pause=int(os.getenv("V76_QUOTA_PAUSE","62"));hist,daily,fetchlog=fetch_history(chunks,5000,pause);results={s:research_pair(s,hist[s],daily[s]) for s in PAIRS};stats,retained=global_archetypes(results);methods,counts=lock_methods(results,retained)
    pairs={s:{"bars":r["bars"],"from":r["from"],"to":r["to"],"signalCount":r["signalCount"],"selected":methods[s],"top5Dev":r["top5Dev"]} for s,r in results.items()}
    research={"version":VERSION,"generatedAt":iso(utcnow()),"scope":"FOREX_28","history":{"source":"Twelve Data exact Physical Currency","baseInterval":"5min","chunks":chunks,"maxPointsPerChunk":5000,"resampledLocally":["15min","1h","4h"],"dailyFetchedSeparately":True,"rawHistoryCommitted":False,"fetchLog":fetchlog},"protocol":{"split":"chronological 60/20/20","selection":"DEV ranking + VALIDATION gate; OOS promotion check only","costModelR":COST_R,"maxHoldM5Bars":MAX_HOLD_BARS,"sameBarTpSl":"SL","newsHistoricalFilter":"NOT_TESTED_NO_CANONICAL_TIMESTAMPED_EVENT_FEED","liveNewsGateStillRequired":True},"setups":SETUP_DEFS,"archetypeValidation":stats,"retainedArchetypes":retained,"pairResults":pairs,"limitations":["Historical broker bid/ask/spread unavailable; fixed 0.05R round-trip cost used.","Historical high-impact macro-event timestamps unavailable from canonical feed; before/after-news performance is not claimed.","OOS is only a one-time promotion gate; failed OOS methods are not retuned in this run."]}
    methodfile={"version":"V76-ENTRY-METHODS-R1","generatedAt":research["generatedAt"],"selectionFrozen":True,"selectionData":"DEV_PLUS_VALIDATION_ONLY","oosUsedFor":"PROMOTION_GATE_ONLY","retainedArchetypes":retained,"setupDefinitions":SETUP_DEFS,"promotionCriteria":{"validationMinN":6,"validationExpectancyR":">0","validationPF":">1.0","oosMinN":8,"oosExpectancyR":">0.05","oosPF":">=1.10","oosMaxDrawdownR":"<=8"},"costModelR":COST_R,"methods":methods,"counts":counts}
    os.makedirs(out_dir,exist_ok=True)
    for name,obj in (("v76_entry_research.json",research),("v76_entry_methods.json",methodfile)):
        with open(os.path.join(out_dir,name),"w",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,separators=(",",":"))
    print(json.dumps({"version":VERSION,"retained":retained,"counts":counts,"barsMin":min(len(hist[s]) for s in PAIRS),"barsMax":max(len(hist[s]) for s in PAIRS)},ensure_ascii=False));return 0
if __name__=="__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv else main(sys.argv[1] if len(sys.argv)>1 else "data"))
