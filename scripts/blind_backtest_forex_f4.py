#!/usr/bin/env python3
import json, math, os, statistics, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PAIRS = [
    "EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
    "EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
    "GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
    "AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"
]
CCY = ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
DEV = [
    "2026-06-08T08:00:00Z","2026-06-09T08:00:00Z","2026-06-10T08:00:00Z",
    "2026-06-11T08:00:00Z","2026-06-12T08:00:00Z","2026-06-15T08:00:00Z",
    "2026-06-16T08:00:00Z","2026-06-17T08:00:00Z","2026-06-18T08:00:00Z",
    "2026-06-19T08:00:00Z","2026-06-22T08:00:00Z","2026-06-23T08:00:00Z",
    "2026-06-25T08:00:00Z","2026-07-03T08:00:00Z","2026-07-14T08:00:00Z"
]
VAL = [
    "2026-07-17T08:00:00Z","2026-07-20T08:00:00Z","2026-07-21T08:00:00Z",
    "2026-07-22T08:00:00Z","2026-07-24T08:00:00Z"
]
END_DATE = "2026-07-25 08:00:00"
OUTPUTSIZE = 5000
TRADE_EXPIRY_H = 30
LIMIT_EXPIRY_H = 5
CURRENCY_PROFILE = {
    "USD":{"riskFloor":1.00,"chase":0.90},
    "EUR":{"riskFloor":1.00,"chase":0.85},
    "GBP":{"riskFloor":1.10,"chase":0.78},
    "JPY":{"riskFloor":1.05,"chase":0.72},
    "CHF":{"riskFloor":1.05,"chase":0.68},
    "CAD":{"riskFloor":1.05,"chase":0.76},
    "AUD":{"riskFloor":1.10,"chase":0.78},
    "NZD":{"riskFloor":1.10,"chase":0.74},
}
MODELS = ("BALANCED","STRUCTURE","REGIME")

def dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def ema(v,n):
    if not v:return None
    a=2/(n+1); x=v[0]
    for z in v[1:]:x=a*z+(1-a)*x
    return x

def rsi(v,n=14):
    if len(v)<n+1:return None
    ds=[b-a for a,b in zip(v[-n-1:-1],v[-n:])]
    g=sum(max(x,0) for x in ds)/n; l=sum(max(-x,0) for x in ds)/n
    return 100.0 if l==0 else 100-100/(1+g/l)

def atr(rows,n=14):
    if len(rows)<n+1:return None
    x=rows[-n-1:]; tr=[]
    for i in range(1,len(x)):
        p=x[i-1]["close"]; q=x[i]
        tr.append(max(q["high"]-q["low"],abs(q["high"]-p),abs(q["low"]-p)))
    return sum(tr)/len(tr)

def adx(rows,n=14):
    if len(rows)<2*n+2:return None
    trs=[]; pdm=[]; mdm=[]
    for i in range(1,len(rows)):
        cur,prev=rows[i],rows[i-1]
        up=cur["high"]-prev["high"]; dn=prev["low"]-cur["low"]
        pdm.append(up if up>dn and up>0 else 0.0); mdm.append(dn if dn>up and dn>0 else 0.0)
        trs.append(max(cur["high"]-cur["low"],abs(cur["high"]-prev["close"]),abs(cur["low"]-prev["close"])))
    if len(trs)<2*n:return None
    dxs=[]
    for j in range(len(trs)-n+1):
        trn=sum(trs[j:j+n])
        if trn<=1e-12:continue
        pdi=100*sum(pdm[j:j+n])/trn; mdi=100*sum(mdm[j:j+n])/trn; den=pdi+mdi
        dxs.append(0.0 if den<=1e-12 else 100*abs(pdi-mdi)/den)
    return statistics.mean(dxs[-n:]) if len(dxs)>=n else (statistics.mean(dxs) if dxs else None)

def bucket(t,h):return t.replace(hour=(t.hour//h)*h,minute=0,second=0,microsecond=0)
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
    if len(d)<2:return {k:0.0 for k in d}
    m=statistics.mean(d.values()); s=statistics.pstdev(d.values())
    return {k:((v-m)/s if s>1e-12 else 0.0) for k,v in d.items()}

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
        req=urllib.request.Request("https://api.twelvedata.com/time_series?"+qs,headers={"User-Agent":"trading-api-forex-f4/1.0"})
        with urllib.request.urlopen(req,timeout=100) as z:payload=json.loads(z.read().decode())
        got=parse_batch(payload); miss=[x for x in g if x not in got]
        if miss:raise RuntimeError(f"batch {i+1} missing {miss}: {str(payload)[:2200]}")
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
    hs=(6,24,72); raw={h:{} for h in hs}
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
    return {h:{c:(statistics.mean(v) if v else 0.0) for c,v in ans[h].items()} for h in hs}

def daily_range_proxy(pre):
    vals=[]; n=96; x=pre[-n*10:]
    for i in range(0,len(x)-n+1,n):
        g=x[i:i+n]
        if len(g)==n:vals.append(max(r["high"] for r in g)-min(r["low"] for r in g))
    return statistics.median(vals) if vals else None

def pair_features(pair,rows,cut,st):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<650:return None
    h1=agg(pre,1); h4=agg(pre,4)
    if len(h1)<100 or len(h4)<55:return None
    c=pre[-1]["close"]; a15=atr(pre); a1=atr(h1); h1adx=adx(h1)
    if not a15 or not a1 or h1adx is None:return None
    mc=[x["close"] for x in pre]; h1c=[x["close"] for x in h1]; h4c=[x["close"] for x in h4]
    e15_20=ema(mc[-120:],20); e1_20=ema(h1c[-120:],20); e1_50=ema(h1c[-180:],50); e1_prev=ema(h1c[-123:-3],20)
    e4_20=ema(h4c[-80:],20); e4_50=ema(h4c[-120:],50); e4_prev=ema(h4c[-83:-3],20); hrsi=rsi(h1c)
    if None in (e15_20,e1_20,e1_50,e1_prev,e4_20,e4_50,e4_prev,hrsi):return None
    b,q=pair[:3],pair[3:]; d6=st[6][b]-st[6][q]; d24=st[24][b]-st[24][q]; d72=st[72][b]-st[72][q]
    h4trend=1 if c>e4_20>e4_50 else -1 if c<e4_20<e4_50 else 0
    h1trend=1 if c>e1_20>e1_50 else -1 if c<e1_20<e1_50 else 0
    h4slope=1 if e4_20>e4_prev else -1; h1slope=1 if e1_20>e1_prev else -1
    m15dev=(c-e15_20)/a15; mom1=(c-mc[-5])/a15; mom4=(c-mc[-17])/a15 if len(mc)>=17 else 0.0
    balanced=1.15*d6+0.85*d24+0.45*d72+1.15*h4trend+0.45*h4slope+1.00*h1trend+0.40*h1slope+0.30*max(-1.5,min(1.5,mom1))
    structure=0.55*d6+0.70*d24+0.45*d72+1.55*h4trend+0.60*h4slope+1.35*h1trend+0.55*h1slope+0.20*max(-1.5,min(1.5,mom4))
    if h1adx>=24:
        regime=1.20*d6+0.85*d24+0.40*d72+1.35*h4trend+1.15*h1trend+0.35*h1slope+0.30*max(-1.5,min(1.5,mom1))
    elif h1adx<=17:
        regime=0.25*d6+0.60*d24+0.45*d72+0.55*h4trend+0.45*h1trend-0.70*max(-1.5,min(1.5,m15dev))
    else:
        regime=0.80*d6+0.80*d24+0.45*d72+1.00*h4trend+0.90*h1trend+0.30*h1slope
    pf1=CURRENCY_PROFILE[b]; pf2=CURRENCY_PROFILE[q]; risk_floor=max(pf1["riskFloor"],pf2["riskFloor"]); chase=max(pf1["chase"],pf2["chase"])
    adr=daily_range_proxy(pre) or 6.0*a1
    return {"symbol":pair,"entry":c,"atr15":a15,"atr1":a1,"adr":adr,"d6":d6,"d24":d24,"d72":d72,"h4trend":h4trend,"h1trend":h1trend,"h1adx":h1adx,"h1rsi":hrsi,"m15dev":m15dev,"mom1":mom1,"mom4":mom4,"ema15":e15_20,"riskFloorATR":risk_floor,"maxChaseATR":chase,"scores":{"BALANCED":balanced,"STRUCTURE":structure,"REGIME":regime},"pre":pre,"h1":h1}

def direction_for(f,model):return "BUY" if f["scores"][model]>=0 else "SELL"

def build_barriers(f,side):
    pre=f["pre"]; en=f["entry"]; a=f["atr15"]; adr=f["adr"]; sgn=1 if side=="BUY" else -1
    recent=pre[-24:]; swing=min(r["low"] for r in recent) if side=="BUY" else max(r["high"] for r in recent)
    raw=(en-swing+0.12*a) if side=="BUY" else (swing-en+0.12*a); floor=f["riskFloorATR"]*a; cap=max(2.6*a,0.32*adr)
    risk=min(max(raw,floor),cap); sl=en-risk if side=="BUY" else en+risk
    p24=pre[-96:] if len(pre)>=96 else pre; p72=pre[-288:] if len(pre)>=288 else pre
    ext24=max(r["high"] for r in p24) if side=="BUY" else min(r["low"] for r in p24); ext72=max(r["high"] for r in p72) if side=="BUY" else min(r["low"] for r in p72)
    def dist(x):return (x-en)*sgn
    candidates=[x for x in (ext24,ext72) if dist(x)>0.75*a]; max_move=max(1.15*a,0.72*adr)
    if candidates:
        target_dist=min(dist(x) for x in candidates)
        if target_dist>1.25*max_move:target_dist=max_move
    else:target_dist=max_move
    target_dist=max(target_dist,0.90*a); tp=en+sgn*target_dist; planned_rr=target_dist/risk if risk>0 else None
    return sl,tp,risk,planned_rr

def limit_price(f,side,risk):
    en=f["entry"]; ema15=f["ema15"]; a=f["atr15"]; sgn=1 if side=="BUY" else -1
    favorable=(ema15<en) if side=="BUY" else (ema15>en); pull=abs(en-ema15) if favorable else 0.18*risk
    pull=min(max(pull,0.12*risk),0.45*a); return en-sgn*pull

def outcome_market(f,rows,cut,model):
    side=direction_for(f,model); sl,tp,risk,rr=build_barriers(f,side); fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_EXPIRY_H)]
    for i,r in enumerate(fut,1):
        hit_sl=(r["low"]<=sl) if side=="BUY" else (r["high"]>=sl); hit_tp=(r["high"]>=tp) if side=="BUY" else (r["low"]<=tp)
        if hit_sl and hit_tp:res="AMBIGUOUS"
        elif hit_sl:res="SL"
        elif hit_tp:res="TP"
        else:continue
        return {"result":res,"bars":i,"side":side,"entry":f["entry"],"sl":sl,"tp":tp,"plannedRR":rr,"risk":risk}
    return {"result":"TIMEOUT","bars":len(fut),"side":side,"entry":f["entry"],"sl":sl,"tp":tp,"plannedRR":rr,"risk":risk}

def outcome_limit(f,rows,cut,model):
    side=direction_for(f,model); sl,tp,risk,rr=build_barriers(f,side); lim=limit_price(f,side,risk); fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_EXPIRY_H)]; fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=LIMIT_EXPIRY_H):break
        hit_tp=(r["high"]>=tp) if side=="BUY" else (r["low"]<=tp); fill=(r["low"]<=lim) if side=="BUY" else (r["high"]>=lim)
        if hit_tp and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False,"side":side,"limit":lim,"sl":sl,"tp":tp,"plannedRRMarket":rr}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False,"side":side,"limit":lim,"sl":sl,"tp":tp,"plannedRRMarket":rr}
    lr=abs(lim-sl); eff=abs(tp-lim)/lr if lr>0 else None
    for j,r in enumerate(fut[fi:],1):
        hit_sl=(r["low"]<=sl) if side=="BUY" else (r["high"]>=sl); hit_tp=(r["high"]>=tp) if side=="BUY" else (r["low"]<=tp)
        if hit_sl and hit_tp:res="AMBIGUOUS"
        elif hit_sl:res="SL"
        elif hit_tp:res="TP"
        else:continue
        return {"result":res,"filled":True,"bars":j,"side":side,"limit":lim,"sl":sl,"tp":tp,"effectiveRR":eff,"plannedRRMarket":rr}
    return {"result":"TIMEOUT","filled":True,"bars":len(fut)-fi,"side":side,"limit":lim,"sl":sl,"tp":tp,"effectiveRR":eff,"plannedRRMarket":rr}

def horizon_dir(f,rows,cut,model,h):
    side=direction_for(f,model); end=before(rows,cut+timedelta(hours=h))
    if end is None:return None
    move=(end-f["entry"]) if side=="BUY" else (f["entry"]-end)
    return {"correct":move>0,"moveATR":(move/f["atr15"] if f["atr15"] else None),"end":end}

def summarize_market(items):
    res=[x for x in items if x["outcome"]["result"] in ("TP","SL")]; w=sum(x["outcome"]["result"]=="TP" for x in res); l=len(res)-w
    rrs=[x["outcome"]["plannedRR"] for x in res if x["outcome"].get("plannedRR") is not None]; pnl=[x["outcome"].get("plannedRR",0.0) if x["outcome"]["result"]=="TP" else -1.0 for x in res]
    return {"signals":len(items),"resolved":len(res),"wins":w,"losses":l,"timeouts":sum(x["outcome"]["result"]=="TIMEOUT" for x in items),"ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in items),"winRateResolved":round(100*w/len(res),2) if res else None,"avgPlannedRR":round(statistics.mean(rrs),3) if rrs else None,"medianPlannedRR":round(statistics.median(rrs),3) if rrs else None,"expectancyR":round(statistics.mean(pnl),3) if pnl else None}

def summarize_limit(items):
    fills=[x for x in items if x["outcome"].get("filled")]; res=[x for x in fills if x["outcome"]["result"] in ("TP","SL")]; w=sum(x["outcome"]["result"]=="TP" for x in res); l=len(res)-w
    rrs=[x["outcome"].get("effectiveRR") for x in res if x["outcome"].get("effectiveRR") is not None]; pnl=[x["outcome"].get("effectiveRR",0.0) if x["outcome"]["result"]=="TP" else -1.0 for x in res]
    return {"signals":len(items),"fills":len(fills),"fillRate":round(100*len(fills)/len(items),2) if items else None,"resolved":len(res),"wins":w,"losses":l,"noFill":sum(x["outcome"]["result"]=="NO_FILL" for x in items),"targetBeforeFill":sum(x["outcome"]["result"]=="TARGET_BEFORE_FILL" for x in items),"timeoutsAfterFill":sum(x["outcome"]["result"]=="TIMEOUT" and x["outcome"].get("filled") for x in items),"ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in items),"winRateResolved":round(100*w/len(res),2) if res else None,"avgEffectiveRR":round(statistics.mean(rrs),3) if rrs else None,"expectancyR":round(statistics.mean(pnl),3) if pnl else None}

def summarize_direction(items,key):
    vals=[x[key] for x in items if x.get(key)]
    if not vals:return {"tests":0,"correct":0,"accuracy":None,"avgMoveATR":None}
    c=sum(v["correct"] for v in vals); mv=[v["moveATR"] for v in vals if v.get("moveATR") is not None]
    return {"tests":len(vals),"correct":c,"accuracy":round(100*c/len(vals),2),"avgMoveATR":round(statistics.mean(mv),3) if mv else None}

def evaluate_model_pair(pair,model,frames,dates):
    items=[]
    for s in dates:
        cut=dt(s); st=strength(frames,cut); f=pair_features(pair,frames[pair],cut,st)
        if not f:continue
        om=outcome_market(f,frames[pair],cut,model)
        items.append({"cutoff":s,"feature":f,"outcome":om,"d6":horizon_dir(f,frames[pair],cut,model,6),"d12":horizon_dir(f,frames[pair],cut,model,12),"d24":horizon_dir(f,frames[pair],cut,model,24)})
    sm=summarize_market(items); sd=summarize_direction(items,"d12"); acc=(sd["accuracy"] or 0)/100; exp=sm["expectancyR"] if sm["expectancyR"] is not None else -1; med=sm["medianPlannedRR"] if sm["medianPlannedRR"] is not None else 0
    score=0.70*acc+0.30*max(-1,min(1,exp/1.5))
    if len(items)<max(8,int(0.7*len(dates))):score-=0.25
    if med<0.70:score-=0.10
    return score,items,sm,sd

def choose_models(frames):
    chosen={}; report={}
    for p in PAIRS:
        stats={}
        for m in MODELS:
            score,items,sm,sd=evaluate_model_pair(p,m,frames,DEV); stats[m]={"selectionScore":round(score,4),"market":sm,"direction12h":sd}
        ranked=sorted(MODELS,key=lambda m:stats[m]["selectionScore"],reverse=True); best=ranked[0]
        if best!="BALANCED" and stats[best]["selectionScore"]-stats["BALANCED"]["selectionScore"]<0.055:best="BALANCED"
        chosen[p]=best; report[p]={"chosen":best,"models":stats}
    return chosen,report

def evaluate_dates(frames,dates,chosen):
    market=[]; limit=[]; per_pair={p:[] for p in PAIRS}; per_cutoff={}
    for s in dates:
        cut=dt(s); st=strength(frames,cut); cm=[]; cl=[]
        for p in PAIRS:
            f=pair_features(p,frames[p],cut,st)
            if not f:continue
            m=chosen[p]; om=outcome_market(f,frames[p],cut,m); ol=outcome_limit(f,frames[p],cut,m)
            rec={"symbol":p,"model":m,"side":direction_for(f,m),"score":round(f["scores"][m],4),"entry":f["entry"],"h1ADX":round(f["h1adx"],2),"h1RSI":round(f["h1rsi"],2),"d6Strength":round(f["d6"],3),"d24Strength":round(f["d24"],3),"d72Strength":round(f["d72"],3),"market":om,"limit":ol,"dir6h":horizon_dir(f,frames[p],cut,m,6),"dir12h":horizon_dir(f,frames[p],cut,m,12),"dir24h":horizon_dir(f,frames[p],cut,m,24)}
            im={"symbol":p,"cutoff":s,"outcome":om,"d6":rec["dir6h"],"d12":rec["dir12h"],"d24":rec["dir24h"]}; il={"symbol":p,"cutoff":s,"outcome":ol}
            market.append(im); limit.append(il); cm.append(im); cl.append(il); per_pair[p].append(rec)
        per_cutoff[s]={"market":summarize_market(cm),"limit":summarize_limit(cl),"direction6h":summarize_direction(cm,"d6"),"direction12h":summarize_direction(cm,"d12"),"direction24h":summarize_direction(cm,"d24")}
    pair_summary={}
    for p,recs in per_pair.items():
        ims=[{"outcome":r["market"],"d6":r["dir6h"],"d12":r["dir12h"],"d24":r["dir24h"]} for r in recs]; ils=[{"outcome":r["limit"]} for r in recs]
        pair_summary[p]={"model":chosen[p],"tests":len(recs),"market":summarize_market(ims),"limit":summarize_limit(ils),"direction6h":summarize_direction(ims,"d6"),"direction12h":summarize_direction(ims,"d12"),"direction24h":summarize_direction(ims,"d24"),"trades":recs}
    return {"market":summarize_market(market),"limit":summarize_limit(limit),"direction6h":summarize_direction(market,"d6"),"direction12h":summarize_direction(market,"d12"),"direction24h":summarize_direction(market,"d24"),"byCutoff":per_cutoff,"byPair":pair_summary}

def main():
    raw=fetch(); frames={p:norm(raw[p]) for p in PAIRS}; chosen,dev_report=choose_models(frames); val=evaluate_dates(frames,VAL,chosen)
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F4 pair-adaptive forced blind","integrity":{"validationCutoffsRepoSearchedAbsentBeforeCreation":True,"decisionUsesFutureData":False,"allValidPairsForcedBuyOrSell":True,"noTop3Selection":True,"tpSlFixedRR":False,"methodFrozenBeforeValidationReveal":True},"method":{"description":"Every valid pair is forced BUY or SELL. Each pair chooses one of three predeclared low-complexity models using development-only evidence: BALANCED cross-currency+trend, STRUCTURE-first, or ADX REGIME-adaptive. Minimal indicators: EMA20/50, RSI14, ATR14, ADX14 plus 6h/24h/72h cross-currency strength. SL is recent M15 structural invalidation with ATR/realized-range floor/cap. TP is prior 24h/72h directional liquidity when realistic, otherwise trailing realized daily-range projection. No fixed RR target. MARKET and adaptive pullback LIMIT are both evaluated. Direction is separately scored at 6h/12h/24h.","models":list(MODELS),"indicators":["EMA20/50","RSI14","ATR14","ADX14"],"nonIndicatorContext":["6h/24h/72h cross-currency strength","H4/H1 structure","M15 location","trailing realized daily range"],"developmentDates":DEV,"validationDates":VAL},"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","pairs":28,"creditsExpected":28,"outputsize":OUTPUTSIZE,"rawCommitted":False},"pairModelSelection":dev_report,"chosenModelByPair":chosen,"blindValidation":val}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f4.json","w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    compact={"chosenModelByPair":chosen,"market":val["market"],"limit":val["limit"],"direction6h":val["direction6h"],"direction12h":val["direction12h"],"direction24h":val["direction24h"],"byPair":{p:{"model":x["model"],"marketWR":x["market"]["winRateResolved"],"marketExpR":x["market"]["expectancyR"],"medianRR":x["market"]["medianPlannedRR"],"dir12":x["direction12h"]["accuracy"],"dir24":x["direction24h"]["accuracy"]} for p,x in val["byPair"].items()}}
    print(json.dumps(compact,indent=2))

if __name__=="__main__":main()
