#!/usr/bin/env python3
"""Canonical V76 Forex entry-research runner."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import research_v76_entry_forex as base
import evaluate_v76_entry_forex as ev
import fetch_v76_history as histfetch


def main(out_dir="data"):
    chunks=int(os.getenv("V76_CHUNKS","6"))
    pause=int(os.getenv("V76_QUOTA_PAUSE","62"))
    hist,daily,fetchlog=histfetch.fetch_history(chunks,pause)
    results={s:ev.research_pair(s,hist[s],daily[s]) for s in base.PAIRS}
    stats,retained,fallback=ev.global_archetypes(results)
    methods,counts=ev.lock_methods(results,retained,fallback)
    pairs={s:{"bars":x["bars"],"from":x["from"],"to":x["to"],"signalCount":x["signalCount"],"selected":methods[s],"top5Dev":x["top5Dev"]} for s,x in results.items()}
    generated=base.iso(base.utcnow());protocol=ev.protocol_summary()
    research={
        "version":"V76-ENTRY-RESEARCH-R2","generatedAt":generated,"scope":"FOREX_28",
        "history":{"source":"Twelve Data exact Physical Currency","baseInterval":"5min","chunks":chunks,"pointsPerSymbolPerChunk":histfetch.M5_OUTPUTSIZE,"batchGroupSize":histfetch.GROUP_SIZE,"batchPageProduct":histfetch.GROUP_SIZE*histfetch.M5_OUTPUTSIZE,"resampledLocally":["15min","1h","4h"],"dailyFetchedSeparately":True,"rawHistoryCommitted":False,"fetchLog":fetchlog},
        "protocol":protocol,"setups":base.SETUP_DEFS,"archetypeValidation":stats,
        "retainedArchetypes":retained,"fallbackResearchArchetypes":fallback if not retained else [],
        "pairResults":pairs,
        "limitations":[
            "Historical broker bid/ask/spread unavailable; fixed 0.05R round-trip cost used.",
            "Historical high-impact macro-event timestamps unavailable from canonical feed; before/after-news performance is not claimed.",
            "OOS is a one-time promotion check only. Failed OOS methods are not retuned in this research version.",
            "Research evidence is not a future/live win-rate guarantee."
        ]
    }
    methodfile={
        "version":"V76-ENTRY-METHODS-R2","generatedAt":generated,"selectionFrozen":True,
        "selectionData":"DEV_PLUS_VALIDATION_ONLY","oosUsedFor":"PROMOTION_GATE_ONLY",
        "retainedArchetypes":retained,"fallbackResearchArchetypes":fallback if not retained else [],
        "setupDefinitions":base.SETUP_DEFS,"protocol":protocol,
        "promotionCriteria":{"devMinN":ev.DEV_MIN_N,"devExpectancyR":">0","devPF":">=1.10","validationMinN":ev.VAL_MIN_N,"validationExpectancyR":">0","validationPF":">=1.05","oosMinN":ev.OOS_MIN_N,"oosExpectancyR":">0.05","oosPF":">=1.15","oosMaxDrawdownR":"<=10","oosMaxLosingStreak":"<=10"},
        "costModelR":base.COST_R,"methods":methods,"counts":counts
    }
    os.makedirs(out_dir,exist_ok=True)
    for name,obj in (("v76_entry_research.json",research),("v76_entry_methods.json",methodfile)):
        with open(os.path.join(out_dir,name),"w",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,indent=2)
    print(json.dumps({"version":research["version"],"evaluator":ev.VERSION,"retained":retained,"fallback":fallback if not retained else [],"counts":counts,"barsMin":min(len(hist[s]) for s in base.PAIRS),"barsMax":max(len(hist[s]) for s in base.PAIRS),"chunks":chunks,"pointsPerChunk":histfetch.M5_OUTPUTSIZE},ensure_ascii=False))
    return 0

if __name__=="__main__":raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else "data"))
