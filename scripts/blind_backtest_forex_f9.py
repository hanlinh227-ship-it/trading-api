#!/usr/bin/env python3
import json, math, os, statistics
from datetime import datetime, timedelta, timezone
from scripts import blind_backtest_forex_f4_allpairs_dynamic as base

PAIRS=base.PAIRS; CCY=base.CCY
DEV=[
"2026-04-27T08:00:00Z","2026-04-28T08:00:00Z","2026-04-29T08:00:00Z","2026-04-30T08:00:00Z","2026-05-01T08:00:00Z",
"2026-05-04T08:00:00Z","2026-05-05T08:00:00Z","2026-05-06T08:00:00Z","2026-05-07T08:00:00Z","2026-05-08T08:00:00Z",
"2026-05-11T08:00:00Z","2026-05-12T08:00:00Z","2026-05-13T08:00:00Z","2026-05-14T08:00:00Z","2026-05-15T08:00:00Z",
"2026-05-18T08:00:00Z","2026-05-19T08:00:00Z","2026-05-20T08:00:00Z","2026-05-21T08:00:00Z","2026-05-22T08:00:00Z"]
VAL=["2026-05-25T08:00:00Z","2026-05-26T08:00:00Z","2026-05-27T08:00:00Z","2026-05-28T08:00:00Z","2026-05-29T08:00:00Z"]
CANDIDATES=("FACTOR_FAST","FACTOR_BAL","FACTOR_ONLY","STRUCTURE","SESSION_SWEEP","RELATIVE_REVERT")
DEFAULT={"USD_MAJOR":"FACTOR_BAL","JPY_CROSS":"SESSION_SWEEP","EUROPE_CROSS":"FACTOR_BAL","COMMODITY_CROSS":"FACTOR_FAST","MIXED_CROSS":"FACTOR_BAL"}
base.END_DATE="2026-05-30 08:00:00"; base.OUTPUTSIZE=5000

def sgn(x):return 1 if x>0 else -1 if x<0 else 0

def group(pair):
    b,q=pair[:3],pair[3:]
    if "USD" in (b,q):return "USD_MAJOR"
    if "JPY" in (b,q):return "JPY_CROSS"
    if b in ("AUD","NZD","CAD") and q in ("AUD","NZD","CAD"):return "COMMODITY_CROSS"
    if b in ("EUR","GBP","CHF") and q in ("EUR","GBP","CHF"):return "EUROPE_CROSS"
    return "MIXED_CROSS"

def strength_pack(frames,cut):
    hs=(3,6,12,24,72);pairret={h:{} for h in hs}
    for p,rows in frames.items():
        pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
        if not pre:continue
        now=pre[-1]["close"]
        for h in hs:
            old=base.before(pre,cut-timedelta(hours=h))
            if old and old>0:pairret[h][p]=math.log(now/old)
    z={h:base.zmap(pairret[h]) for h in hs};out={};disp={}
    for h in hs:
        vals={c:[] for c in CCY}
        for p,v in z[h].items():
            b,q=p[:3],p[3:];vals[b].append(v);vals[q].append(-v)
        strength={c:(statistics.mean(v) if v else 0) for c,v in vals.items()};coh={}
        for c,v in vals.items():
            non=[x for x in v if abs(x)>1e-12];coh[c]=abs(sum(sgn(x) for x in non))/len(non) if non else 0
        order=sorted(CCY,key=lambda c:strength[c],reverse=True);rank={c:i for i,c in enumerate(order)}
        out[h]={"strength":strength,"coherence":coh,"rank":rank};disp[h]=statistics.pstdev(strength.values()) if len(strength)>1 else 0
    return {"h":out,"dispersion":disp}

def feat(pair,rows,cut,sp):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<700:return None
    h1=base.agg(pre,1);h4=base.agg(pre,4)
    if len(h1)<120 or len(h4)<65:return None
    c=pre[-1]["close"];a=base.atr(pre);ax=base.adx(h1)
    if not a or ax is None:return None
    mc=[x["close"] for x in pre];h1c=[x["close"] for x in h1];h4c=[x["close"] for x in h4]
    e15=base.ema(mc[-120:],20);e1=base.ema(h1c[-130:],20);e150=base.ema(h1c[-170:],50);e4=base.ema(h4c[-90:],20);e450=base.ema(h4c[-130:],50);rsi=base.rsi(h1c)
    if None in (e15,e1,e150,e4,e450,rsi):return None
    h1s=1 if c>e1>e150 else -1 if c<e1<e150 else (1 if c>e1 else -1);h4s=1 if c>e4>e450 else -1 if c<e4<e450 else (1 if c>e4 else -1)
    b,q=pair[:3],pair[3:];d={h:sp["h"][h]["strength"][b]-sp["h"][h]["strength"][q] for h in (3,6,12,24,72)}
    c3=min(sp["h"][3]["coherence"][b],sp["h"][3]["coherence"][q]);c24=min(sp["h"][24]["coherence"][b],sp["h"][24]["coherence"][q])
    rg3=sp["h"][3]["rank"][q]-sp["h"][3]["rank"][b];rg24=sp["h"][24]["rank"][q]-sp["h"][24]["rank"][b]
    fq3=c3*abs(d[3])/(sp["dispersion"][3]+1e-9);fq24=c24*abs(d[24])/(sp["dispersion"][24]+1e-9)
    m1=(c-mc[-5])/a;m3=(c-mc[-13])/a;dev=(c-e15)/a
    sess=pre[-32:];prior=pre[-96:-32];sh=max(x["high"] for x in sess);sl=min(x["low"] for x in sess);so=sess[0]["open"];sr=(c-so)/a;spx=(c-sl)/(sh-sl) if sh>sl else .5
    ph=max(x["high"] for x in prior);pl=min(x["low"] for x in prior);su=sh>ph and c<ph;sd=sl<pl and c>pl;bu=c>ph;bd=c<pl
    return {"symbol":pair,"group":group(pair),"pre":pre,"h1rows":h1,"entry":c,"atr":a,"adx":ax,"rsi":rsi,"ema15":e15,"h1":h1s,"h4":h4s,"d3":d[3],"d6":d[6],"d12":d[12],"d24":d[24],"d72":d[72],"coh3":c3,"coh24":c24,"fq3":fq3,"fq24":fq24,"rankgap3":rg3,"rankgap24":rg24,"mom1":m1,"mom3":m3,"dev":dev,"sessionRet":sr,"sessionPos":spx,"sweepUp":su,"sweepDown":sd,"breakUp":bu,"breakDown":bd}

def score(f,m):
    d3,d6,d12,d24,d72=f["d3"],f["d6"],f["d12"],f["d24"],f["d72"];sr=f["sessionRet"];m1=f["mom1"];m3=f["mom3"];h1=f["h1"];h4=f["h4"]
    q3=.72+.28*min(1.5,f["fq3"]);q24=.72+.28*min(1.5,f["fq24"])
    if m=="FACTOR_FAST":s=q3*(1.50*d3+.80*d6+.25*d12)+.28*max(-2,min(2,sr))+.18*max(-2,min(2,m1))
    elif m=="FACTOR_ONLY":s=q3*(1.45*d3+1.00*d6+.35*d12)+q24*(.35*d24+.12*d72)
    elif m=="STRUCTURE":
        s=.40*d3+.60*d6+.30*d12+q24*(.75*d24+.45*d72)+.90*h1+.65*h4+.18*max(-2,min(2,m3))
        if sgn(d6) and sgn(s)!=sgn(d6) and abs(f["rankgap3"])>=4 and f["coh3"]>=.4:s*=.4
    elif m=="SESSION_SWEEP":
        s=q3*(1.00*d3+.80*d6+.25*d12)+.62*max(-2,min(2,sr))+.22*max(-2,min(2,m1))+.15*h1
        if f["sweepUp"] and f["rsi"]>=57:s=-abs(s)-.35
        if f["sweepDown"] and f["rsi"]<=43:s=abs(s)+.35
    elif m=="RELATIVE_REVERT":
        s=.30*d3+.55*d6+.55*d12+.45*d24+.20*d72+.25*h1+.15*h4-.48*max(-2,min(2,sr))-.28*max(-2,min(2,m1))
        if f["sweepUp"]:s-=.25
        if f["sweepDown"]:s+=.25
    else:s=q3*(1.15*d3+.90*d6+.30*d12)+.38*d24+.15*d72+.32*h1+.18*h4+.18*max(-2,min(2,sr))
    g=f["group"]
    if g=="JPY_CROSS":s+=.14*sgn(sr)+.10*sgn(d6)
    elif g=="EUROPE_CROSS":s+=.10*sgn(d6)
    elif g=="COMMODITY_CROSS":s+=.10*sgn(d6)+.08*sgn(d24)
    elif g=="USD_MAJOR":s+=.08*sgn(d6)+.06*sgn(d24)
    return s

def trade(f,m):
    sc=score(f,m);side="BUY" if sc>=0 else "SELL";sg=1 if side=="BUY" else -1
    fast=sum(x*sg>0 for x in (f["d3"],f["d6"],f["sessionRet"],f["mom1"]));intra=sum(x*sg>0 for x in (f["d6"],f["d12"],f["sessionRet"],f["h1"]));reg=sum(x*sg>0 for x in (f["d24"],f["d72"],f["h1"],f["h4"]))
    strongopp=(f["d6"]*sg<0 and abs(f["rankgap3"])>=4 and f["coh3"]>=.4)
    fastmode=(fast>=4 and f["fq3"]>=.85 and abs(f["rankgap3"])>=5 and (f["breakUp"] or f["breakDown"] or abs(f["sessionRet"])>=1.0))
    regmode=(reg==4 and not strongopp and f["fq24"]>=.55 and f["adx"]>=20 and intra<=2)
    mode="FAST_3H" if fastmode else "REGIME_24H" if regmode else "INTRADAY_8H"
    if mode=="FAST_3H":recent=f["pre"][-7:];floor=.62*f["atr"];cap=1.55*f["atr"];expiry=4;rr=1.05+.10*fast+.10*min(1.2,f["fq3"])+(.10 if f["adx"]>=20 else 0);rr=max(.95,min(1.60,rr))
    elif mode=="REGIME_24H":recent=f["pre"][-20:];floor=1.0*f["atr"];cap=2.35*f["atr"];expiry=24;rr=1.42+.11*reg+.10*min(1.2,f["fq24"])+(.15 if f["adx"]>=24 else 0);rr=max(1.35,min(2.25,rr))
    else:recent=f["pre"][-12:];floor=.82*f["atr"];cap=1.90*f["atr"];expiry=10;rr=1.22+.09*intra+.08*min(1.2,f["fq3"])+(.10 if f["adx"]>=20 else 0);rr=max(1.15,min(1.85,rr))
    if "JPY" in (f["symbol"][:3],f["symbol"][3:]) or "GBP" in (f["symbol"][:3],f["symbol"][3:]):floor+=.08*f["atr"]
    swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent);raw=(f["entry"]-swing) if side=="BUY" else (swing-f["entry"]);risk=min(max(raw+.10*f["atr"],floor),cap);sl=f["entry"]-risk if side=="BUY" else f["entry"]+risk
    win=10 if mode=="FAST_3H" else 18 if mode=="INTRADAY_8H" else 30;h=f["h1rows"];hh=max(x["high"] for x in h[-win:]);ll=min(x["low"] for x in h[-win:]);dist=(hh-f["entry"]) if side=="BUY" else (f["entry"]-ll);fr=.95 if mode=="FAST_3H" else 1.15 if mode=="INTRADAY_8H" else 1.35
    if dist>0 and fr<=dist/risk<=2.7:rr=min(rr,max(fr,dist/risk))
    tp=f["entry"]+risk*rr if side=="BUY" else f["entry"]-risk*rr
    eligible=(mode!="FAST_3H" and abs(f["dev"])>=.55 and f["h1"]==sg and not (f["breakUp"] or f["breakDown"]) and f["sessionRet"]*sg>0)
    if eligible and side=="BUY" and sl<f["ema15"]<f["entry"]:lim=f["ema15"]
    elif eligible and side=="SELL" and f["entry"]<f["ema15"]<sl:lim=f["ema15"]
    else:lim=f["entry"]-(.16*risk if side=="BUY" else -.16*risk)
    return {k:v for k,v in f.items() if k not in ("pre","h1rows")}|{"model":m,"side":side,"score":sc,"mode":mode,"fastEvidence":fast,"intradayEvidence":intra,"regimeEvidence":reg,"risk":risk,"sl":sl,"tp":tp,"rr":rr,"expiryH":expiry,"limit":lim,"limitEligible":eligible}

def direval(t,rows,cut):
    sg=1 if t["side"]=="BUY" else -1;en=t["entry"];o={}
    for h in (3,6,8,12,24):
        z=base.before(rows,cut+timedelta(hours=h));o[f"{h}h"]={"correct":((z-en)*sg>0) if z is not None else None,"close":z}
    ch=3 if t["mode"]=="FAST_3H" else 24 if t["mode"]=="REGIME_24H" else 8;o["chosen"]={"horizonH":ch,"correct":o[f"{ch}h"]["correct"]};return o

def market(t,rows,cut):
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=t["expiryH"])];mfe=mae=0
    for i,r in enumerate(fut,1):
        fav=(r["high"]-t["entry"]) if t["side"]=="BUY" else (t["entry"]-r["low"]);adv=(t["entry"]-r["low"]) if t["side"]=="BUY" else (r["high"]-t["entry"]);mfe=max(mfe,fav/t["risk"]);mae=max(mae,adv/t["risk"])
        hs=r["low"]<=t["sl"] if t["side"]=="BUY" else r["high"]>=t["sl"];ht=r["high"]>=t["tp"] if t["side"]=="BUY" else r["low"]<=t["tp"]
        if hs and ht:return {"result":"AMBIGUOUS","bars":i,"mfeR":mfe,"maeR":mae}
        if hs:return {"result":"SL","bars":i,"mfeR":mfe,"maeR":mae}
        if ht:return {"result":"TP","bars":i,"mfeR":mfe,"maeR":mae}
    return {"result":"TIMEOUT","bars":len(fut),"mfeR":mfe,"maeR":mae}

def limit(t,rows,cut):
    pending=1.25 if t["mode"]=="FAST_3H" else 2.5 if t["mode"]=="INTRADAY_8H" else 4;fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=t["expiryH"])];fi=None
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

def recommended(t,m,l):return (l|{"execution":"LIMIT"}) if t["limitEligible"] else (m|{"execution":"MARKET"})

def sm(rows,key):
    outs=[x[key] for x in rows];res=[(i,o) for i,o in enumerate(outs) if o["result"] in ("TP","SL")];w=sum(o["result"]=="TP" for _,o in res);tot=0
    for i,o in res:
        if o["result"]=="SL":tot-=1
        else:tot+=o.get("effectiveRR",rows[i]["trade"]["rr"])
    return {"signals":len(rows),"resolved":len(res),"wins":w,"losses":len(res)-w,"winRateResolved":round(100*w/len(res),2) if res else None,"expectancyR":round(tot/len(res),3) if res else None,"timeouts":sum(o["result"]=="TIMEOUT" for o in outs),"noFill":sum(o["result"]=="NO_FILL" for o in outs),"targetBeforeFill":sum(o["result"]=="TARGET_BEFORE_FILL" for o in outs)}
def sd(rows,k):
    v=[x["direction"][k]["correct"] for x in rows if x["direction"][k]["correct"] is not None];return {"n":len(v),"correct":sum(v),"accuracy":round(100*sum(v)/len(v),2) if v else None}
def diag(rows):
    sl=[x for x in rows if x["market"]["result"]=="SL"]
    return {"marketSL":len(sl),"slBiasWrong":sum(x["direction"]["chosen"]["correct"] is False for x in sl),"slButChosenCorrect":sum(x["direction"]["chosen"]["correct"] is True for x in sl),"slBut6hCorrect":sum(x["direction"]["6h"]["correct"] is True for x in sl),"slBut12hCorrect":sum(x["direction"]["12h"]["correct"] is True for x in sl),"slBut24hCorrect":sum(x["direction"]["24h"]["correct"] is True for x in sl),"avgSLMfeR":round(statistics.mean(x["market"].get("mfeR",0) for x in sl),3) if sl else None}
def devscore(rows):
    if not rows:return -999
    a6=(sd(rows,"6h")["accuracy"] or 0)/100;a12=(sd(rows,"12h")["accuracy"] or 0)/100;e=sm(rows,"market")["expectancyR"] or -1;to=sm(rows,"market")["timeouts"]/max(1,len(rows));return round(.32*(a6-.5)+.23*(a12-.5)+.45*e-.08*to,5)

def build(frames,cuts,models=None,allmodels=False):
    out=[]
    for cs in cuts:
        cut=base.DT(cs);sp=strength_pack(frames,cut)
        for p in PAIRS:
            f=feat(p,frames[p],cut,sp)
            if not f:continue
            ms=CANDIDATES if allmodels else (models[f["group"]],)
            for m in ms:
                t=trade(f,m);d=direval(t,frames[p],cut);mk=market(t,frames[p],cut);lm=limit(t,frames[p],cut);rc=recommended(t,mk,lm);out.append({"cutoff":cs,"model":m,"trade":t,"direction":d,"market":mk,"limit":lm,"recommended":rc})
    return out

def main():
    raw=base.fetch();frames={p:base.norm(raw[p]) for p in PAIRS};dev=build(frames,DEV,allmodels=True);sel={};devdetail={}
    groups=("USD_MAJOR","JPY_CROSS","EUROPE_CROSS","COMMODITY_CROSS","MIXED_CROSS")
    for g in groups:
        scores={};stats={}
        for m in CANDIDATES:
            z=[x for x in dev if x["trade"]["group"]==g and x["model"]==m];scores[m]=devscore(z);stats[m]={"score":scores[m],"market":sm(z,"market"),"dir6":sd(z,"6h"),"dir12":sd(z,"12h")}
        best=max(scores,key=scores.get);d=DEFAULT[g];sel[g]=best if scores[best]>=scores[d]+.03 else d;devdetail[g]={"chosen":sel[g],"candidates":stats}
    val=build(frames,VAL,models=sel);bycut={};bygroup={};bymode={};bysym={}
    for cs in VAL:
        z=[x for x in val if x["cutoff"]==cs];bycut[cs]={"market":sm(z,"market"),"limit":sm(z,"limit"),"recommended":sm(z,"recommended"),"dir6":sd(z,"6h"),"dir8":sd(z,"8h"),"dir12":sd(z,"12h"),"dir24":sd(z,"24h"),"diagnostics":diag(z)}
    for g in groups:
        z=[x for x in val if x["trade"]["group"]==g];bygroup[g]={"model":sel[g],"market":sm(z,"market"),"recommended":sm(z,"recommended"),"dir6":sd(z,"6h"),"dir12":sd(z,"12h"),"diagnostics":diag(z)}
    for md in ("FAST_3H","INTRADAY_8H","REGIME_24H"):
        z=[x for x in val if x["trade"]["mode"]==md];bymode[md]={"signals":len(z),"market":sm(z,"market"),"recommended":sm(z,"recommended"),"chosenDirection":sd(z,"chosen"),"diagnostics":diag(z)}
    for p in PAIRS:
        z=[x for x in val if x["trade"]["symbol"]==p];bysym[p]={"market":sm(z,"market"),"recommended":sm(z,"recommended"),"dir6":sd(z,"6h"),"dir12":sd(z,"12h"),"dir24":sd(z,"24h"),"diagnostics":diag(z)}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F9 three-horizon factor-state walk-forward","method":"F9 retains F8 factor coherence/session/archetype design but corrects the horizon mismatch revealed by F8. FAST_3H is rare and requires extreme coherent factor separation; INTRADAY_8H is the default; REGIME_24H remains exceptional. Model selection per archetype now scores 6h/12h direction plus expectancy on development only. FACTOR_ONLY reduces idiosyncratic price noise, while RELATIVE_REVERT is a predeclared alternative for Europe crosses. LIMIT is used only for a controlled intraday/regime pullback. No new overlapping indicators or historical macro hindsight.","integrity":{"walkForward":True,"developmentBeforeValidation":True,"validationDatesRepoSearchedAbsentBeforeCreation":True,"forcedAllPairs":True,"noTop3":True,"noNoTrade":True,"holdoutUsedForSelection":False},"developmentDates":DEV,"validationDates":VAL,"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28,"rawCommitted":False},"selectedModels":sel,"archetypeModelSelection":devdetail,"summary":{"signals":len(val),"market":sm(val,"market"),"limit":sm(val,"limit"),"recommended":sm(val,"recommended"),"chosenDirection":sd(val,"chosen"),"direction3":sd(val,"3h"),"direction6":sd(val,"6h"),"direction8":sd(val,"8h"),"direction12":sd(val,"12h"),"direction24":sd(val,"24h"),"avgRR":round(statistics.mean(x["trade"]["rr"] for x in val),3),"fastCount":sum(x["trade"]["mode"]=="FAST_3H" for x in val),"intradayCount":sum(x["trade"]["mode"]=="INTRADAY_8H" for x in val),"regimeCount":sum(x["trade"]["mode"]=="REGIME_24H" for x in val),"limitEligible":sum(x["trade"]["limitEligible"] for x in val),"diagnostics":diag(val)},"byMode":bymode,"byGroup":bygroup,"byCutoff":bycut,"bySymbol":bysym,"trades":val}
    os.makedirs("data",exist_ok=True);json.dump(result,open("data/blind_backtest_forex_f9.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(json.dumps({"selectedModels":sel,"summary":result["summary"],"byMode":bymode,"byGroup":bygroup,"byCutoff":bycut},indent=2))
if __name__=="__main__":main()
