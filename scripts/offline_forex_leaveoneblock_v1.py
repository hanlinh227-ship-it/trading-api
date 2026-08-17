#!/usr/bin/env python3
import json, statistics

SRC='data/offline_forex_meta_v1.json'
OUT='data/offline_forex_leaveoneblock_v1.json'

def mean(xs): return statistics.mean(xs) if xs else None

def main():
    d=json.load(open(SRC,encoding='utf-8'))
    details=d.get('pairDetail',{})
    all_obs=[]; qualified=[]; folds={}
    # Each run/source is an independent stored blind block. For every held-out source,
    # pair eligibility is learned only from the other sources. No held-out outcome enters the gate.
    sources=sorted({r['source'] for p in details.values() for r in p.get('runs',[])})
    for hold in sources:
        fold_all=[]; fold_q=[]
        for sym,p in details.items():
            runs=p.get('runs',[])
            test=[r for r in runs if r.get('source')==hold]
            train=[r for r in runs if r.get('source')!=hold]
            if not test or len(train)<2: continue
            exps=[r['market'].get('expectancyR') for r in train if isinstance(r.get('market',{}).get('expectancyR'),(int,float))]
            wrs=[r['market'].get('winRateResolved') for r in train if isinstance(r.get('market',{}).get('winRateResolved'),(int,float))]
            if len(exps)<2: continue
            pos=sum(x>0 for x in exps)/len(exps)
            med=statistics.median(exps); mw=mean(wrs) or 0
            # Conservative pair reliability gate. This is frozen before looking at held-out run.
            ok=(med>0.05 and pos>=0.5 and mw>=40) or (med>-0.02 and pos>=2/3 and mw>=45)
            for r in test:
                m=r.get('market',{}); e=m.get('expectancyR'); w=m.get('winRateResolved')
                if not isinstance(e,(int,float)):continue
                o={'symbol':sym,'expectancyR':e,'winRate':w,'qualified':ok}
                all_obs.append(o);fold_all.append(o)
                if ok: qualified.append(o);fold_q.append(o)
        def summ(arr):
            es=[x['expectancyR'] for x in arr]; ws=[x['winRate'] for x in arr if isinstance(x['winRate'],(int,float))]
            return {'pairBlockObs':len(arr),'meanExpectancyR':round(mean(es),3) if es else None,
                    'medianExpectancyR':round(statistics.median(es),3) if es else None,
                    'meanResolvedWR':round(mean(ws),2) if ws else None,'positiveExpectancyRate':round(sum(x>0 for x in es)/len(es),3) if es else None}
        folds[hold]={'all':summ(fold_all),'qualified':summ(fold_q)}
    def summ(arr):
        es=[x['expectancyR'] for x in arr];ws=[x['winRate'] for x in arr if isinstance(x['winRate'],(int,float))]
        return {'pairBlockObs':len(arr),'meanExpectancyR':round(mean(es),3) if es else None,
                'medianExpectancyR':round(statistics.median(es),3) if es else None,
                'meanResolvedWR':round(mean(ws),2) if ws else None,'positiveExpectancyRate':round(sum(x>0 for x in es)/len(es),3) if es else None}
    out={'version':'FOREX LEAVE-ONE-BLOCK V1','providerCreditsUsed':0,'integrity':{'heldoutSourceExcludedFromGate':True,'usesOnlyCommittedBlindPairTables':True},
         'sources':sources,'all':summ(all_obs),'qualified':summ(qualified),'folds':folds,
         'conclusion':'Pair reputation is useful only if held-out expectancy improves. If not, current-state bias/regime must dominate live qualification.'}
    json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
