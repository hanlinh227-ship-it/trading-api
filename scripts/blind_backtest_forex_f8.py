#!/usr/bin/env python3
import json, math, os, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from scripts import blind_backtest_forex_f4_allpairs_dynamic as base

PAIRS=base.PAIRS
CCY=base.CCY
# Strict walk-forward design: development ends before blind validation begins.
DEV=[
"2026-04-27T08:00:00Z","2026-04-28T08:00:00Z","2026-04-29T08:00:00Z","2026-04-30T08:00:00Z","2026-05-01T08:00:00Z",
"2026-05-04T08:00:00Z","2026-05-05T08:00:00Z","2026-05-06T08:00:00Z","2026-05-07T08:00:00Z","2026-05-08T08:00:00Z",
"2026-05-11T08:00:00Z","2026-05-12T08:00:00Z","2026-05-13T08:00:00Z","2026-05-14T08:00:00Z","2026-05-15T08:00:00Z"]
VAL=["2026-05-18T08:00:00Z","2026-05-19T08:00:00Z","2026-05-20T08:00:00Z","2026-05-21T08:00:00Z","2026-05-22T08:00:00Z"]
CANDIDATES=("FACTOR_FAST","FACTOR_BAL","STRUCTURE","SESSION_SWEEP")
DEFAULT_MODEL="FACTOR_BAL"

base.END_DATE="2026-05-23 08:00:00"
base.OUTPUTSIZE=5000

def sgn(x): return 1 if x>0 else -1 if x<0 else 0

def group(pair):
    b,q=pair[:3],pair[3:]
    if "USD" in (b,q): return "USD_MAJOR"
    if "JPY" in (b,q): return "JPY_CROSS"
    if b in ("AUD","NZD","CAD") and q in ("AUD","NZD","CAD"): return "COMMODITY_CROSS"
    if b in ("EUR","GBP","CHF") and q in ("EUR","GBP","CHF"): return "EUROPE_CROSS"
    return "MIXED_CROSS"

def strength_pack(frames,cut):
    hs=(3,6,12,24,72); pairret={h:{} for h in hs}
    for p,rows in frames.items():
        pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
        if not pre: continue
        now=pre[-1]["close"]
        for h in hs:
            old=base.before(pre,cut-timedelta(hours=h))
            if old and old>0: pairret[h][p]=math.log(now/old)
    z={h:base.zmap(pairret[h]) for h in hs}
    out={}; disp={}
    for h in hs:
        vals={c:[] for c in CCY}
        for p,v in z[h].items():
            b,q=p[:3],p[3:]; vals[b].append(v); vals[q].append(-v)
        strength={c:(statistics.mean(v) if v else 0.0) for c,v in vals.items()}
        coherence={}
        for c,v in vals.items():
            non=[x for x in v if abs(x)>1e-12]
            coherence[c]=abs(sum(sgn(x) for x in non))/len(non) if non else 0.0
        order=sorted(CCY,key=lambda c:strength[c],reverse=True)
        rank={c:i for i,c in enumerate(order)}
        out[h]={"strength":strength,"coherence":coherence,"rank":rank}
        disp[h]=statistics.pstdev(strength.values()) if len(strength)>1 else 0.0
    return {"h":out,"dispersion":disp}

def core_feature(pair,rows,cut,sp):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<700:return None
    h1=base.agg(pre,1);h4=base.agg(pre,4)
    if len(h1)<120 or len(h4)<65:return None
    c=pre[-1]["close"];a=base.atr(pre);a1=base.atr(h1);ax=base.adx(h1)
    if not a or not a1 or ax is None:return None
    mc=[x["close"] for x in pre];h1c=[x["close"] for x in h1];h4c=[x["close"] for x in h4]
    e15=base.ema(mc[-120:],20);e1=base.ema(h1c[-130:],20);e150=base.ema(h1c[-170:],50);e4=base.ema(h4c[-90:],20);e450=base.ema(h4c[-130:],50);hr=base.rsi(h1c)
    if None in (e15,e1,e150,e4,e450,hr):return None
    h1s=1 if c>e1>e150 else -1 if c<e1<e150 else (1 if c>e1 else -1)
    h4s=1 if c>e4>e450 else -1 if c<e4<e450 else (1 if c>e4 else -1)
    b,q=pair[:3],pair[3:]
    gaps={h:sp["h"][h]["strength"][b]-sp["h"][h]["strength"][q] for h in (3,6,12,24,72)}
    coh3=min(sp["h"][3]["coherence"][b],sp["h"][3]["coherence"][q]);coh24=min(sp["h"][24]["coherence"][b],sp["h"][24]["coherence"][q])
    rankgap3=sp["h"][3]["rank"][q]-sp["h"][3]["rank"][b];rankgap24=sp["h"][24]["rank"][q]-sp["h"][24]["rank"][b]
    fq3=coh3*abs(gaps[3])/(sp["dispersion"][3]+1e-9);fq24=coh24*abs(gaps[24])/(sp["dispersion"][24]+1e-9)
    mom1=(c-mc[-5])/a;mom3=(c-mc[-13])/a;dev=(c-e15)/a
    sess=pre[-32:]; prior=pre[-96:-32]
    sh=max(x["high"] for x in sess);sl=min(x["low"] for x in sess);so=sess[0]["open"]
    sessret=(c-so)/a;sessrange=(sh-sl)/a;sesspos=(c-sl)/(sh-sl) if sh>sl else .5
    ph=max(x["high"] for x in prior);pl=min(x["low"] for x in prior)
    sweepup=(sh>ph and c<ph);sweepdn=(sl<pl and c>pl);breakup=c>ph;breakdn=c<pl
    return {"symbol":pair,"group":group(pair),"pre":pre,"h1rows":h1,"entry":c,"atr":a,"atr1":a1,"adx":ax,"rsi":hr,"ema15":e15,"h1":h1s,"h4":h4s,
            "d3":gaps[3],"d6":gaps[6],"d12":gaps[12],"d24":gaps[24],"d72":gaps[72],"coh3":coh3,"coh24":coh24,"fq3":fq3,"fq24":fq24,"rankgap3":rankgap3,"rankgap24":rankgap24,
            "mom1":mom1,"mom3":mom3,"dev":dev,"sessionRet":sessret,"sessionRangeATR":sessrange,"sessionPos":sesspos,"sweepUp":sweepup,"sweepDown":sweepdn,"breakUp":breakup,"breakDown":breakdn,"priorHigh":ph,"priorLow":pl}

def model_score(f,model):
    d3,d6,d24,d72=f["d3"],f["d6"],f["d24"],f["d72"]
    m1,m3=f["mom1"],f["mom3"];sr=f["sessionRet"];h1,h4=f["h1"],f["h4"]
    q3=.75+.25*min(1.5,f["fq3"]);q24=.75+.25*min(1.5,f["fq24"])
    if model=="FACTOR_FAST":
        sc=q3*(1.65*d3+.65*d6)+.38*max(-2,min(2,sr))+.30*max(-2,min(2,m1))+.20*h1
    elif model=="STRUCTURE":
        sc=.55*d3+.55*d6+q24*(.90*d24+.55*d72)+1.05*h1+.80*h4+.25*max(-2,min(2,m3))
        if sgn(d3) and sgn(sc)!=sgn(d3) and abs(f["rankgap3"])>=4 and f["coh3"]>=.40: sc*=.35
    elif model=="SESSION_SWEEP":
        sc=q3*(1.10*d3+.55*d6)+.70*max(-2,min(2,sr))+.35*max(-2,min(2,m1))+.20*h1
        if f["sweepUp"] and f["rsi"]>=58: sc=-abs(sc)-.45
        if f["sweepDown"] and f["rsi"]<=42: sc=abs(sc)+.45
    else:
        sc=q3*(1.25*d3+.75*d6)+.45*d24+.18*d72+.42*h1+.25*h4+.25*max(-2,min(2,sr))
    g=f["group"]
    if g=="JPY_CROSS": sc+=.18*sgn(sr)+.12*sgn(d3)
    elif g=="EUROPE_CROSS": sc+=.16*sgn(sr)+.10*sgn(m1)
    elif g=="COMMODITY_CROSS": sc+=.12*sgn(d24)+.08*sgn(d72)
    elif g=="USD_MAJOR": sc+=.10*sgn(d3)+.08*sgn(d24)
    return sc

def build_trade(f,model):
    sc=model_score(f,model);side="BUY" if sc>=0 else "SELL";sg=1 if side=="BUY" else -1
    impulse=sum(x*sg>0 for x in (f["d3"],f["d6"],f["sessionRet"],f["mom1"]))
    regime=sum(x*sg>0 for x in (f["d24"],f["d72"],f["h1"],f["h4"]))
    strong_opp3=(f["d3"]*sg<0 and abs(f["rankgap3"])>=4 and f["coh3"]>=.40)
    use_regime=(regime==4 and not strong_opp3 and f["adx"]>=18 and impulse<=2 and f["fq24"]>=.45)
    mode="REGIME_24H" if use_regime else "IMPULSE_3H"
    recent=f["pre"][-16:] if use_regime else f["pre"][-7:]
    swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    raw=(f["entry"]-swing) if side=="BUY" else (swing-f["entry"])
    floor=(.92 if use_regime else .62)*f["atr"]
    if "JPY" in (f["symbol"][:3],f["symbol"][3:]) or "GBP" in (f["symbol"][:3],f["symbol"][3:]): floor+=.08*f["atr"]
    cap=(2.25 if use_regime else 1.55)*f["atr"]
    risk=min(max(raw+.10*f["atr"],floor),cap)
    sl=f["entry"]-risk if side=="BUY" else f["entry"]+risk
    if use_regime:
        rr=1.40+.12*regime+(.18 if f["adx"]>=24 else .05)+.10*min(1.2,f["fq24"])
        rr=max(1.30,min(2.25,rr));expiry=24
    else:
        rr=1.05+.10*impulse+(.12 if f["adx"]>=20 else 0)+.10*min(1.2,f["fq3"])
        if abs(f["dev"])>1.05: rr-=.12
        rr=max(.95,min(1.65,rr));expiry=4
    h1=f["h1rows"];window=24 if use_regime else 10
    hh=max(x["high"] for x in h1[-window:]);ll=min(x["low"] for x in h1[-window:])
    dist=(hh-f["entry"]) if side=="BUY" else (f["entry"]-ll)
    floor_rr=1.30 if use_regime else .95
    if dist>0 and floor_rr<=dist/risk<=2.6: rr=min(rr,max(floor_rr,dist/risk))
    tp=f["entry"]+risk*rr if side=="BUY" else f["entry"]-risk*rr
    eligible_limit=(use_regime and abs(f["dev"])>=.45 and f["h1"]==sg and f["h4"]==sg and not (f["breakUp"] or f["breakDown"]))
    if eligible_limit and side=="BUY" and sl<f["ema15"]<f["entry"]:lim=f["ema15"]
    elif eligible_limit and side=="SELL" and f["entry"]<f["ema15"]<sl:lim=f["ema15"]
    else:lim=f["entry"]-(.18*risk if side=="BUY" else -.18*risk)
    return {k:v for k,v in f.items() if k not in ("pre","h1rows")} | {"model":model,"side":side,"score":sc,"mode":mode,"impulseEvidence":impulse,"regimeEvidence":regime,"risk":risk,"sl":sl,"tp":tp,"rr":rr,"expiryH":expiry,"limit":lim,"limitEligible":eligible_limit}

def dir_eval(t,rows,cut):
    sg=1 if t["side"]=="BUY" else -1;en=t["entry"];out={}
    for h in (3,6,12,24):
        z=base.before(rows,cut+timedelta(hours=h));out[str(h)+"h"]={"correct":((z-en)*sg>0) if z is not None else None,"close":z}
    ch=24 if t["mode"]=="REGIME_24H" else 3;out["chosen"]={"horizonH":ch,"correct":out[str(ch)+"h"]["correct"]};return out

def market_eval(t,rows,cut):
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=t["expiryH"])];mfe=mae=0.0
    for i,r in enumerate(fut,1):
        fav=(r["high"]-t["entry"]) if t["side"]=="BUY" else (t["entry"]-r["low"]);adv=(t["entry"]-r["low"]) if t["side"]=="BUY" else (r["high"]-t["entry"])
        mfe=max(mfe,fav/t["risk"]);mae=max(mae,adv/t["risk"])
        hs=r["low"]<=t["sl"] if t["side"]=="BUY" else r["high"]>=t["sl"];ht=r["high"]>=t["tp"] if t["side"]=="BUY" else r["low"]<=t["tp"]
        if hs and ht:return {"result":"AMBIGUOUS","bars":i,"mfeR":mfe,"maeR":mae}
        if hs:return {"result":"SL","bars":i,"mfeR":mfe,"maeR":mae}
        if ht:return {"result":"TP","bars":i,"mfeR":mfe,"maeR":mae}
    return {"result":"TIMEOUT","bars":len(fut),"mfeR":mfe,"maeR":mae}

def limit_eval(t,rows,cut):
    pending=4 if t["mode"]=="REGIME_24H" else 1.25;fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=t["expiryH"])];fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=pending):break
        target=r["high"]>=t["tp"] if t["side"]=="BUY" else r["low"]<=t["tp"];fill=r["low"]<=t["limit"] if t["side"]=="BUY" else r["high"]>=t["limit"]
        if target and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False}
    lr=abs(t["limit"]-t["sl"]);eff=abs(t["tp"]-t["limit"])/lr if lr else None
    for j,r in enumerate(fut[fi:],1):
        hs=r["low"]<=t["sl"] if t["side"]=="BUY" else r["high"]>=t["sl"];ht=r["high"]>=t["tp"] if t["side"]=="BUY" else r["low"]<=t["tp"]
        if hs and ht:return {"result":"AMBIGUOUS","filled":True,"effectiveRR":eff,"bars":j}
        if hs:return {"result":"SL","filled":True,"effectiveRR":eff,"bars":j}
        if ht:return {"result":"TP","filled":True,"effectiveRR":eff,"bars":j}
    return {"result":"TIMEOUT","filled":True,"effectiveRR":eff,"bars":len(fut)-fi}

def rec_eval(t,m,l):
    return (l|{"execution":"LIMIT"}) if t["limitEligible"] else (m|{"execution":"MARKET"})

def summary(rows,key):
    outs=[x[key] for x in rows];resolved=[(i,o) for i,o in enumerate(outs) if o["result"] in ("TP","SL")];w=sum(o["result"]=="TP" for _,o in resolved);tot=0.0
    for i,o in resolved:
        if o["result"]=="SL":tot-=1
        else:tot+=(rows[i]["trade"]["rr"] if o.get("execution","MARKET")=="MARKET" and key!="limit" else o.get("effectiveRR",rows[i]["trade"]["rr"]))
    return {"signals":len(rows),"resolved":len(resolved),"wins":w,"losses":len(resolved)-w,"winRateResolved":round(100*w/len(resolved),2) if resolved else None,"expectancyR":round(tot/len(resolved),3) if resolved else None,"timeouts":sum(o["result"]=="TIMEOUT" for o in outs),"noFill":sum(o["result"]=="NO_FILL" for o in outs),"targetBeforeFill":sum(o["result"]=="TARGET_BEFORE_FILL" for o in outs)}

def dirsum(rows,k):
    v=[x["direction"][k]["correct"] for x in rows if x["direction"][k]["correct"] is not None];return {"n":len(v),"correct":sum(v),"accuracy":round(100*sum(v)/len(v),2) if v else None}

def diagnostics(rows):
    sl=[x for x in rows if x["market"]["result"]=="SL"]
    biaswrong=sum(x["direction"]["chosen"]["correct"] is False for x in sl);barrier=sum(x["direction"]["chosen"]["correct"] is True for x in sl)
    return {"marketSL":len(sl),"slBiasWrong":biaswrong,"slButChosenDirectionCorrect":barrier,"slBut24hCorrect":sum(x["direction"]["24h"]["correct"] is True for x in sl),"avgSLMfeR":round(statistics.mean(x["market"].get("mfeR",0) for x in sl),3) if sl else None}

def dev_score(rows):
    if not rows:return -999
    ds=dirsum(rows,"chosen");sm=summary(rows,"market");da=(ds["accuracy"] or 0)/100;ex=sm["expectancyR"] if sm["expectancyR"] is not None else -1;to=sm["timeouts"]/max(1,sm["signals"])
    return round(.65*(da-.50)+.35*ex-.10*to,5)

def build_rows(frames,cuts,model_map=None,all_models=False):
    rows=[]
    for cs in cuts:
        cut=base.DT(cs);sp=strength_pack(frames,cut)
        for p in PAIRS:
            cf=core_feature(p,frames[p],cut,sp)
            if not cf:continue
            models=CANDIDATES if all_models else (model_map[cf["group"]],)
            for model in models:
                t=build_trade(cf,model);d=dir_eval(t,frames[p],cut);m=market_eval(t,frames[p],cut);l=limit_eval(t,frames[p],cut);r=rec_eval(t,m,l)
                rows.append({"cutoff":cs,"model":model,"trade":t,"direction":d,"market":m,"limit":l,"recommended":r})
    return rows

def main():
    raw=base.fetch();frames={p:base.norm(raw[p]) for p in PAIRS}
    dev=build_rows(frames,DEV,all_models=True);selection={};devdetail={}
    for g in ("USD_MAJOR","JPY_CROSS","EUROPE_CROSS","COMMODITY_CROSS","MIXED_CROSS"):
        scores={};stats={}
        for m in CANDIDATES:
            z=[x for x in dev if x["trade"]["group"]==g and x["model"]==m];scores[m]=dev_score(z);stats[m]={"score":scores[m],"market":summary(z,"market"),"chosenDirection":dirsum(z,"chosen")}
        best=max(scores,key=scores.get);selection[g]=best if scores[best]>=scores[DEFAULT_MODEL]+.04 else DEFAULT_MODEL;devdetail[g]={"chosen":selection[g],"candidates":stats}
    val=build_rows(frames,VAL,model_map=selection)
    bycut={};bysym={};bygroup={};bymode={}
    for cs in VAL:
        z=[x for x in val if x["cutoff"]==cs];bycut[cs]={"market":summary(z,"market"),"limit":summary(z,"limit"),"recommended":summary(z,"recommended"),"chosenDirection":dirsum(z,"chosen"),"direction3":dirsum(z,"3h"),"direction24":dirsum(z,"24h"),"diagnostics":diagnostics(z)}
    for p in PAIRS:
        z=[x for x in val if x["trade"]["symbol"]==p];bysym[p]={"market":summary(z,"market"),"recommended":summary(z,"recommended"),"chosenDirection":dirsum(z,"chosen"),"direction3":dirsum(z,"3h"),"direction24":dirsum(z,"24h"),"diagnostics":diagnostics(z)}
    for g in selection:
        z=[x for x in val if x["trade"]["group"]==g];bygroup[g]={"model":selection[g],"market":summary(z,"market"),"recommended":summary(z,"recommended"),"chosenDirection":dirsum(z,"chosen"),"diagnostics":diagnostics(z)}
    for md in ("IMPULSE_3H","REGIME_24H"):
        z=[x for x in val if x["trade"]["mode"]==md];bymode[md]={"signals":len(z),"market":summary(z,"market"),"recommended":summary(z,"recommended"),"chosenDirection":dirsum(z,"chosen"),"diagnostics":diagnostics(z)}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F8 factor-coherence + session + archetype walk-forward","method":"F8 keeps the minimal indicator stack but adds non-indicator state: 3/6/12/24/72h currency-factor coherence, cross-sectional dispersion/rank separation, 8h session position/breakout/sweep, and five interpretable pair archetype groups. Four predeclared low-complexity bias models are selected per archetype using only Apr27-May15 development outcomes. May18-May22 is untouched chronological blind holdout. F6 over-selected REGIME, so REGIME_24H is now exceptional and requires unanimous 24/72/H1/H4 persistence without a strong 3h factor veto. SL/TP/expiry are horizon-matched. LIMIT is eligible only for a genuine regime pullback. Bias-vs-barrier SL diagnostics are explicit.","integrity":{"walkForward":True,"developmentBeforeValidation":True,"validationDatesRepoSearchedAbsentBeforeCreation":True,"forcedAllPairs":True,"noTop3":True,"noNoTrade":True,"holdoutUsedForModelSelection":False,"historicalMacroReconstruction":False},"developmentDates":DEV,"validationDates":VAL,"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28,"rawCommitted":False},"archetypeModelSelection":devdetail,"selectedModels":selection,"summary":{"signals":len(val),"market":summary(val,"market"),"limit":summary(val,"limit"),"recommended":summary(val,"recommended"),"chosenDirection":dirsum(val,"chosen"),"direction3":dirsum(val,"3h"),"direction6":dirsum(val,"6h"),"direction12":dirsum(val,"12h"),"direction24":dirsum(val,"24h"),"avgRR":round(statistics.mean(x["trade"]["rr"] for x in val),3),"impulseCount":sum(x["trade"]["mode"]=="IMPULSE_3H" for x in val),"regimeCount":sum(x["trade"]["mode"]=="REGIME_24H" for x in val),"limitEligible":sum(x["trade"]["limitEligible"] for x in val),"diagnostics":diagnostics(val)},"byMode":bymode,"byGroup":bygroup,"byCutoff":bycut,"bySymbol":bysym,"trades":val}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f8.json","w",encoding="utf-8") as z:json.dump(result,z,ensure_ascii=False,indent=2)
    print(json.dumps({"selectedModels":selection,"summary":result["summary"],"byMode":bymode,"byGroup":bygroup,"byCutoff":bycut},indent=2))

if __name__=="__main__":main()
