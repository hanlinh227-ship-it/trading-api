#!/usr/bin/env python3
import json, os, statistics
from datetime import datetime, timezone
from scripts import blind_backtest_forex_f8 as f8

VAL2=["2026-05-25T08:00:00Z","2026-05-26T08:00:00Z","2026-05-27T08:00:00Z","2026-05-28T08:00:00Z","2026-05-29T08:00:00Z"]
FROZEN_MODELS={
    "USD_MAJOR":"FACTOR_BAL",
    "JPY_CROSS":"SESSION_SWEEP",
    "EUROPE_CROSS":"FACTOR_BAL",
    "COMMODITY_CROSS":"FACTOR_FAST",
    "MIXED_CROSS":"FACTOR_BAL"
}
f8.base.END_DATE="2026-05-30 08:00:00"
f8.base.OUTPUTSIZE=5000

def main():
    raw=f8.base.fetch();frames={p:f8.base.norm(raw[p]) for p in f8.PAIRS}
    val=f8.build_rows(frames,VAL2,model_map=FROZEN_MODELS)
    bycut={};bygroup={};bymode={};bysym={}
    for cs in VAL2:
        z=[x for x in val if x["cutoff"]==cs]
        bycut[cs]={"market":f8.summary(z,"market"),"limit":f8.summary(z,"limit"),"recommended":f8.summary(z,"recommended"),"chosenDirection":f8.dirsum(z,"chosen"),"direction3":f8.dirsum(z,"3h"),"direction6":f8.dirsum(z,"6h"),"direction12":f8.dirsum(z,"12h"),"direction24":f8.dirsum(z,"24h"),"diagnostics":f8.diagnostics(z)}
    for g,m in FROZEN_MODELS.items():
        z=[x for x in val if x["trade"]["group"]==g]
        bygroup[g]={"model":m,"market":f8.summary(z,"market"),"limit":f8.summary(z,"limit"),"recommended":f8.summary(z,"recommended"),"chosenDirection":f8.dirsum(z,"chosen"),"direction6":f8.dirsum(z,"6h"),"direction12":f8.dirsum(z,"12h"),"direction24":f8.dirsum(z,"24h"),"diagnostics":f8.diagnostics(z)}
    for md in ("IMPULSE_3H","REGIME_24H"):
        z=[x for x in val if x["trade"]["mode"]==md]
        bymode[md]={"signals":len(z),"market":f8.summary(z,"market"),"limit":f8.summary(z,"limit"),"recommended":f8.summary(z,"recommended"),"chosenDirection":f8.dirsum(z,"chosen"),"diagnostics":f8.diagnostics(z)}
    for p in f8.PAIRS:
        z=[x for x in val if x["trade"]["symbol"]==p]
        bysym[p]={"market":f8.summary(z,"market"),"recommended":f8.summary(z,"recommended"),"direction6":f8.dirsum(z,"6h"),"direction12":f8.dirsum(z,"12h"),"direction24":f8.dirsum(z,"24h"),"diagnostics":f8.diagnostics(z)}
    result={
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "version":"FOREX F8 frozen second chronological holdout",
        "integrity":{"rulesUnchangedFromF8":True,"modelsFrozenBeforeHoldout2":True,"validationDatesRepoSearchedAbsentBeforeCreation":True,"firstF8HoldoutNotUsedToRetune":True,"forcedAllPairs":True,"noTop3":True,"noNoTrade":True},
        "sourceEngine":"scripts/blind_backtest_forex_f8.py",
        "frozenModels":FROZEN_MODELS,
        "validationDates":VAL2,
        "dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","creditsExpected":28,"rawCommitted":False},
        "summary":{"signals":len(val),"market":f8.summary(val,"market"),"limit":f8.summary(val,"limit"),"recommended":f8.summary(val,"recommended"),"chosenDirection":f8.dirsum(val,"chosen"),"direction3":f8.dirsum(val,"3h"),"direction6":f8.dirsum(val,"6h"),"direction12":f8.dirsum(val,"12h"),"direction24":f8.dirsum(val,"24h"),"avgRR":round(statistics.mean(x["trade"]["rr"] for x in val),3),"impulseCount":sum(x["trade"]["mode"]=="IMPULSE_3H" for x in val),"regimeCount":sum(x["trade"]["mode"]=="REGIME_24H" for x in val),"limitEligible":sum(x["trade"]["limitEligible"] for x in val),"diagnostics":f8.diagnostics(val)},
        "byMode":bymode,"byGroup":bygroup,"byCutoff":bycut,"bySymbol":bysym,"trades":val
    }
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f8_holdout2.json","w",encoding="utf-8") as z:json.dump(result,z,ensure_ascii=False,indent=2)
    print(json.dumps({"summary":result["summary"],"byGroup":bygroup,"byCutoff":bycut},indent=2))

if __name__=="__main__":main()
