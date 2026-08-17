#!/usr/bin/env python3
import json, math, os, statistics, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PAIRS=[
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"]
CCY=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]

# Locked unseen holdout dates. Repo search returned no prior exact references before this file was created.
VAL=[
"2026-07-31T08:00:00Z",
"2026-08-03T08:00:00Z",
"2026-08-07T08:00:00Z",
"2026-08-12T08:00:00Z",
"2026-08-14T08:00:00Z",
]
END_DATE="2026-08-15 08:00:00"
OUTPUTSIZE=5000
RR_MODES=[1.80,2.10]
BASE_RR=1.80
LIMIT_EXPIRY_H=4
TRADE_EXPIRY_H=24

# Technical profile is deliberately small: EMA, RSI, ATR, ADX.
# Macro drivers are handled live from official sources; historical F3 does not reconstruct news with hindsight.
PROFILE={
"USD":{"minAdx":17.0,"maxChase":0.82,"riskFloor":1.00,"strict24":False,
       "drivers":["Fed/rate path","PCE-CPI","labour/NFP","US yields"]},
"EUR":{"minAdx":17.0,"maxChase":0.80,"riskFloor":1.00,"strict24":False,
       "drivers":["ECB/rate path","HICP/core","wages/services","energy-growth"]},
"GBP":{"minAdx":18.0,"maxChase":0.72,"riskFloor":1.10,"strict24":False,
       "drivers":["BoE/rate path","CPI/services","wages","UK growth"]},
"JPY":{"minAdx":20.0,"maxChase":0.62,"riskFloor":1.05,"strict24":True,
       "drivers":["BoJ/rate path","wages/core CPI","JGB yields","MOF intervention/carry"]},
"CHF":{"minAdx":20.0,"maxChase":0.60,"riskFloor":1.05,"strict24":True,
       "drivers":["SNB/rate path","Swiss inflation","SNB FX intervention","risk-off"]},
"CAD":{"minAdx":18.0,"maxChase":0.72,"riskFloor":1.05,"strict24":True,
       "drivers":["BoC/rate path","CPI/jobs","oil","US trade/growth"]},
"AUD":{"minAdx":18.0,"maxChase":0.72,"riskFloor":1.10,"strict24":False,
       "drivers":["RBA/rate path","trimmed inflation","labour","China/commodities/risk"]},
"NZD":{"minAdx":18.0,"maxChase":0.68,"riskFloor":1.10,"strict24":False,
       "drivers":["RBNZ/OCR","CPI","spare capacity/labour","dairy/global rates"]},
}

def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def ema(v,n):
    if not v:return None
    a=2/(n+1); x=v[0]
    for z in v[1:]:x=a*z+(1-a)*x
    return x

def rsi(v,n=14):
    if len(v)<n+1:return None
    ds=[b-a for a,b in zip(v[-n-1:-1],v[-n:])]
    g=sum(max(x,0) for x in ds)/n
    l=sum(max(-x,0) for x in ds)/n
    return 100 if l==0 else 100-100/(1+g/l)

def atr(rows,n=14):
    if len(rows)<n+1:return None
    x=rows[-n-1:]; tr=[]
    for i in range(1,len(x)):
        p=x[i-1]["close"]; q=x[i]
        tr.append(max(q["high"]-q["low"],abs(q["high"]-p),abs(q["low"]-p)))
    return sum(tr)/len(tr)

def adx(rows,n=14):
    if len(rows)<2*n+2:return None
    x=rows[-(2*n+2):]
    trs=[]; plus=[]; minus=[]
    for i in range(1,len(x)):
        cur=x[i]; prev=x[i-1]
        up=cur["high"]-prev["high"]
        dn=prev["low"]-cur["low"]
        plus.append(up if up>dn and up>0 else 0.0)
        minus.append(dn if dn>up and dn>0 else 0.0)
        trs.append(max(cur["high"]-cur["low"],abs(cur["high"]-prev["close"]),abs(cur["low"]-prev["close"])))
    if len(trs)<n:return None
    dx=[]
    for end in range(n,len(trs)+1):
        tr=sum(trs[end-n:end])
        if tr<=0: continue
        p=100*sum(plus[end-n:end])/tr
        m=100*sum(minus[end-n:end])/tr
        den=p+m
        dx.append(0 if den<=1e-12 else 100*abs(p-m)/den)
    return statistics.mean(dx[-n:]) if dx else 0.0

def bucket(t,h): return t.replace(hour=(t.hour//h)*h,minute=0,second=0,microsecond=0)
def agg(rows,h):
    d=defaultdict(list); exp=h*4
    for r in rows:d[bucket(r["dt"],h)].append(r)
    out=[]
    for t in sorted(d):
        g=d[t]
        if len(g)<max(1,exp-1):continue
        out.append({"dt":t,"open":g[0]["open"],"high":max(x["high"] for x in g),
                    "low":min(x["low"] for x in g),"close":g[-1]["close"]})
    return out

def before(rows,t):
    x=None
    for r in rows:
        if r["dt"]<=t:x=r["close"]
        else:break
    return x

def zmap(d):
    if len(d)<2:return {k:0 for k in d}
    m=statistics.mean(d.values()); s=statistics.pstdev(d.values())
    return {k:(v-m)/s if s>1e-12 else 0 for k,v in d.items()}

def parse_batch(p):
    out={}
    if isinstance(p,dict) and "values" not in p:
        for k,v in p.items():
            if not isinstance(v,dict):continue
            q=v.get("data") if isinstance(v.get("data"),dict) else v
            if isinstance(q,dict) and q.get("values"):
                s=((q.get("meta") or {}).get("symbol") or k).replace("/","").upper()
                out[s]=q
    return out

def fetch():
    key=os.environ.get("TWELVEDATA_API_KEY","").strip()
    if not key:raise RuntimeError("TWELVEDATA_API_KEY missing")
    out={}; groups=[PAIRS[i:i+7] for i in range(0,28,7)]
    for i,g in enumerate(groups):
        syms=",".join(f"{p[:3]}/{p[3:]}" for p in g)
        qs=urllib.parse.urlencode({
            "symbol":syms,"interval":"15min","outputsize":OUTPUTSIZE,
            "end_date":END_DATE,"timezone":"UTC","order":"asc","apikey":key})
        req=urllib.request.Request(
            "https://api.twelvedata.com/time_series?"+qs,
            headers={"User-Agent":"trading-api-forex-f3/1.0"})
        with urllib.request.urlopen(req,timeout=120) as z:
            p=json.loads(z.read().decode())
        got=parse_batch(p); miss=[x for x in g if x not in got]
        if miss:raise RuntimeError(f"batch {i+1} missing {miss}: {str(p)[:2500]}")
        out.update(got); print(f"Fetched {i+1}/4: {','.join(g)}")
        if i<3:time.sleep(66)
    return out

def norm(x):
    o=[]
    for r in x["values"]:
        t=datetime.fromisoformat(r["datetime"]).replace(tzinfo=timezone.utc)
        o.append({"dt":t,"open":float(r["open"]),"high":float(r["high"]),
                  "low":float(r["low"]),"close":float(r["close"])})
    return sorted(o,key=lambda q:q["dt"])

def strength(frames,cut):
    hs=[6,24,72]; raw={h:{} for h in hs}
    for p,rows in frames.items():
        pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
        if not pre:continue
        now=pre[-1]["close"]
        for h in hs:
            old=before(pre,cut-timedelta(hours=h))
            if old and old>0:raw[h][p]=math.log(now/old)
    zz={h:zmap(raw[h]) for h in hs}
    ans={h:{c:[] for c in CCY} for h in hs}
    for h in hs:
        for p,v in zz[h].items():
            b,q=p[:3],p[3:]
            ans[h][b].append(v); ans[h][q].append(-v)
    return {h:{c:(statistics.mean(v) if v else 0) for c,v in ans[h].items()} for h in hs}

def pair_profile(pair):
    a=PROFILE[pair[:3]]; b=PROFILE[pair[3:]]
    return {
        "minAdx":max(a["minAdx"],b["minAdx"]),
        "maxChase":min(a["maxChase"],b["maxChase"]),
        "riskFloor":max(a["riskFloor"],b["riskFloor"]),
        "strict24":a["strict24"] or b["strict24"],
    }

def feat(pair,rows,cut,st):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<450:return None
    h1=agg(pre,1); h4=agg(pre,4)
    if len(h1)<80 or len(h4)<60:return None

    c=pre[-1]["close"]; a15=atr(pre); hc=[x["close"] for x in h1]
    h4c=[x["close"] for x in h4]; mc=[x["close"] for x in pre]
    if not a15:return None

    e4_20=ema(h4c[-100:],20); e4_50=ema(h4c[-140:],50); e4_prev=ema(h4c[-103:-3],20)
    e1_20=ema(hc[-100:],20); e1_50=ema(hc[-140:],50); e1_prev=ema(hc[-103:-3],20)
    er=rsi(hc); ax=adx(h1); em=ema(mc[-100:],20)
    if None in (e4_20,e4_50,e4_prev,e1_20,e1_50,e1_prev,er,ax,em):return None

    b,q=pair[:3],pair[3:]
    d6=st[6][b]-st[6][q]; d24=st[24][b]-st[24][q]; d72=st[72][b]-st[72][q]

    h4s=(1.25 if c>e4_20>e4_50 else -1.25 if c<e4_20<e4_50 else 0)
    h4s+=(0.40 if e4_20>e4_prev else -0.40)
    h1s=(1.00 if c>e1_20>e1_50 else -1.00 if c<e1_20<e1_50 else 0)
    h1s+=(0.45 if e1_20>e1_prev else -0.45)
    if er>=55:h1s+=0.25
    elif er<=45:h1s-=0.25

    mom4=(c-mc[-5])/a15
    m15s=(0.30 if c>em else -0.30)+(0.30 if mom4>=0 else -0.30)
    score=1.10*d6+0.80*d24+0.45*d72+h4s+h1s+m15s
    side="BUY" if score>=0 else "SELL"; s=1 if side=="BUY" else -1

    agree=sum((x*s)>0 for x in (d6,d24,d72))
    chase=abs(c-em)/a15
    p=pair_profile(pair)
    h4a=h4s*s>0; h1a=h1s*s>0; m15a=m15s*s>0
    slope=(e1_20-e1_prev)*s>0
    rsi_ok=(46<=er<=68) if side=="BUY" else (32<=er<=54)
    mom_ok=(mom4*s)>=0.03 and abs(mom4)<=1.20
    adx_ok=ax>=p["minAdx"]
    strict_ok=(d24*s>0) if p["strict24"] else True

    recent=pre[-10:]
    structure=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    rawrisk=(c-structure+0.12*a15) if side=="BUY" else (structure-c+0.12*a15)
    risk=max(rawrisk,p["riskFloor"]*a15)
    sl=c-risk if side=="BUY" else c+risk
    ratr=risk/a15

    mag=abs(score)
    sweet=max(0,1.20-abs(mag-3.8)*0.28)
    quality=sweet+(1.0 if h4a else 0)+(0.9 if h1a else 0)+(0.45 if m15a else 0)
    quality+=(0.55 if agree==3 else 0.20 if agree==2 else -0.8)
    quality+=min(0.6,max(0,(ax-p["minAdx"])/15))
    if chase>p["maxChase"]:quality-=1.2
    if mag>6.3:quality-=0.9
    if not rsi_ok:quality-=0.8

    ok=(1.8<=mag<=6.3 and agree>=2 and d6*s>0 and strict_ok and h4a and h1a and slope
        and m15a and rsi_ok and mom_ok and adx_ok and chase<=p["maxChase"] and ratr<=2.35)

    # Execution classification is locked before future candles:
    # clean continuation near value => MARKET; otherwise controlled pullback => LIMIT.
    execution="MARKET" if ok and chase<=0.42 and ax>=p["minAdx"]+1.5 else "LIMIT"

    return {
        "symbol":pair,"side":side,"entry":c,"sl":sl,"risk":risk,
        "score":round(score,4),"quality":round(quality,4),
        "d6":round(d6,3),"d24":round(d24,3),"d72":round(d72,3),
        "agree":agree,"h1Rsi":round(er,2),"h1Adx":round(ax,2),
        "mom4ATR":round(mom4,3),"chaseATR":round(chase,3),
        "riskATR":round(ratr,3),"m15Ema20":em,
        "selectiveOK":ok,"execution":execution
    }

def market(f,rows,cut,rr):
    side=f["side"]; en=f["entry"]; sl=f["sl"]; risk=f["risk"]
    tp=en+risk*rr if side=="BUY" else en-risk*rr
    end=cut+timedelta(hours=TRADE_EXPIRY_H)
    fut=[r for r in rows if cut<=r["dt"]<end]
    for i,r in enumerate(fut,1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl
        b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:return {"result":"AMBIGUOUS","bars":i,"rr":rr,"tp":tp}
        if a:return {"result":"SL","bars":i,"rr":rr,"tp":tp}
        if b:return {"result":"TP","bars":i,"rr":rr,"tp":tp}
    return {"result":"TIMEOUT","bars":len(fut),"rr":rr,"tp":tp}

def limit_price(f):
    side=f["side"]; en=f["entry"]; sl=f["sl"]; risk=f["risk"]; em=f["m15Ema20"]
    structural = (sl<em<en) if side=="BUY" else (en<em<sl)
    lim=em if structural else (en-0.22*risk if side=="BUY" else en+0.22*risk)
    improvement=(en-lim)/risk if side=="BUY" else (lim-en)/risk
    if improvement<0.10:
        lim=en-0.18*risk if side=="BUY" else en+0.18*risk
    max_pb=0.45
    pb=(en-lim)/risk if side=="BUY" else (lim-en)/risk
    if pb>max_pb:
        lim=en-max_pb*risk if side=="BUY" else en+max_pb*risk
    return lim

def limit(f,rows,cut,rr):
    side=f["side"]; en=f["entry"]; sl=f["sl"]; risk=f["risk"]
    tp=en+risk*rr if side=="BUY" else en-risk*rr
    lim=limit_price(f)
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_EXPIRY_H)]
    fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=LIMIT_EXPIRY_H):break
        tgt=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        fill=r["low"]<=lim if side=="BUY" else r["high"]>=lim
        if tgt and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False,"limit":lim}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False,"limit":lim}

    lr=abs(lim-sl); eff=abs(tp-lim)/lr if lr else None
    for j,r in enumerate(fut[fi:],1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl
        b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:return {"result":"AMBIGUOUS","filled":True,"effectiveRR":eff,"bars":j,"limit":lim}
        if a:return {"result":"SL","filled":True,"effectiveRR":eff,"bars":j,"limit":lim}
        if b:return {"result":"TP","filled":True,"effectiveRR":eff,"bars":j,"limit":lim}
    return {"result":"TIMEOUT","filled":True,"effectiveRR":eff,"bars":len(fut)-fi,"limit":lim}

def sm(rows,rr):
    res=[x for x in rows if x["outcome"]["result"] in ("TP","SL")]
    w=sum(x["outcome"]["result"]=="TP" for x in res); l=len(res)-w
    return {"signals":len(rows),"resolved":len(res),"wins":w,"losses":l,
            "timeouts":sum(x["outcome"]["result"]=="TIMEOUT" for x in rows),
            "ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in rows),
            "winRateResolved":round(100*w/len(res),2) if res else None,
            "rr":rr,"expectancyR":round((w*rr-l)/len(res),3) if res else None}

def slm(rows):
    fills=[x for x in rows if x["outcome"].get("filled")]
    res=[x for x in fills if x["outcome"]["result"] in ("TP","SL")]
    w=sum(x["outcome"]["result"]=="TP" for x in res); l=len(res)-w
    rrs=[x["outcome"].get("effectiveRR") for x in res if x["outcome"].get("effectiveRR")]
    total=sum((x["outcome"].get("effectiveRR",0) if x["outcome"]["result"]=="TP" else -1) for x in res)
    return {"signals":len(rows),"fills":len(fills),
            "fillRate":round(100*len(fills)/len(rows),2) if rows else None,
            "resolved":len(res),"wins":w,"losses":l,
            "noFill":sum(x["outcome"]["result"]=="NO_FILL" for x in rows),
            "targetBeforeFill":sum(x["outcome"]["result"]=="TARGET_BEFORE_FILL" for x in rows),
            "timeoutsAfterFill":sum(x["outcome"]["result"]=="TIMEOUT" and x["outcome"].get("filled") for x in rows),
            "ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in rows),
            "winRateResolved":round(100*w/len(res),2) if res else None,
            "avgEffectiveRR":round(statistics.mean(rrs),3) if rrs else None,
            "expectancyR":round(total/len(res),3) if res else None}

def sumhy(rows,rr):
    res=[x for x in rows if x["outcome"]["result"] in ("TP","SL")]
    w=sum(x["outcome"]["result"]=="TP" for x in res); total=0
    for x in res:
        total += x["outcome"].get("effectiveRR",rr) if x["outcome"]["result"]=="TP" else -1
    return {"signals":len(rows),"resolved":len(res),"wins":w,"losses":len(res)-w,
            "noPosition":sum(x["outcome"]["result"] in ("NO_FILL","TARGET_BEFORE_FILL") for x in rows),
            "winRateResolved":round(100*w/len(res),2) if res else None,
            "expectancyR":round(total/len(res),3) if res else None}

def pick(fs):
    e=sorted([x for x in fs if x["selectiveOK"]],key=lambda x:x["quality"],reverse=True)
    out=[]; used=set()
    for f in e:
        b,q=f["symbol"][:3],f["symbol"][3:]
        if b in used or q in used:continue
        out.append(f); used|={b,q}
        if len(out)==3:break
    return out

def block(frames,c,rr):
    st=strength(frames,c)
    fs=[x for p in PAIRS if (x:=feat(p,frames[p],c,st))]
    forced=[{"feature":f,"outcome":market(f,frames[f["symbol"]],c,rr)} for f in fs]
    top=pick(fs)
    mk=[{"feature":f,"outcome":market(f,frames[f["symbol"]],c,rr)} for f in top]
    lm=[{"feature":f,"outcome":limit(f,frames[f["symbol"]],c,rr)} for f in top]
    hy=[]
    for f,m,l in zip(top,mk,lm):
        hy.append(m if f["execution"]=="MARKET" else l)
    return {"forced":forced,"market":mk,"limit":lm,"hybrid":hy,"top":top,"strength":st}

def flat(bs,k):return [x for b in bs.values() for x in b[k]]

def currency_stats(rows):
    stats={c:{"resolved":0,"wins":0,"losses":0} for c in CCY}
    for x in rows:
        r=x["outcome"]["result"]
        if r not in ("TP","SL"):continue
        p=x["feature"]["symbol"]; b,q=p[:3],p[3:]
        for c in (b,q):
            stats[c]["resolved"]+=1
            if r=="TP":stats[c]["wins"]+=1
            else:stats[c]["losses"]+=1
    for c,s in stats.items():
        s["winRateResolved"]=round(100*s["wins"]/s["resolved"],2) if s["resolved"] else None
    return stats

def phase(bs,rr):
    forced=flat(bs,"forced"); market_rows=flat(bs,"market"); limit_rows=flat(bs,"limit"); hybrid=flat(bs,"hybrid")
    return {
        "forcedMarket":sm(forced,rr),
        "selectiveMarket":sm(market_rows,rr),
        "selectiveLimit":slm(limit_rows),
        "selectiveHybrid":sumhy(hybrid,rr),
        "currencyStatsForced":currency_stats(forced),
        "currencyStatsSelective":currency_stats(market_rows),
    }

def main():
    raw=fetch()
    frames={p:norm(raw[p]) for p in PAIRS}
    results_by_rr={}
    all_blocks={}
    for rr in RR_MODES:
        bs={c:block(frames,dt(c),rr) for c in VAL}
        all_blocks[rr]=bs
        results_by_rr[str(rr)]=phase(bs,rr)

    base=all_blocks[BASE_RR]
    result={
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "method":"FOREX F3 currency-profile + minimal-indicator blind holdout. Technical stack limited to EMA20/50, RSI14, ATR14, ADX14 plus 6h/24h/72h cross-currency strength. Currency-specific profiles adjust trend-strength, chase and volatility gates for USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD; macro/news drivers are documented for live use but are NOT reconstructed historically to avoid hindsight. H4/H1 alignment + M15 setup define direction and structure SL. Continuation near value is MARKET; controlled pullback uses structural M15 EMA20 LIMIT or capped 0.22R fallback, 4h expiry. Five exact cutoff strings were repo-searched and absent before F3 creation. RR 1.8 and 2.1 are both predeclared; 1.8 is baseline, not selected after outcomes.",
        "integrity":{
            "lookAheadForDecision":False,
            "rulesFrozenBeforeValidation":True,
            "validationDatesPreviouslyAbsentFromRepo":True,
            "macroHistoricalReconstructionUsed":False
        },
        "dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","pairs":28,
                    "creditsExpected":28,"outputsize":OUTPUTSIZE,"rawCommitted":False},
        "validationCutoffs":VAL,
        "currencyProfiles":PROFILE,
        "rrResults":results_by_rr,
        "baselineRR":BASE_RR,
        "baselineByCutoff":{}
    }
    for c,b in base.items():
        result["baselineByCutoff"][c]={
            "forced":sm(b["forced"],BASE_RR),
            "market":sm(b["market"],BASE_RR),
            "limit":slm(b["limit"]),
            "hybrid":sumhy(b["hybrid"],BASE_RR),
            "top":[{"symbol":x["symbol"],"side":x["side"],"execution":x["execution"],
                    "score":x["score"],"quality":x["quality"],"rsi":x["h1Rsi"],
                    "adx":x["h1Adx"],"chaseATR":x["chaseATR"],"riskATR":x["riskATR"],
                    "d6":x["d6"],"d24":x["d24"],"d72":x["d72"]} for x in b["top"]]
        }

    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f3.json","w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({"baselineRR":BASE_RR,"rrResults":results_by_rr,
                      "baselineByCutoff":result["baselineByCutoff"]},indent=2))

if __name__=="__main__":
    main()
