#!/usr/bin/env python3
import json, os
from datetime import datetime, timezone
from scripts import blind_backtest_forex_f8 as f8

DEV=f8.DEV+f8.VAL+[
"2026-05-25T08:00:00Z","2026-05-26T08:00:00Z","2026-05-27T08:00:00Z","2026-05-28T08:00:00Z","2026-05-29T08:00:00Z"]
VAL=["2026-06-01T08:00:00Z","2026-06-02T08:00:00Z","2026-06-03T08:00:00Z","2026-06-04T08:00:00Z","2026-06-05T08:00:00Z"]
F8_MODELS={"USD_MAJOR":"FACTOR_BAL","JPY_CROSS":"SESSION_SWEEP","EUROPE_CROSS":"FACTOR_BAL","COMMODITY_CROSS":"FACTOR_FAST","MIXED_CROSS":"FACTOR_BAL"}
f8.base.END_DATE="2026-06-06 08:00:00";f8.base.OUTPUTSIZE=5000

def usd_mid_score(f):
    sc=(.45*f["d3"]+1.05*f["d6"]+.95*f["d12"]+.50*f["d24"]+.15*f["d72"]
        +.45*f["h1"]+.25*f["h4"]+.15*max(-2,min(2,f["sessionRet"]))+.12*max(-2,min(2,f["mom3"])))
    if f["d3"]*sc<0 and abs(f["rankgap3"])>=5 and f["coh3"]>=.45:sc*=.45
    return sc

def build_trade_usd_mid(f):
    sc=usd_mid_score(f);side="BUY" if sc>=0 else "SELL";sg=1 if side=="BUY" else -1
    impulse=sum(x*sg>0 for x in (f["d3"],f["d6"],f["sessionRet"],f["mom1"]))
    regime=sum(x*sg>0 for x in (f["d24"],f["d72"],f["h1"],f["h4"]))
    strong_opp3=(f["d3"]*sg<0 and abs(f["rankgap3"])>=4 and f["coh3"]>=.40)
    use_regime=(regime==4 and not strong_opp3 and f["adx"]>=18 and impulse<=2 and f["fq24"]>=.45)
    mode="REGIME_24H" if use_regime else "IMPULSE_3H"
    recent=f["pre"][-16:] if use_regime else f["pre"][-7:]
    swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    raw=(f["entry"]-swing) if side=="BUY" else (swing-f["entry"])
    floor=(.92 if use_regime else .62)*f["atr"]
    if "JPY" in (f["symbol"][:3],f["symbol"][3:]) or "GBP" in (f["symbol"][:3],f["symbol"][3:]):floor+=.08*f["atr"]
    cap=(2.25 if use_regime else 1.55)*f["atr"];risk=min(max(raw+.10*f["atr"],floor),cap)
    sl=f["entry"]-risk if side=="BUY" else f["entry"]+risk
    if use_regime:
        rr=1.40+.12*regime+(.18 if f["adx"]>=24 else .05)+.10*min(1.2,f["fq24"]);rr=max(1.30,min(2.25,rr));expiry=24
    else:
        rr=1.05+.10*impulse+(.12 if f["adx"]>=20 else 0)+.10*min(1.2,f["fq3"])
        if abs(f["dev"])>1.05:rr-=.12
        rr=max(.95,min(1.65,rr));expiry=4
    h=f["h1rows"];window=24 if use_regime else 10;hh=max(x["high"] for x in h[-window:]);ll=min(x["low"] for x in h[-window:])
    dist=(hh-f["entry"]) if side=="BUY" else (f["entry"]-ll);floor_rr=1.30 if use_regime else .95
    if dist>0 and floor_rr<=dist/risk<=2.6:rr=min(rr,max(floor_rr,dist/risk))
    tp=f["entry"]+risk*rr if side=="BUY" else f["entry"]-risk*rr
    eligible=(use_regime and abs(f["dev"])>=.45 and f["h1"]==sg and f["h4"]==sg and not (f["breakUp"] or f["breakDown"]))
    if eligible and side=="BUY" and sl<f["ema15"]<f["entry"]:lim=f["ema15"]
    elif eligible and side=="SELL" and f["entry"]<f["ema15"]<sl:lim=f["ema15"]
    else:lim=f["entry"]-(.18*risk if side=="BUY" else -.18*risk)
    return {k:v for k,v in f.items() if k not in ("pre","h1rows")}|{"model":"USD_MID","side":side,"score":sc,"mode":mode,"impulseEvidence":impulse,"regimeEvidence":regime,"risk":risk,"sl":sl,"tp":tp,"rr":rr,"expiryH":expiry,"limit":lim,"limitEligible":eligible}

def row(cs,p,t,frames):
    cut=f8.base.DT(cs);d=f8.dir_eval(t,frames[p],cut);m=f8.market_eval(t,frames[p],cut);l=f8.limit_eval(t,frames[p],cut);r=f8.rec_eval(t,m,l)
    return {"cutoff":cs,"model":t["model"],"trade":t,"direction":d,"market":m,"limit":l,"recommended":r}

def build(frames,cuts,use_mid,usd_only=False):
    out=[]
    for cs in cuts:
        cut=f8.base.DT(cs);sp=f8.strength_pack(frames,cut)
        for p in f8.PAIRS:
            cf=f8.core_feature(p,frames[p],cut,sp)
            if not cf or (usd_only and cf["group"]!="USD_MAJOR"):continue
            if cf["group"]=="USD_MAJOR" and use_mid:t=build_trade_usd_mid(cf)
            else:t=f8.build_trade(cf,F8_MODELS[cf["group"]])
            out.append(row(cs,p,t,frames))
    return out

def pack(x):
    return {"market":f8.summary(x,"market"),"limit":f8.summary(x,"limit"),"recommended":f8.summary(x,"recommended"),"chosenDirection":f8.dirsum(x,"chosen"),"direction3":f8.dirsum(x,"3h"),"direction6":f8.dirsum(x,"6h"),"direction12":f8.dirsum(x,"12h"),"direction24":f8.dirsum(x,"24h"),"diagnostics":f8.diagnostics(x)}

def main():
    raw=f8.base.fetch();frames={p:f8.base.norm(raw[p]) for p in f8.PAIRS}
    dev_base=build(frames,DEV,False,True);dev_mid=build(frames,DEV,True,True)
    score_base=f8.dev_score(dev_base);score_mid=f8.dev_score(dev_mid)
    selected="USD_MID" if score_mid>=score_base+.03 else "FACTOR_BAL"
    baseline=build(frames,VAL,False);f10=build(frames,VAL,selected=="USD_MID")
    usd_base=[x for x in baseline if x["trade"]["group"]=="USD_MAJOR"];usd_f10=[x for x in f10 if x["trade"]["group"]=="USD_MAJOR"]
    bycut={}
    for cs in VAL:bycut[cs]={"baseline":pack([x for x in baseline if x["cutoff"]==cs]),"f10":pack([x for x in f10 if x["cutoff"]==cs])}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F10 USD-major mid-horizon comparator","integrity":{"developmentBeforeValidation":True,"validationDatesRepoSearchedAbsentBeforeCreation":True,"all28PairsForced":True,"sameHoldoutBaselineVsF10":True,"nonUsdF8Frozen":True,"holdoutUnusedForUsdSelection":True},"hypothesis":"Only USD_MAJOR is modified. USD_MID reduces noisy 3h ownership and emphasizes 6h/12h cross-currency factor state plus H1/H4. No new indicator; F8 barriers/execution remain unchanged.","developmentDates":DEV,"validationDates":VAL,"usdDevelopmentSelection":{"f8Score":score_base,"usdMidScore":score_mid,"selected":selected,"f8":pack(dev_base),"usdMid":pack(dev_mid)},"blindValidation":{"f8All28":pack(baseline),"f10All28":pack(f10),"f8UsdMajor":pack(usd_base),"f10UsdMajor":pack(usd_f10),"byCutoff":bycut},"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28,"rawCommitted":False}}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f10_usd_mid.json","w",encoding="utf-8") as z:json.dump(result,z,ensure_ascii=False,indent=2)
    print(json.dumps({"selection":result["usdDevelopmentSelection"],"validation":result["blindValidation"]},indent=2))
if __name__=="__main__":main()
