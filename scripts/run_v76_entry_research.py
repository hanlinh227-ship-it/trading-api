#!/usr/bin/env python3
"""Quota-safe canonical runner for V76 Forex research."""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import research_v76_entry_forex as r

OUTPUTSIZE = 3500  # 28 symbols * 3500 = 98,000 <= Twelve Data 100,000 batch-page cap.


def main(out_dir="data"):
    chunks=int(os.getenv("V76_CHUNKS","3"));pause=int(os.getenv("V76_QUOTA_PAUSE","62"))
    hist,daily,fetchlog=r.fetch_history(chunks,OUTPUTSIZE,pause)
    results={s:r.research_pair(s,hist[s],daily[s]) for s in r.PAIRS}
    stats,retained=r.global_archetypes(results);methods,counts=r.lock_methods(results,retained)
    pairs={s:{"bars":x["bars"],"from":x["from"],"to":x["to"],"signalCount":x["signalCount"],"selected":methods[s],"top5Dev":x["top5Dev"]} for s,x in results.items()}
    research={"version":r.VERSION,"generatedAt":r.iso(r.utcnow()),"scope":"FOREX_28","history":{"source":"Twelve Data exact Physical Currency","baseInterval":"5min","chunks":chunks,"maxPointsPerChunk":OUTPUTSIZE,"batchPageProduct":28*OUTPUTSIZE,"resampledLocally":["15min","1h","4h"],"dailyFetchedSeparately":True,"rawHistoryCommitted":False,"fetchLog":fetchlog},"protocol":{"split":"chronological 60/20/20","selection":"DEV ranking + VALIDATION gate; OOS promotion check only","costModelR":r.COST_R,"maxHoldM5Bars":r.MAX_HOLD_BARS,"sameBarTpSl":"SL","newsHistoricalFilter":"NOT_TESTED_NO_CANONICAL_TIMESTAMPED_EVENT_FEED","liveNewsGateStillRequired":True},"setups":r.SETUP_DEFS,"archetypeValidation":stats,"retainedArchetypes":retained,"pairResults":pairs,"limitations":["Historical broker bid/ask/spread unavailable; fixed 0.05R round-trip cost used.","Historical high-impact macro-event timestamps unavailable from canonical feed; before/after-news performance is not claimed.","OOS is only a one-time promotion gate; failed OOS methods are not retuned in this run."]}
    methodfile={"version":"V76-ENTRY-METHODS-R1","generatedAt":research["generatedAt"],"selectionFrozen":True,"selectionData":"DEV_PLUS_VALIDATION_ONLY","oosUsedFor":"PROMOTION_GATE_ONLY","retainedArchetypes":retained,"setupDefinitions":r.SETUP_DEFS,"promotionCriteria":{"validationMinN":6,"validationExpectancyR":">0","validationPF":">1.0","oosMinN":8,"oosExpectancyR":">0.05","oosPF":">=1.10","oosMaxDrawdownR":"<=8"},"costModelR":r.COST_R,"methods":methods,"counts":counts}
    os.makedirs(out_dir,exist_ok=True)
    for name,obj in (("v76_entry_research.json",research),("v76_entry_methods.json",methodfile)):
        with open(os.path.join(out_dir,name),"w",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,separators=(",",":"))
    print(json.dumps({"version":r.VERSION,"retained":retained,"counts":counts,"barsMin":min(len(hist[s]) for s in r.PAIRS),"barsMax":max(len(hist[s]) for s in r.PAIRS),"outputsize":OUTPUTSIZE},ensure_ascii=False))
    return 0

if __name__=="__main__":raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else "data"))
