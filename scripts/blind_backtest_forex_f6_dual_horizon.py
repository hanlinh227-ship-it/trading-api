#!/usr/bin/env python3
import json, os, statistics
from datetime import datetime, timedelta, timezone
from scripts import blind_backtest_forex_f4_allpairs_dynamic as base

PAIRS=base.PAIRS
CUTS=["2026-06-24T08:00:00Z","2026-06-30T08:00:00Z","2026-07-02T08:00:00Z","2026-07-07T08:00:00Z","2026-07-10T08:00:00Z"]

# F6: classify the tradable horizon BEFORE future prices are opened.
# IMPULSE_3H focuses on immediate session displacement.
# REGIME_24H focuses on H4/H1 + 24h/72h persistence.

def feat(pair,rows,cut,st):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<500:return None
    h1=base.agg(pre,1);h4=base.agg(pre,4)
    if len(h1)<90 or len(h4)<55:return None
    c=pre[-1]["close"]; a=base.atr(pre); a1=base.atr(h1); ax=base.adx(h1)
    if not a or not a1 or ax is None:return None
    mc=[x["close"] for x in pre]; h1c=[x["close"] for x in h1]; h4c=[x["close"] for x in h4]
    e15=base.ema(mc[-100:],20);e1=base.ema(h1c[-110:],20);e150=base.ema(h1c[-150:],50);e4=base.ema(h4c[-80:],20);e450=base.ema(h4c[-110:],50);hr=base.rsi(h1c)
    if None in (e15,e1,e150,e4,e450,hr):return None
    b,q=pair[:3],pair[3:];d6=st[6][b]-st[6][q];d24=st[24][b]-st[24][q];d72=st[72][b]-st[72][q]
    h4s=1 if c>e4>e450 else -1 if c<e4<e450 else (1 if c>e4 else -1)
    h1s=1 if c>e1>e150 else -1 if c<e1<e150 else (1 if c>e1 else -1)
    mom1=(c-mc[-5])/a; mom3=(c-mc[-13])/a; dev=(c-e15)/a
    # Pre-known classifier; no future performance is involved.
    regime_agree=(h4s==h1s and d24*h4s>0 and d72*h4s>0)
    impulse_strength=abs(d6)+.35*abs(mom1)+.20*abs(mom3)
    regime_strength=abs(d24)+.70*abs(d72)+.55*(1 if h4s==h1s else 0)+(.25 if ax>=22 else 0)
    stretched=(abs(dev)>=.95 or hr>=70 or hr<=30)
    if impulse_strength>=regime_strength*.92 and not (regime_agree and ax>=25 and abs(d6)<.65):
        horizon="IMPULSE_3H"
        score=1.55*d6+.40*d24+.45*(1 if mom1>0 else -1)+.25*(1 if mom3>0 else -1)+.30*h1s
        # If immediate impulse is clearly stretched against H1 regime, damp it rather than flip blindly.
        if stretched and score*h1s<0:score*=.65
        recent=pre[-5:]
        expiry=4
        risk_floor=.62*a
        rr=.90+.18*(1 if d6*score>0 else 0)+(.18 if ax>=22 else .05)+(.12 if abs(dev)<.60 else -.08)
        rr=max(.72,min(1.45,rr))
    else:
        horizon="REGIME_24H"
        score=.35*d6+1.00*d24+.72*d72+1.05*h4s+.85*h1s
        # Strong H4/H1 alignment is the defining feature of this branch.
        recent=pre[-16:]
        expiry=28
        risk_floor=.95*a
        rr=1.25+.20*(1 if h4s==h1s else 0)+.18*(1 if d24*score>0 else 0)+.18*(1 if d72*score>0 else 0)+(.15 if ax>=22 else 0)
        rr=max(1.05,min(2.10,rr))
    side="BUY" if score>=0 else "SELL";sg=1 if side=="BUY" else -1
    swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    raw=(c-swing) if side=="BUY" else (swing-c)
    risk=max(raw+.10*a,risk_floor)
    if "JPY" in (b,q) or "GBP" in (b,q):risk=max(risk,risk_floor+.10*a)
    sl=c-risk if side=="BUY" else c+risk
    # Pre-known liquidity target may shorten, never lengthen, the modeled target.
    window=12 if horizon=="IMPULSE_3H" else 32
    hh=max(x["high"] for x in h1[-window:]);ll=min(x["low"] for x in h1[-window:])
    dist=(hh-c) if side=="BUY" else (c-ll)
    if dist>0 and .65<=dist/risk<=2.3:rr=min(rr,max(.68,dist/risk))
    tp=c+risk*rr if side=="BUY" else c-risk*rr
    # LIMIT only if REGIME branch or clearly stretched impulse. Otherwise MARKET should capture impulse.
    use_limit=(horizon=="REGIME_24H" and abs(dev)>=.45) or (horizon=="IMPULSE_3H" and abs(dev)>=.85)
    if use_limit and side=="BUY" and sl<e15<c:lim=e15
    elif use_limit and side=="SELL" and c<e15<sl:lim=e15
    else:lim=c-(.16*risk if side=="BUY" else -.16*risk)
    return {"symbol":pair,"side":side,"horizon":horizon,"entry":c,"limit":lim,"sl":sl,"tp":tp,"risk":risk,"rr":rr,"expiryH":expiry,"useLimit":use_limit,"score":score,"d6":d6,"d24":d24,"d72":d72,"adx":ax,"rsi":hr,"devATR":dev,"h4":h4s,"h1":h1s}

def direction(f,rows,cut):
    sg=1 if f["side"]=="BUY" else -1;en=f["entry"];out={}
    for h in (3,6,12,24):
        z=base.before(rows,cut+timedelta(hours=h));out[f"{h}h"]={"correct":((z-en)*sg>0) if z is not None else None,"close":z}
    target=3 if f["horizon"]=="IMPULSE_3H" else 24
    out["chosen"]={"horizonH":target,"correct":out[f"{target}h"]["correct"]}
    return out

def mkt(f,rows,cut):
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=f["expiryH"])]
    for i,r in enumerate(fut,1):
        a=r["low"]<=f["sl"] if f["side"]=="BUY" else r["high"]>=f["sl"]
        b=r["high"]>=f["tp"] if f["side"]=="BUY" else r["low"]<=f["tp"]
        if a and b:return {"result":"AMBIGUOUS","bars":i}
        if a:return {"result":"SL","bars":i}
        if b:return {"result":"TP","bars":i}
    return {"result":"TIMEOUT","bars":len(fut)}
def lim(f,rows,cut):
    # Pending validity is shorter for impulse, longer for regime.
    pending=1.5 if f["horizon"]=="IMPULSE_3H" else 5
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=f["expiryH"])];fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=pending):break
        tgt=r["high"]>=f["tp"] if f["side"]=="BUY" else r["low"]<=f["tp"]
        fill=r["low"]<=f["limit"] if f["side"]=="BUY" else r["high"]>=f["limit"]
        if tgt and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False}
    lr=abs(f["limit"]-f["sl"]);eff=abs(f["tp"]-f["limit"])/lr if lr else None
    for j,r in enumerate(fut[fi:],1):
        a=r["low"]<=f["sl"] if f["side"]=="BUY" else r["high"]>=f["sl"]
        b=r["high"]>=f["tp"] if f["side"]=="BUY" else r["low"]<=f["tp"]
        if a and b:return {"result":"AMBIGUOUS","filled":True,"effectiveRR":eff,"bars":j}
        if a:return {"result":"SL","filled":True,"effectiveRR":eff,"bars":j}
        if b:return {"result":"TP","filled":True,"effectiveRR":eff,"bars":j}
    return {"result":"TIMEOUT","filled":True,"effectiveRR":eff,"bars":len(fut)-fi}

def summary(rows,key):
    outs=[x[key] for x in rows];resolved=[(i,o) for i,o in enumerate(outs) if o["result"] in ("TP","SL")];w=sum(o["result"]=="TP" for _,o in resolved);total=0
    for i,o in resolved:total+=(rows[i]["feature"]["rr"] if key=="market" else o.get("effectiveRR",0)) if o["result"]=="TP" else -1
    return {"signals":len(rows),"resolved":len(resolved),"wins":w,"losses":len(resolved)-w,"winRateResolved":round(100*w/len(resolved),2) if resolved else None,"expectancyR":round(total/len(resolved),3) if resolved else None,"timeouts":sum(o["result"]=="TIMEOUT" for o in outs),"noFill":sum(o["result"]=="NO_FILL" for o in outs),"targetBeforeFill":sum(o["result"]=="TARGET_BEFORE_FILL" for o in outs)}
def dirsum(rows,k):
    v=[x["direction"][k]["correct"] for x in rows if x["direction"][k]["correct"] is not None];return {"n":len(v),"correct":sum(v),"accuracy":round(100*sum(v)/len(v),2) if v else None}

def main():
    raw=base.fetch();frames={p:base.norm(raw[p]) for p in PAIRS};allr=[];bycut={}
    for cs in CUTS:
        cut=base.DT(cs);st=base.strength(frames,cut);g=[]
        for p in PAIRS:
            f=feat(p,frames[p],cut,st)
            if not f:continue
            x={"cutoff":cs,"feature":f,"direction":direction(f,frames[p],cut),"market":mkt(f,frames[p],cut),"limit":lim(f,frames[p],cut)};g.append(x);allr.append(x)
        bycut[cs]={"market":summary(g,"market"),"limit":summary(g,"limit"),"chosenDirection":dirsum(g,"chosen"),"direction3":dirsum(g,"3h"),"direction24":dirsum(g,"24h"),"impulseCount":sum(x["feature"]["horizon"]=="IMPULSE_3H" for x in g),"regimeCount":sum(x["feature"]["horizon"]=="REGIME_24H" for x in g)}
    bysym={}
    for p in PAIRS:
        g=[x for x in allr if x["feature"]["symbol"]==p];bysym[p]={"market":summary(g,"market"),"limit":summary(g,"limit"),"chosenDirection":dirsum(g,"chosen"),"direction3":dirsum(g,"3h"),"direction24":dirsum(g,"24h"),"impulseCount":sum(x["feature"]["horizon"]=="IMPULSE_3H" for x in g),"regimeCount":sum(x["feature"]["horizon"]=="REGIME_24H" for x in g)}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"FOREX F6 dual-horizon forced blind. Every valid pair is forced BUY/SELL. Before future candles, each setup is classified as IMPULSE_3H or REGIME_24H from relative 6h impulse versus H4/H1 + 24h/72h regime strength. The two horizons are not averaged. SL, TP, expiry and pending-order lifetime are matched to the selected horizon. Minimal indicator stack unchanged. LIMIT is evaluated but MARKET remains default for impulse. No historical macro reconstruction.","integrity":{"rulesFrozenBeforeOutcomes":True,"forcedAllPairs":True,"noTop3":True,"noNoTrade":True,"lookAhead":False,"f4f5OnlyDiagnosis":True},"cutoffs":CUTS,"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28},"summary":{"signals":len(allr),"market":summary(allr,"market"),"limit":summary(allr,"limit"),"chosenDirection":dirsum(allr,"chosen"),"direction3":dirsum(allr,"3h"),"direction24":dirsum(allr,"24h"),"avgRR":round(statistics.mean(x["feature"]["rr"] for x in allr),3),"impulseCount":sum(x["feature"]["horizon"]=="IMPULSE_3H" for x in allr),"regimeCount":sum(x["feature"]["horizon"]=="REGIME_24H" for x in allr)},"byCutoff":bycut,"bySymbol":bysym,"trades":allr}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f6_dual_horizon.json","w",encoding="utf-8") as z:json.dump(result,z,ensure_ascii=False,indent=2)
    print(json.dumps({"summary":result["summary"],"byCutoff":bycut,"bySymbol":bysym},indent=2))
if __name__=="__main__":main()
