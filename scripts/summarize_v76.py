#!/usr/bin/env python3
"""Build compact human/LLM-readable outputs from locked V76 methods."""
import json, os, sys

FIELDS=("n","wr","expectancyR","profitFactor","avgWinR","avgLossR","maxLosingStreak","maxDrawdownR","mfeR","maeR","hit1R","hit2R","timeoutRate")

def compact(m): return {k:m.get(k) for k in FIELDS}
def fmt(x): return "-" if x is None else str(x)

def main(src="data/v76_entry_methods.json",dst="data/v76_entry_summary.json",table="data/v76_pair_table.md"):
    d=json.load(open(src,encoding="utf-8"));methods=d.get("methods") or {};rows=[]
    for symbol in sorted(methods):
        m=methods[symbol]
        rows.append({"symbol":symbol,"status":m.get("status"),"liveEligible":m.get("liveEligible"),"archetype":m.get("archetype"),"entryMode":m.get("entryMode"),"stopMode":m.get("stopMode"),"rr":m.get("rr"),"dev":compact(m.get("dev") or {}),"validation":compact(m.get("validation") or {}),"oos":compact(m.get("oos") or {})})
    setups=set((d.get("setupDefinitions") or {}).keys());retained=d.get("retainedArchetypes") or [];fallback=d.get("fallbackResearchArchetypes") or []
    out={"version":"V76-ENTRY-SUMMARY-R2","methodsVersion":d.get("version"),"generatedAt":d.get("generatedAt"),"selectionFrozen":d.get("selectionFrozen"),"retainedArchetypes":retained,"fallbackResearchArchetypes":fallback,"notRetainedArchetypes":sorted(setups-set(retained)),"fullyRejectedArchetypes":sorted(setups-set(retained)-set(fallback)),"counts":d.get("counts"),"promotionCriteria":d.get("promotionCriteria"),"promotedSymbols":[r["symbol"] for r in rows if r["liveEligible"]],"researchOnlySymbols":[r["symbol"] for r in rows if not r["liveEligible"]],"pairs":rows}
    os.makedirs(os.path.dirname(dst) or ".",exist_ok=True)
    with open(dst,"w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    lines=["# V76 R2 — 28-pair compact readout","",f"Methods: `{d.get('version')}` | retained: {', '.join(retained) if retained else 'NONE'} | promoted: {len(out['promotedSymbols'])}/28","","| Pair | Status | Archetype | Entry | Stop | RR | DEV n/Exp/PF | VAL n/Exp/PF | OOS n/WR/Exp/PF/DD/LS/TO |","|---|---|---|---|---|---:|---|---|---|"]
    for x in rows:
        a,b,c=x['dev'],x['validation'],x['oos']
        lines.append(f"| {x['symbol']} | {x['status']} | {x['archetype']} | {x['entryMode']} | {x['stopMode']} | {x['rr']} | {fmt(a['n'])}/{fmt(a['expectancyR'])}/{fmt(a['profitFactor'])} | {fmt(b['n'])}/{fmt(b['expectancyR'])}/{fmt(b['profitFactor'])} | {fmt(c['n'])}/{fmt(c['wr'])}%/{fmt(c['expectancyR'])}/{fmt(c['profitFactor'])}/{fmt(c['maxDrawdownR'])}/{fmt(c['maxLosingStreak'])}/{fmt(c['timeoutRate'])}% |")
    lines += ["", "Legend OOS: n / WR / expectancy R / PF / max DD R / max losing streak / timeout %."]
    with open(table,"w",encoding="utf-8") as f:f.write("\n".join(lines)+"\n")
    print(json.dumps({"methodsVersion":d.get("version"),"retained":retained,"fallback":fallback,"promoted":out["promotedSymbols"],"counts":d.get("counts")},ensure_ascii=False))
if __name__=="__main__":main(*(sys.argv[1:4]))
