#!/usr/bin/env python3
"""Build a compact human/LLM-readable summary from locked V76 methods."""
import json, os, sys

FIELDS=("n","wr","expectancyR","profitFactor","avgWinR","avgLossR","maxLosingStreak","maxDrawdownR","mfeR","maeR","hit1R","hit2R","timeoutRate")

def compact(m): return {k:m.get(k) for k in FIELDS}

def main(src="data/v76_entry_methods.json",dst="data/v76_entry_summary.json"):
    d=json.load(open(src,encoding="utf-8")); methods=d.get("methods") or {}; rows=[]
    for symbol in sorted(methods):
        m=methods[symbol]
        rows.append({"symbol":symbol,"status":m.get("status"),"liveEligible":m.get("liveEligible"),"archetype":m.get("archetype"),"entryMode":m.get("entryMode"),"stopMode":m.get("stopMode"),"rr":m.get("rr"),"dev":compact(m.get("dev") or {}),"validation":compact(m.get("validation") or {}),"oos":compact(m.get("oos") or {})})
    setups=set((d.get("setupDefinitions") or {}).keys()); retained=d.get("retainedArchetypes") or []
    out={"version":"V76-ENTRY-SUMMARY-R1","methodsVersion":d.get("version"),"generatedAt":d.get("generatedAt"),"selectionFrozen":d.get("selectionFrozen"),"retainedArchetypes":retained,"eliminatedArchetypes":sorted(setups-set(retained)),"counts":d.get("counts"),"promotionCriteria":d.get("promotionCriteria"),"promotedSymbols":[r["symbol"] for r in rows if r["liveEligible"]],"researchOnlySymbols":[r["symbol"] for r in rows if not r["liveEligible"]],"pairs":rows}
    os.makedirs(os.path.dirname(dst) or ".",exist_ok=True)
    with open(dst,"w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({"methodsVersion":d.get("version"),"retained":retained,"promoted":out["promotedSymbols"],"counts":d.get("counts")},ensure_ascii=False))
if __name__=="__main__":main(*(sys.argv[1:3]))
