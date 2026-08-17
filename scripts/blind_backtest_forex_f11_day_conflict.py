#!/usr/bin/env python3
import json, os, statistics
from datetime import datetime, timezone
from scripts import blind_backtest_forex_f8 as f8

DEV=f8.DEV+f8.VAL+[
"2026-05-25T08:00:00Z","2026-05-26T08:00:00Z","2026-05-27T08:00:00Z","2026-05-28T08:00:00Z","2026-05-29T08:00:00Z",
"2026-06-01T08:00:00Z","2026-06-02T08:00:00Z","2026-06-03T08:00:00Z","2026-06-04T08:00:00Z","2026-06-05T08:00:00Z"]
VAL=["2026-06-08T08:00:00Z","2026-06-09T08:00:00Z","2026-06-10T08:00:00Z","2026-06-11T08:00:00Z","2026-06-12T08:00:00Z"]
MODELS={"USD_MAJOR":"FACTOR_BAL","JPY_CROSS":"SESSION_SWEEP","EUROPE_CROSS":"FACTOR_BAL","COMMODITY_CROSS":"FACTOR_FAST","MIXED_CROSS":"FACTOR_BAL"}
THRESHOLDS=(.55,.65,.75)
f8.base.END_DATE="2026-06-13 08:00:00"; f8.base.OUTPUTSIZE=5000

def sg(x):return 1 if x>0 else -1 if x<0 else 0

def mid_score(cf):
    return .90*cf["d6"]+.90*cf["d12"]+.30*cf["d24"]+.25*cf["h1"]+.15*cf["h4"]+.10*max(-2,min(2,cf["sessionRet"]))

def day_pack(frames,cs):
    cut=f8.base.DT(cs);sp=f8.strength_pack(frames,cut);arr=[]
    for p in f8.PAIRS:
        cf=f8.core_feature(p,frames[p],cut,sp)
        if not cf:continue
        bt=f8.build_trade(cf,MODELS[cf["group"]]);ms=mid_score(cf);mid="BUY" if ms>=0 else "SELL"
        coherent=(sg(cf["d6"])==sg(cf["d12"]) and sg(cf["d6"])!=0)
        arr.append((p,cf,bt,ms,mid,coherent))
    conflict=sum(bt["side"]!=mid for _,_,bt,_,mid,_ in arr)/max(1,len(arr))
    medcoh=sum(coh for *_,coh in arr)/max(1,len(arr))
    return {"cut":cut,"sp":sp,"arr":arr,"conflict":conflict,"mediumCoherence":medcoh}

def mid_trade(cf,ms):
    side="BUY" if ms>=0 else "SELL";s=1 if side=="BUY" else -1
    evidence=sum(x*s>0 for x in (cf["d6"],cf["d12"],cf["h1"],cf["sessionRet"]))
    recent=cf["pre"][-10:];swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    raw=(cf["entry"]-swing) if side=="BUY" else (swing-cf["entry"])
    floor=.72*cf["atr"] + (.08*cf["atr"] if "JPY" in (cf["symbol"][:3],cf["symbol"][3:]) or "GBP" in (cf["symbol"][:3],cf["symbol"][3:]) else 0)
    risk=min(max(raw+.10*cf["atr"],floor),1.85*cf["atr"]);sl=cf["entry"]-risk if side=="BUY" else cf["entry"]+risk
    rr=1.18+.09*evidence+(.10 if cf["adx"]>=20 else 0)+.08*min(1.2,cf["fq3"]);rr=max(1.05,min(1.65,rr));expiry=8
    h=cf["h1rows"];hh=max(x["high"] for x in h[-14:]);ll=min(x["low"] for x in h[-14:]);dist=(hh-cf["entry"]) if side=="BUY" else (cf["entry"]-ll)
    if dist>0 and 1.05<=dist/risk<=2.5:rr=min(rr,max(1.05,dist/risk))
    tp=cf["entry"]+risk*rr if side=="BUY" else cf["entry"]-risk*rr
    # Mid-factor override is a continuation/reversal decision at observable price; keep MARKET to isolate direction effect.
    lim=cf["entry"]-(.18*risk if side=="BUY" else -.18*risk)
    return {k:v for k,v in cf.items() if k not in ("pre","h1rows")}|{"model":"MID_FACTOR","side":side,"score":ms,"mode":"MID_6H","impulseEvidence":evidence,"regimeEvidence":0,"risk":risk,"sl":sl,"tp":tp,"rr":rr,"expiryH":expiry,"limit":lim,"limitEligible":False}

def row(cs,p,t,frames):
    cut=f8.base.DT(cs);d=f8.dir_eval(t,frames[p],cut);m=f8.market_eval(t,frames[p],cut);l=f8.limit_eval(t,frames[p],cut);r=f8.rec_eval(t,m,l)
    return {"cutoff":cs,"model":t["model"],"trade":t,"direction":d,"market":m,"limit":l,"recommended":r}

def build(frames,cuts,threshold=None):
    rows=[];daymeta={};overrides=0
    for cs in cuts:
        pk=day_pack(frames,cs);active=(threshold is not None and pk["conflict"]>=threshold and pk["mediumCoherence"]>=.55);ov=0
        for p,cf,bt,ms,mid,coh in pk["arr"]:
            strong_mid=(coh and abs(cf["d6"])+abs(cf["d12"])>=.55)
            use_mid=(active and strong_mid and bt["side"]!=mid)
            t=mid_trade(cf,ms) if use_mid else bt
            if use_mid:ov+=1;overrides+=1
            rows.append(row(cs,p,t,frames))
        daymeta[cs]={"conflictRatio":round(pk["conflict"],4),"mediumCoherence":round(pk["mediumCoherence"],4),"active":active,"overrides":ov}
    return rows,daymeta,overrides

def pack(x):return {"market":f8.summary(x,"market"),"limit":f8.summary(x,"limit"),"recommended":f8.summary(x,"recommended"),"chosenDirection":f8.dirsum(x,"chosen"),"direction3":f8.dirsum(x,"3h"),"direction6":f8.dirsum(x,"6h"),"direction12":f8.dirsum(x,"12h"),"direction24":f8.dirsum(x,"24h"),"diagnostics":f8.diagnostics(x)}

def main():
    raw=f8.base.fetch();frames={p:f8.base.norm(raw[p]) for p in f8.PAIRS}
    dev_base,_,_=build(frames,DEV,None);devscores={};devdetails={}
    base_score=f8.dev_score(dev_base)
    for th in THRESHOLDS:
        z,meta,ov=build(frames,DEV,th);devscores[str(th)]=f8.dev_score(z);devdetails[str(th)]={"score":devscores[str(th)],"overrides":ov,"summary":pack(z),"daysActive":sum(x["active"] for x in meta.values())}
    best=max(THRESHOLDS,key=lambda x:devscores[str(x)]);selected=best if devscores[str(best)]>=base_score+.02 else None
    val_base,base_meta,_=build(frames,VAL,None);val_f11,f11_meta,ov=build(frames,VAL,selected)
    bycut={}
    for cs in VAL:bycut[cs]={"dayMeta":f11_meta[cs],"baseline":pack([x for x in val_base if x["cutoff"]==cs]),"f11":pack([x for x in val_f11 if x["cutoff"]==cs])}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F11 day-conflict MID_FACTOR comparator","integrity":{"developmentBeforeValidation":True,"validationDatesRepoSearchedAbsentBeforeCreation":True,"all28PairsForced":True,"sameHoldoutF8VsF11":True,"holdoutUnusedForThresholdSelection":True,"noNewIndicator":True},"hypothesis":"On dates where frozen F8 short-horizon direction conflicts broadly with a coherent 6h/12h cross-currency state, selectively override only conflicting pairs with a MID_FACTOR 6h/12h direction. All other pairs keep frozen F8.","developmentDates":DEV,"validationDates":VAL,"developmentSelection":{"f8Score":base_score,"thresholdGrid":devdetails,"selectedThreshold":selected},"blindValidation":{"f8":pack(val_base),"f11":pack(val_f11),"f11Overrides":ov,"byCutoff":bycut},"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28,"rawCommitted":False}}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f11_day_conflict.json","w",encoding="utf-8") as z:json.dump(result,z,ensure_ascii=False,indent=2)
    print(json.dumps({"selection":result["developmentSelection"],"validation":result["blindValidation"]},indent=2))
if __name__=="__main__":main()
