#!/usr/bin/env python3
import json, math, os, statistics
from datetime import datetime, timedelta, timezone
from scripts import blind_backtest_forex_f4_allpairs_dynamic as base

PAIRS=base.PAIRS
CUTS=["2026-06-29T08:00:00Z","2026-07-01T08:00:00Z","2026-07-08T08:00:00Z","2026-07-13T08:00:00Z","2026-07-22T08:00:00Z"]
TRADE_H=8; LIMIT_H=2

# Currency behaviour profiles: only alter relative role of 6h impulse vs H1/H4 regime.
PROFILE={
"USD":{"imp":1.00,"reg":1.00},"EUR":{"imp":1.00,"reg":1.00},
"GBP":{"imp":1.05,"reg":.95},"JPY":{"imp":1.15,"reg":.85},
"CHF":{"imp":1.10,"reg":.90},"CAD":{"imp":.85,"reg":1.15},
"AUD":{"imp":1.15,"reg":.85},"NZD":{"imp":1.15,"reg":.85}}

def feature(pair,rows,cut,st):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<450:return None
    h1=base.agg(pre,1); h4=base.agg(pre,4)
    if len(h1)<80 or len(h4)<55:return None
    c=pre[-1]["close"]; a=base.atr(pre); hc=[x["close"] for x in h1]; q4=[x["close"] for x in h4]; mc=[x["close"] for x in pre]
    if not a:return None
    e4=base.ema(q4[-100:],20); e450=base.ema(q4[-140:],50); e1=base.ema(hc[-100:],20); e150=base.ema(hc[-140:],50); em=base.ema(mc[-100:],20)
    er=base.rsi(hc); ax=base.adx(h1)
    if None in (e4,e450,e1,e150,em,er,ax):return None
    b,q=pair[:3],pair[3:]; d6=st[6][b]-st[6][q]; d24=st[24][b]-st[24][q]; d72=st[72][b]-st[72][q]
    pimp=(PROFILE[b]["imp"]+PROFILE[q]["imp"])/2; preg=(PROFILE[b]["reg"]+PROFILE[q]["reg"])/2
    s4=1 if c>e4>e450 else -1 if c<e4<e450 else (1 if c>e4 else -1)
    s1=1 if c>e1>e150 else -1 if c<e1<e150 else (1 if c>e1 else -1)
    m4=(c-mc[-5])/a; sm=1 if c>em and m4>=0 else -1 if c<em and m4<=0 else (1 if c>em else -1)
    chase=abs(c-em)/a
    # F5: regime selection first. Aligned trend -> continuation. Conflict/extreme -> shorter-horizon tactical model.
    aligned=(s4==s1)
    stretched=(er>=68 or er<=32 or chase>=.85)
    impulse=1.45*d6+.55*d24+.20*d72+.55*sm
    regime=.95*s4+.85*s1+.25*d24+.20*d72
    if aligned and not stretched and ax>=18:
        score=pimp*.75*impulse+preg*1.15*regime
        mode="CONTINUATION"
    elif stretched and abs(d6)>=.75 and ((d6>0 and er>=65) or (d6<0 and er<=35)):
        # Exhaustion: do not blindly chase the latest 6h impulse. Anchor to H1/H4 regime.
        score=preg*1.20*regime-pimp*.35*d6+.20*sm
        mode="EXHAUSTION"
    else:
        score=pimp*1.20*impulse+preg*.60*regime
        mode="TACTICAL_6H"
    side="BUY" if score>=0 else "SELL"; sg=1 if side=="BUY" else -1
    # Stop calibrated to 6-8h horizon: most recent 6 M15 bars + ATR buffer.
    recent=pre[-6:]
    swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    raw=(c-swing) if side=="BUY" else (swing-c)
    risk=max(raw+.10*a,.70*a)
    if "JPY" in (b,q) or "GBP" in (b,q):risk=max(risk,.85*a)
    sl=c-risk if side=="BUY" else c+risk
    # TP is dynamic, deliberately shorter than F4 because the signal is a 6-8h forecast.
    agree=sum((x*sg)>0 for x in (d6,d24,d72))
    rr=.95+.18*agree+(.22 if ax>=25 else .08 if ax>=18 else -.08)+(.18 if aligned and s1==sg else 0)+(.10 if chase<.50 else -.08)
    if mode=="EXHAUSTION":rr-=.10
    rr=max(.75,min(1.85,rr))
    # Respect nearest pre-known H1 structure when it is inside the projected target.
    hi=max(x["high"] for x in h1[-16:]); lo=min(x["low"] for x in h1[-16:]); sd=(hi-c) if side=="BUY" else (c-lo)
    if sd>0 and .70<=sd/risk<=2.20:rr=min(rr,max(.72,sd/risk))
    tp=c+risk*rr if side=="BUY" else c-risk*rr
    # LIMIT only if price is actually extended; otherwise MARKET comparator remains primary.
    lim=(em if side=="BUY" and sl<em<c else em if side=="SELL" and c<em<sl else c-.15*risk if side=="BUY" else c+.15*risk)
    return {"symbol":pair,"side":side,"entry":c,"limit":lim,"sl":sl,"tp":tp,"risk":risk,"rr":rr,"score":score,"mode":mode,"adx":ax,"rsi":er,"d6":d6,"d24":d24,"d72":d72,"chaseATR":chase}

def direction_eval(f,rows,cut):
    sg=1 if f["side"]=="BUY" else -1; en=f["entry"]; out={}
    for h in (3,6,8,12,24):
        close=base.before(rows,cut+timedelta(hours=h))
        out[f"{h}h"]={"close":close,"correct":((close-en)*sg>0) if close is not None else None,"returnPct":((close/en-1)*100*sg) if close else None}
    return out

def market_eval(f,rows,cut):
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_H)]; side=f["side"]; sl=f["sl"]; tp=f["tp"]
    for i,r in enumerate(fut,1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl; b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:return {"result":"AMBIGUOUS","bars":i}
        if a:return {"result":"SL","bars":i}
        if b:return {"result":"TP","bars":i}
    return {"result":"TIMEOUT","bars":len(fut)}
def limit_eval(f,rows,cut):
    side=f["side"]; lim=f["limit"]; sl=f["sl"]; tp=f["tp"]
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_H)]; fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=LIMIT_H):break
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

def summary(rows,key):
    outs=[x[key] for x in rows]; res=[(i,o) for i,o in enumerate(outs) if o["result"] in ("TP","SL")]; w=sum(o["result"]=="TP" for _,o in res); l=len(res)-w
    total=0
    for i,o in res:
        total += (rows[i]["feature"]["rr"] if key=="market" else o.get("effectiveRR",0)) if o["result"]=="TP" else -1
    return {"signals":len(rows),"resolved":len(res),"wins":w,"losses":l,"winRateResolved":round(100*w/len(res),2) if res else None,"expectancyR":round(total/len(res),3) if res else None,"timeouts":sum(o["result"]=="TIMEOUT" for o in outs),"noFill":sum(o["result"]=="NO_FILL" for o in outs),"targetBeforeFill":sum(o["result"]=="TARGET_BEFORE_FILL" for o in outs)}
def dirsum(rows,h):
    v=[x["direction"][h]["correct"] for x in rows if x["direction"][h]["correct"] is not None]
    return {"n":len(v),"correct":sum(v),"accuracy":round(100*sum(v)/len(v),2) if v else None}

def main():
    raw=base.fetch(); frames={p:base.norm(raw[p]) for p in PAIRS}; allrows=[]; bycut={}
    for cs in CUTS:
        cut=base.DT(cs); st=base.strength(frames,cut); b=[]
        for p in PAIRS:
            f=feature(p,frames[p],cut,st)
            if not f:continue
            x={"cutoff":cs,"feature":f,"direction":direction_eval(f,frames[p],cut),"market":market_eval(f,frames[p],cut),"limit":limit_eval(f,frames[p],cut)}; b.append(x); allrows.append(x)
        bycut[cs]={"market":summary(b,"market"),"limit":summary(b,"limit"),**{f"direction{h}":dirsum(b,f"{h}h") for h in (3,6,8,12,24)}}
    bysym={}
    for p in PAIRS:
        g=[x for x in allrows if x["feature"]["symbol"]==p]; bysym[p]={"market":summary(g,"market"),"limit":summary(g,"limit"),**{f"direction{h}":dirsum(g,f"{h}h") for h in (3,6,8,12,24)}}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"FOREX F5 horizon-matched forced all-pair blind. Every pair gets BUY/SELL. F4 revealed that 6h direction retained signal while 12h/24h did not. F5 therefore separates CONTINUATION, TACTICAL_6H and EXHAUSTION regimes; currency profiles only change impulse-vs-regime weighting, with no extra indicators. H1/H4 remain regime context, M15/6h strength drives tactical direction. Structural SL and dynamic TP are sized for an 8h trade horizon. LIMIT only tests a 2h pullback; same frozen SL/TP. No historical macro/news reconstruction.","integrity":{"rulesFrozenBeforeValidation":True,"forcedAllPairs":True,"noNoTrade":True,"lookAheadDecision":False,"f4DatesUsedOnlyForDiagnosis":True},"cutoffs":CUTS,"dataPlan":{"provider":"Twelve Data","creditsExpected":28,"intervalFetched":"15min"},"summary":{"signals":len(allrows),"market":summary(allrows,"market"),"limit":summary(allrows,"limit"),**{f"direction{h}":dirsum(allrows,f"{h}h") for h in (3,6,8,12,24)},"avgPlannedRR":round(statistics.mean(x["feature"]["rr"] for x in allrows),3)},"byCutoff":bycut,"bySymbol":bysym,"trades":allrows}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f5_horizon.json","w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({"summary":result["summary"],"byCutoff":bycut,"bySymbol":bysym},indent=2))
if __name__=="__main__":main()
