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
DEV=["2026-07-15T08:00:00Z","2026-07-16T08:00:00Z","2026-07-23T08:00:00Z","2026-07-29T08:00:00Z","2026-07-30T08:00:00Z"]
VAL=["2026-08-04T08:00:00Z","2026-08-05T08:00:00Z","2026-08-06T08:00:00Z","2026-08-10T08:00:00Z","2026-08-11T08:00:00Z"]
RR_GRID=[1.30,1.50,1.70,1.90,2.10]
END_DATE="2026-08-12 08:00:00"; OUTPUTSIZE=5000
LIMIT_PULLBACK_R=.25; LIMIT_EXPIRY_H=4; TRADE_EXPIRY_H=24

def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def ema(v,n):
    if not v:return None
    a=2/(n+1); x=v[0]
    for z in v[1:]:x=a*z+(1-a)*x
    return x

def rsi(v,n=14):
    if len(v)<n+1:return None
    ds=[b-a for a,b in zip(v[-n-1:-1],v[-n:])]; g=sum(max(x,0) for x in ds)/n; l=sum(max(-x,0) for x in ds)/n
    return 100 if l==0 else 100-100/(1+g/l)
def atr(r,n=14):
    if len(r)<n+1:return None
    x=r[-n-1:]; tr=[]
    for i in range(1,len(x)):
        p=x[i-1]["close"]; q=x[i]; tr.append(max(q["high"]-q["low"],abs(q["high"]-p),abs(q["low"]-p)))
    return sum(tr)/len(tr)
def bucket(t,h): return t.replace(hour=(t.hour//h)*h,minute=0,second=0,microsecond=0)
def agg(rows,h):
    d=defaultdict(list); exp=h*4
    for r in rows:d[bucket(r["dt"],h)].append(r)
    out=[]
    for t in sorted(d):
        g=d[t]
        if len(g)<max(1,exp-1):continue
        out.append({"dt":t,"open":g[0]["open"],"high":max(x["high"] for x in g),"low":min(x["low"] for x in g),"close":g[-1]["close"]})
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
                s=((q.get("meta") or {}).get("symbol") or k).replace("/","").upper(); out[s]=q
    return out

def fetch():
    key=os.environ.get("TWELVEDATA_API_KEY","").strip()
    if not key:raise RuntimeError("TWELVEDATA_API_KEY missing")
    out={}; groups=[PAIRS[i:i+7] for i in range(0,28,7)]
    for i,g in enumerate(groups):
        syms=",".join(f"{p[:3]}/{p[3:]}" for p in g)
        qs=urllib.parse.urlencode({"symbol":syms,"interval":"15min","outputsize":OUTPUTSIZE,"end_date":END_DATE,"timezone":"UTC","order":"asc","apikey":key})
        req=urllib.request.Request("https://api.twelvedata.com/time_series?"+qs,headers={"User-Agent":"trading-api-forex-f2/1.0"})
        with urllib.request.urlopen(req,timeout=100) as z:p=json.loads(z.read().decode())
        got=parse_batch(p); miss=[x for x in g if x not in got]
        if miss:raise RuntimeError(f"batch {i+1} missing {miss}: {str(p)[:2500]}")
        out.update(got); print(f"Fetched {i+1}/4: {','.join(g)}")
        if i<3:time.sleep(66)
    return out

def norm(x):
    o=[]
    for r in x["values"]:
        t=datetime.fromisoformat(r["datetime"]).replace(tzinfo=timezone.utc)
        o.append({"dt":t,"open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"])})
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
    zz={h:zmap(raw[h]) for h in hs}; ans={h:{c:[] for c in CCY} for h in hs}
    for h in hs:
        for p,v in zz[h].items():
            b,q=p[:3],p[3:]; ans[h][b].append(v); ans[h][q].append(-v)
    return {h:{c:(statistics.mean(v) if v else 0) for c,v in ans[h].items()} for h in hs}

def feat(pair,rows,cut,st):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<450:return None
    h1=agg(pre,1); h4=agg(pre,4)
    if len(h1)<80 or len(h4)<60:return None
    c=pre[-1]["close"]; a15=atr(pre); hc=[x["close"] for x in h1]; h4c=[x["close"] for x in h4]; mc=[x["close"] for x in pre]
    if not a15:return None
    e4_20=ema(h4c[-100:],20); e4_50=ema(h4c[-140:],50); e4_prev=ema(h4c[-103:-3],20)
    e1_20=ema(hc[-100:],20); e1_50=ema(hc[-140:],50); e1_prev=ema(hc[-103:-3],20); er=rsi(hc); em=ema(mc[-100:],20)
    if None in (e4_20,e4_50,e4_prev,e1_20,e1_50,e1_prev,er,em):return None
    b,q=pair[:3],pair[3:]; d6=st[6][b]-st[6][q]; d24=st[24][b]-st[24][q]; d72=st[72][b]-st[72][q]
    h4s=(1.35 if c>e4_20>e4_50 else -1.35 if c<e4_20<e4_50 else 0)+(0.45 if e4_20>e4_prev else -0.45)
    h1s=(1.05 if c>e1_20>e1_50 else -1.05 if c<e1_20<e1_50 else 0)+(0.45 if e1_20>e1_prev else -0.45)
    if er>=55:h1s+=.30
    elif er<=45:h1s-=.30
    mom4=(c-mc[-5])/a15
    m15s=(.35 if c>em else -.35)+(.30 if mom4>=0 else -.30)
    score=1.15*d6+.75*d24+.40*d72+h4s+h1s+m15s
    side="BUY" if score>=0 else "SELL"; s=1 if side=="BUY" else -1
    agree=sum((x*s)>0 for x in (d6,d24,d72)); chase=abs(c-em)/a15
    h4a=h4s*s>0; h1a=h1s*s>0; m15a=m15s*s>0; slope=(e1_20-e1_prev)*s>0
    rsi_ok=(48<=er<=67.5) if side=="BUY" else (32.5<=er<=52)
    mom_ok=(mom4*s)>=.05 and abs(mom4)<=1.10
    recent=pre[-8:]
    structure=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    rawrisk=(c-structure+.15*a15) if side=="BUY" else (structure-c+.15*a15); risk=max(rawrisk,a15); sl=c-risk if side=="BUY" else c+risk; ratr=risk/a15
    mag=abs(score); sweet=max(0,1.2-abs(mag-4.0)*.30)
    quality=sweet+(1 if h4a else 0)+(.9 if h1a else 0)+(.5 if m15a else 0)+(.5 if agree==3 else .2 if agree==2 else -.8)
    if chase>.95:quality-=1.2
    if mag>6:quality-=1.0
    if not rsi_ok:quality-=.8
    ok=(2.1<=mag<=6.0 and agree>=2 and d6*s>0 and h4a and h1a and slope and m15a and rsi_ok and mom_ok and chase<=.95 and ratr<=2.25)
    return {"symbol":pair,"side":side,"entry":c,"sl":sl,"risk":risk,"score":round(score,4),"quality":round(quality,4),"d6":round(d6,3),"d24":round(d24,3),"d72":round(d72,3),"agree":agree,"h1Rsi":round(er,2),"mom4ATR":round(mom4,3),"chaseATR":round(chase,3),"riskATR":round(ratr,3),"selectiveOK":ok}

def market(f,rows,cut,rr):
    side=f["side"]; en=f["entry"]; sl=f["sl"]; risk=f["risk"]; tp=en+risk*rr if side=="BUY" else en-risk*rr; end=cut+timedelta(hours=TRADE_EXPIRY_H)
    fut=[r for r in rows if cut<=r["dt"]<end]
    for i,r in enumerate(fut,1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl; b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:return {"result":"AMBIGUOUS","bars":i,"rr":rr,"tp":tp}
        if a:return {"result":"SL","bars":i,"rr":rr,"tp":tp}
        if b:return {"result":"TP","bars":i,"rr":rr,"tp":tp}
    return {"result":"TIMEOUT","bars":len(fut),"rr":rr,"tp":tp}
def limit(f,rows,cut,rr):
    side=f["side"]; en=f["entry"]; sl=f["sl"]; risk=f["risk"]; tp=en+risk*rr if side=="BUY" else en-risk*rr; lim=en-LIMIT_PULLBACK_R*risk if side=="BUY" else en+LIMIT_PULLBACK_R*risk
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_EXPIRY_H)]; fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=LIMIT_EXPIRY_H):break
        tgt=r["high"]>=tp if side=="BUY" else r["low"]<=tp; fill=r["low"]<=lim if side=="BUY" else r["high"]>=lim
        if tgt and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False}
    lr=abs(lim-sl); eff=abs(tp-lim)/lr if lr else None
    for j,r in enumerate(fut[fi:],1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl; b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:return {"result":"AMBIGUOUS","filled":True,"effectiveRR":eff,"bars":j}
        if a:return {"result":"SL","filled":True,"effectiveRR":eff,"bars":j}
        if b:return {"result":"TP","filled":True,"effectiveRR":eff,"bars":j}
    return {"result":"TIMEOUT","filled":True,"effectiveRR":eff,"bars":len(fut)-fi}
def sm(rows,rr):
    res=[x for x in rows if x["outcome"]["result"] in ("TP","SL")]; w=sum(x["outcome"]["result"]=="TP" for x in res); l=len(res)-w
    return {"signals":len(rows),"resolved":len(res),"wins":w,"losses":l,"timeouts":sum(x["outcome"]["result"]=="TIMEOUT" for x in rows),"ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in rows),"winRateResolved":round(100*w/len(res),2) if res else None,"rr":rr,"expectancyR":round((w*rr-l)/len(res),3) if res else None}
def slm(rows):
    fills=[x for x in rows if x["outcome"].get("filled")]; res=[x for x in fills if x["outcome"]["result"] in ("TP","SL")]; w=sum(x["outcome"]["result"]=="TP" for x in res); l=len(res)-w; rrs=[x["outcome"].get("effectiveRR") for x in res if x["outcome"].get("effectiveRR")]
    total=sum((x["outcome"].get("effectiveRR",0) if x["outcome"]["result"]=="TP" else -1) for x in res)
    return {"signals":len(rows),"fills":len(fills),"fillRate":round(100*len(fills)/len(rows),2) if rows else None,"resolved":len(res),"wins":w,"losses":l,"noFill":sum(x["outcome"]["result"]=="NO_FILL" for x in rows),"targetBeforeFill":sum(x["outcome"]["result"]=="TARGET_BEFORE_FILL" for x in rows),"winRateResolved":round(100*w/len(res),2) if res else None,"avgEffectiveRR":round(statistics.mean(rrs),3) if rrs else None,"expectancyR":round(total/len(res),3) if res else None}
def pick(fs):
    e=sorted([x for x in fs if x["selectiveOK"]],key=lambda x:x["quality"],reverse=True); out=[]; used=set()
    for f in e:
        b,q=f["symbol"][:3],f["symbol"][3:]
        if b in used or q in used:continue
        out.append(f);used|={b,q}
        if len(out)==3:break
    return out
def block(frames,c,rr):
    st=strength(frames,c); fs=[x for p in PAIRS if (x:=feat(p,frames[p],c,st))]
    forced=[{"feature":f,"outcome":market(f,frames[f["symbol"]],c,rr)} for f in fs]; top=pick(fs)
    mk=[{"feature":f,"outcome":market(f,frames[f["symbol"]],c,rr)} for f in top]; lm=[{"feature":f,"outcome":limit(f,frames[f["symbol"]],c,rr)} for f in top]
    # Execution classifier: clean/near EMA continuation -> MARKET; stretched but still valid -> LIMIT.
    hy=[]
    for m,l in zip(mk,lm):
        use_limit=m["feature"]["chaseATR"]>=.55
        hy.append(l if use_limit else m)
    return {"forced":forced,"market":mk,"limit":lm,"hybrid":hy,"top":top}
def flat(bs,k):return [x for b in bs.values() for x in b[k]]
def sumhy(rows,rr):
    # Hybrid mixes MARKET and LIMIT outcomes; score each resolved win by its actual RR.
    res=[x for x in rows if x["outcome"]["result"] in ("TP","SL")];w=sum(x["outcome"]["result"]=="TP" for x in res); total=0
    for x in res:
        if x["outcome"]["result"]=="TP":total+=x["outcome"].get("effectiveRR",rr)
        else:total-=1
    return {"signals":len(rows),"resolved":len(res),"wins":w,"losses":len(res)-w,"winRateResolved":round(100*w/len(res),2) if res else None,"expectancyR":round(total/len(res),3) if res else None}

def main():
    raw=fetch(); frames={p:norm(raw[p]) for p in PAIRS}
    grid={}; cache={}
    for rr in RR_GRID:
        bs={c:block(frames,dt(c),rr) for c in DEV};cache[rr]=bs;grid[str(rr)]={"forced":sm(flat(bs,"forced"),rr),"top3Market":sm(flat(bs,"market"),rr),"hybrid":sumhy(flat(bs,"hybrid"),rr)}
    viable=[]
    for rr in RR_GRID:
        s=grid[str(rr)]["forced"]
        if s["resolved"]>=100 and s["expectancyR"] is not None:viable.append((s["expectancyR"],-rr,rr))
    chosen=max(viable)[-1] if viable else 1.5
    dev=cache[chosen]; val={c:block(frames,dt(c),chosen) for c in VAL}
    def phase(bs):return {"forcedMarket":sm(flat(bs,"forced"),chosen),"top3Market":sm(flat(bs,"market"),chosen),"top3Limit":slm(flat(bs,"limit")),"top3Hybrid":sumhy(flat(bs,"hybrid"),chosen)}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"FOREX F2 anti-crowding/anti-exhaustion. One Twelve Data M15 series per pair. Derive 6h/24h/72h cross-currency strength plus H4/H1 locally. July revealed block is development only. Validation uses untouched Aug04/05/06/10/11. Top3 requires 2-of-3 horizon agreement, 6h confirmation, H4/H1 alignment and slope, moderate RSI, M15 confirmation, anti-chase and structural-risk gates. Extreme score is penalized rather than rewarded. No currency may appear twice in Top3. Structural SL first. RR chosen from development forced-market sample only. LIMIT is fixed 0.25R pullback; hybrid uses LIMIT only when chase >=0.55 ATR.","dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","pairs":28,"creditsExpected":28,"outputsize":OUTPUTSIZE,"rawCommitted":False},"developmentCutoffs":DEV,"validationCutoffs":VAL,"rrGrid":grid,"chosenRR":chosen,"developmentSummary":phase(dev),"validationSummary":phase(val),"validationByCutoff":{}}
    for c,b in val.items():result["validationByCutoff"][c]={"forced":sm(b["forced"],chosen),"market":sm(b["market"],chosen),"limit":slm(b["limit"]),"hybrid":sumhy(b["hybrid"],chosen),"top3":[{"symbol":x["symbol"],"side":x["side"],"score":x["score"],"quality":x["quality"],"rsi":x["h1Rsi"],"chaseATR":x["chaseATR"]} for x in b["top"]]}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f2.json","w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({"chosenRR":chosen,"dev":result["developmentSummary"],"validation":result["validationSummary"],"grid":grid},indent=2))
if __name__=="__main__":main()
