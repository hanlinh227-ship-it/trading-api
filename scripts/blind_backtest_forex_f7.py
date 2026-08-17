#!/usr/bin/env python3
import json, os
from datetime import datetime, timezone
import blind_backtest_forex_f6 as core

VAL=["2026-04-20T08:00:00Z","2026-04-21T08:00:00Z","2026-04-22T08:00:00Z","2026-04-23T08:00:00Z","2026-04-24T08:00:00Z"]
core.END_DATE="2026-04-25 08:00:00"
core._ST.clear(); core._FT.clear()

def sgn(x):
    return 1 if x>0 else -1 if x<0 else 0

def consensus_side(f):
    votes=[sgn(f["d6"]),sgn(f["d24"]),sgn(f["d72"]),int(f["h4trend"]),int(f["h1trend"])]
    pos=sum(v>0 for v in votes); neg=sum(v<0 for v in votes)
    if pos>=3:return "BUY"
    if neg>=3:return "SELL"
    if sgn(f["d6"])==sgn(f["d24"]) and sgn(f["d6"])!=0:return "BUY" if f["d6"]>0 else "SELL"
    if sgn(f["d24"])==sgn(f["d72"]) and sgn(f["d24"])!=0:return "BUY" if f["d24"]>0 else "SELL"
    if f["h4trend"]==f["h1trend"] and f["h4trend"]!=0:return "BUY" if f["h4trend"]>0 else "SELL"
    return core.base_side(f)

def evaluate(frames,mode):
    mk=[];lm=[];byc={};byp={p:[] for p in core.PAIRS};overrides=0
    for s in VAL:
        cut=core.dt(s);st=core.strength(frames,cut);cm=[];cl=[];ov=0
        for p in core.PAIRS:
            f=core.feat(p,frames[p],cut,st)
            if not f:continue
            base=core.base_side(f);side=consensus_side(f) if mode=="CONSENSUS" else base
            if side!=base:ov+=1;overrides+=1
            om=core.market(f,frames[p],cut,side);ol=core.limit(f,frames[p],cut,side)
            rec={"symbol":p,"cutoff":s,"outcome":om,"d6":core.hd(f,frames[p],cut,side,6),"d12":core.hd(f,frames[p],cut,side,12),"d24":core.hd(f,frames[p],cut,side,24)}
            li={"symbol":p,"cutoff":s,"outcome":ol};mk.append(rec);lm.append(li);cm.append(rec);cl.append(li);byp[p].append(rec)
        byc[s]={"overrides":ov,"market":core.sm(cm),"limit":core.slm(cl),"dir12":core.sd(cm,"d12"),"dir24":core.sd(cm,"d24"),"path":core.path(cm)}
    return {"market":core.sm(mk),"limit":core.slm(lm),"direction6h":core.sd(mk,"d6"),"direction12h":core.sd(mk,"d12"),"direction24h":core.sd(mk,"d24"),"path":core.path(mk),"overrides":overrides,"byCutoff":byc,"byPair":{p:{"market":core.sm(v),"dir12":core.sd(v,"d12"),"dir24":core.sd(v,"d24"),"path":core.path(v)} for p,v in byp.items()}}

def main():
    raw=core.fetch();frames={p:core.norm(raw[p]) for p in core.PAIRS}
    baseline=evaluate(frames,"BASELINE");consensus=evaluate(frames,"CONSENSUS")
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F7 five-vote consensus blind comparator","integrity":{"validationCutoffsRepoSearchedAbsentBeforeCreation":True,"rulesFrozenBeforeReveal":True,"allValidPairsForcedBuyOrSell":True,"sameBlindDataForBaselineAndF7":True,"noTop3":True},"method":{"hypothesis":"A simple majority across five distinct directional views (6h,24h,72h cross-currency strength,H4 trend,H1 trend) may be more robust than a continuous weighted score that can be dominated by one extreme input.","votes":["6h strength","24h strength","72h strength","H4 trend","H1 trend"],"fallback":"current baseline only if the five-vote set cannot form a majority after horizon/structure tie-breaks","unchanged":["minimal indicator stack","F5 dynamic structural SL","F5 economic liquidity/ADR TP","adaptive LIMIT"]},"dataPlan":{"provider":"Twelve Data","interval":"15min","pairs":28,"creditsExpected":28,"validationDates":VAL,"rawCommitted":False},"baselineOnSameHoldout":baseline,"f7ConsensusOnSameHoldout":consensus}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f7.json","w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({"baseline":{"market":baseline["market"],"limit":baseline["limit"],"dir12":baseline["direction12h"],"dir24":baseline["direction24h"],"path":baseline["path"]},"f7":{"market":consensus["market"],"limit":consensus["limit"],"dir12":consensus["direction12h"],"dir24":consensus["direction24h"],"path":consensus["path"],"overrides":consensus["overrides"]},"byCutoff":consensus["byCutoff"]},indent=2))
if __name__=="__main__":main()
