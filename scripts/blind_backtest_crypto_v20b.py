#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v20 as v20

# NO RULE CHANGES after Jul24/Jul22 results. Same V20 chosen policy is frozen here.
POLICY='fade_alt'; LOW=.05; HIGH=.80
CUTOFFS=[('BLIND_JUL20','2026-07-20T12:00:00Z'),('BLIND_JUL18','2026-07-18T12:00:00Z')]

def run(label,cutoff):
    rows,b=v20.load(cutoff);details=[]
    for r in rows:
        side,fade,rr,en,sl,tp,z=v20.trade_result(r,b,POLICY,LOW,HIGH)
        details.append({'symbol':r['sym']+'USDT','cutoff':cutoff,'blind':True,'decision':side,'fadeBreadth':fade,'score':round(r['baseScore'],3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(b,3),'model':r['model'],'features':r['f'],'outcome':{'result':z}})
    resolved=[x for x in details if x['outcome']['result'] in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    s={'label':label,'cutoff':cutoff,'isTrueBlind':True,'marketTrades':len(details),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(details)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(b,3),'breadthFades':sum(x['fadeBreadth'] for x in details)}
    return {'summary':s,'tests':details}

def main():
    samples={n:run(n,c) for n,c in CUTOFFS}
    with open('data/blind_backtest_v20b.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'Locked V20 out-of-sample extension. Same fade_alt breadth thresholds .05/.80, V17 short-horizon momentum/structure direction, 48xM15 structural SL + .75 profile ATR floor, RR1.5/1.7/1.9 alignment. No parameters changed after prior V20 fresh results.','samples':samples},f,indent=2)
    print(json.dumps({k:v['summary'] for k,v in samples.items()},indent=2))
if __name__=='__main__':main()
