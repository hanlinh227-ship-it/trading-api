#!/usr/bin/env python3
import json, math, os, statistics
from datetime import datetime, timedelta, timezone
from scripts import blind_backtest_forex_f8 as f8

PAIRS=f8.PAIRS; CCY=f8.CCY
VAL=["2026-06-01T08:00:00Z","2026-06-02T08:00:00Z","2026-06-03T08:00:00Z","2026-06-04T08:00:00Z","2026-06-05T08:00:00Z"]
FROZEN={"USD_MAJOR":"FACTOR_BAL","JPY_CROSS":"SESSION_SWEEP","EUROPE_CROSS":"FACTOR_BAL","COMMODITY_CROSS":"FACTOR_FAST","MIXED_CROSS":"FACTOR_BAL"}
f8.base.END_DATE="2026-06-06 08:00:00"; f8.base.OUTPUTSIZE=5000

def strength_pack_loo(frames,cut,excluded):
    hs=(3,6,12,24,72); pairret={h:{} for h in hs}
    for p,rows in frames.items():
        if p==excluded: continue
        pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
        if not pre: continue
        now=pre[-1]["close"]
        for h in hs:
            old=f8.base.before(pre,cut-timedelta(hours=h))
            if old and old>0: pairret[h][p]=math.log(now/old)
    z={h:f8.base.zmap(pairret[h]) for h in hs};out={};disp={}
    for h in hs:
        vals={c:[] for c in CCY}
        for p,v in z[h].items():
            b,q=p[:3],p[3:];vals[b].append(v);vals[q].append(-v)
        strength={c:(statistics.mean(v) if v else 0.0) for c,v in vals.items()};coh={}
        for c,v in vals.items():
            non=[x for x in v if abs(x)>1e-12]
            coh[c]=abs(sum(f8.sgn(x) for x in non))/len(non) if non else 0.0
        order=sorted(CCY,key=lambda c:strength[c],reverse=True);rank={c:i for i,c in enumerate(order)}
        out[h]={"strength":strength,"coherence":coh,"rank":rank};disp[h]=statistics.pstdev(strength.values()) if len(strength)>1 else 0.0
    return {"h":out,"dispersion":disp}

def build_loo(frames):
    rows=[]
    for cs in VAL:
        cut=f8.base.DT(cs)
        for p in PAIRS:
            sp=strength_pack_loo(frames,cut,p);cf=f8.core_feature(p,frames[p],cut,sp)
            if not cf:continue
            model=FROZEN[cf["group"]];t=f8.build_trade(cf,model);d=f8.dir_eval(t,frames[p],cut);m=f8.market_eval(t,frames[p],cut);l=f8.limit_eval(t,frames[p],cut);r=f8.rec_eval(t,m,l)
            rows.append({"cutoff":cs,"model":model,"trade":t,"direction":d,"market":m,"limit":l,"recommended":r})
    return rows

def branch(rows):
    return {"market":f8.summary(rows,"market"),"limit":f8.summary(rows,"limit"),"recommended":f8.summary(rows,"recommended"),"chosenDirection":f8.dirsum(rows,"chosen"),"direction3":f8.dirsum(rows,"3h"),"direction6":f8.dirsum(rows,"6h"),"direction12":f8.dirsum(rows,"12h"),"direction24":f8.dirsum(rows,"24h"),"avgRR":round(statistics.mean(x["trade"]["rr"] for x in rows),3),"diagnostics":f8.diagnostics(rows)}

def main():
    raw=f8.base.fetch();frames={p:f8.base.norm(raw[p]) for p in PAIRS}
    baseline=f8.build_rows(frames,VAL,model_map=FROZEN);loo=build_loo(frames)
    bycut={};bygroup={};bysym={}
    groups=("USD_MAJOR","JPY_CROSS","EUROPE_CROSS","COMMODITY_CROSS","MIXED_CROSS")
    for cs in VAL:
        bycut[cs]={"baseline":branch([x for x in baseline if x["cutoff"]==cs]),"loo":branch([x for x in loo if x["cutoff"]==cs])}
    for g in groups:
        bygroup[g]={"baseline":branch([x for x in baseline if x["trade"]["group"]==g]),"loo":branch([x for x in loo if x["trade"]["group"]==g])}
    for p in PAIRS:
        bysym[p]={"baseline":branch([x for x in baseline if x["trade"]["symbol"]==p]),"loo":branch([x for x in loo if x["trade"]["symbol"]==p])}
    b=branch(baseline);l=branch(loo)
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F10 leave-one-pair-out factor isolation","method":"Direct frozen-engine comparator on a new blind block. Baseline is unchanged F8. F10 changes only one thing: when scoring a pair, that pair is excluded from the 28-pair network before currency strength/coherence/ranks are computed. This tests whether self-inclusion contaminates the cross-currency factor signal. Models, indicators, barriers, RR, horizon classification and execution rules are unchanged from F8.","integrity":{"validationDatesRepoSearchedAbsentBeforeCreation":True,"forcedAllPairs":True,"noTop3":True,"noNoTrade":True,"f8RulesFrozen":True,"onlyChangeIsLeaveOnePairOutStrength":True,"outcomesNotUsedBeforeRulesFrozen":True},"validationDates":VAL,"frozenModels":FROZEN,"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28,"rawCommitted":False},"baselineF8":b,"f10LeaveOneOut":l,"delta":{"marketWR":round((l["market"]["winRateResolved"] or 0)-(b["market"]["winRateResolved"] or 0),2),"marketExpectancyR":round((l["market"]["expectancyR"] or 0)-(b["market"]["expectancyR"] or 0),3),"recommendedExpectancyR":round((l["recommended"]["expectancyR"] or 0)-(b["recommended"]["expectancyR"] or 0),3),"direction3":round((l["direction3"]["accuracy"] or 0)-(b["direction3"]["accuracy"] or 0),2),"direction24":round((l["direction24"]["accuracy"] or 0)-(b["direction24"]["accuracy"] or 0),2)},"byCutoff":bycut,"byGroup":bygroup,"bySymbol":bysym}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f10_loo.json","w",encoding="utf-8") as z:json.dump(result,z,ensure_ascii=False,indent=2)
    print(json.dumps({"baselineF8":b,"f10LeaveOneOut":l,"delta":result["delta"],"byGroup":bygroup,"byCutoff":bycut},indent=2))
if __name__=="__main__":main()
