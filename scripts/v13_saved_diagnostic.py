#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone

SRC='data/blind_backtest_v12.json'
OUT='data/v13_saved_diagnostic.json'

def score_bucket(x):
    a=abs(x)
    return '0-1' if a<1 else '1-3' if a<3 else '3-5' if a<5 else '5-7' if a<7 else '7+'
def pos_bucket(x):
    return '0-.2' if x<=.2 else '.2-.4' if x<=.4 else '.4-.6' if x<=.6 else '.6-.8' if x<=.8 else '.8-1'
def chase_bucket(x):
    a=abs(x)
    return '<.5' if a<.5 else '.5-1.2' if a<1.2 else '1.2+'
def group(rows, keyfn):
    d=defaultdict(lambda:{'n':0,'tp':0,'sl':0,'unresolved':0,'rrSumResolved':0.0,'rSum':0.0})
    for r in rows:
        k=str(keyfn(r)); z=d[k];z['n']+=1
        out=r.get('outcome',{}).get('result');rr=r.get('plannedRR',0)
        if out=='TP':z['tp']+=1;z['rrSumResolved']+=rr;z['rSum']+=rr
        elif out=='SL':z['sl']+=1;z['rrSumResolved']+=rr;z['rSum']-=1
        else:z['unresolved']+=1
    for z in d.values():
        n=z['tp']+z['sl'];z['winRate']=round(100*z['tp']/n,2) if n else None;z['avgRR']=round(z['rrSumResolved']/n,3) if n else None;z['expectancyR']=round(z['rSum']/n,3) if n else None
        del z['rrSumResolved'];del z['rSum']
    return dict(d)

def main():
    p=json.load(open(SRC));samples={}
    for label,s in p['samples'].items():
        rows=[r for r in s['tests'] if r.get('decision') in ('BUY','SELL')]
        samples[label]={
            'summary':s['summary'],
            'byRegime':group(rows,lambda r:r['model']['regime']),
            'byProfile':group(rows,lambda r:r['model']['profile']),
            'bySide':group(rows,lambda r:r['decision']),
            'byScoreBucket':group(rows,lambda r:score_bucket(r['score'])),
            'byRangePosition':group(rows,lambda r:pos_bucket(r['model']['rangePositionH1'])),
            'byChase':group(rows,lambda r:chase_bucket(r['model']['chaseAdjustment'])),
            'byRegimeSide':group(rows,lambda r:r['model']['regime']+'_'+r['decision']),
            'byProfileRegime':group(rows,lambda r:r['model']['profile']+'_'+r['model']['regime']),
            'bySweep15':group(rows,lambda r:r['model']['m15Sweep']),
        }
    json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'source':SRC,'samples':samples},open(OUT,'w'),indent=2)
    print(json.dumps(samples,indent=2))
if __name__=='__main__':main()
