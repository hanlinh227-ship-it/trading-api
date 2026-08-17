#!/usr/bin/env python3
import json, os, statistics, itertools
from scripts.offline_crypto_v29_symbol_conditional import prep, sm, stats_map, score_row, aligned
from scripts.offline_crossmarket_rolling_blind_v4 import extract_crypto

PARAMS=[(th,k,a) for th,k,a in itertools.product((.54,.58,.62,.66,.70,.74),(3,5,8,12),(False,True))]

def apply_day(day,maps,p):
    th,k,a=p
    z=[(score_row(r,maps),r) for r in day if (not a or aligned(r))]
    z=[x for x in z if x[0]>=th]; z.sort(key=lambda x:x[0],reverse=True)
    return [r for _,r in z[:k]]

def inner_score(train,p):
    dates=sorted(set(r['date'] for r in train));picked=[]
    # expanding inner CV: at least 3 earlier dates before scoring a held inner date
    for i,d in enumerate(dates):
        if i<3:continue
        tr=[r for r in train if r['date']<d]
        day=[r for r in train if r['date']==d]
        maps=stats_map(tr);picked+=apply_day(day,maps,p)
    s=sm(picked)
    if s.get('n',0)<12 or s.get('dates',0)<2:return None
    return s

def choose(train):
    best=None
    for p in PARAMS:
        s=inner_score(train,p)
        if not s:continue
        # no hindsight target: expectancy and WR, with sample floor, all from inner held dates
        score=(1 if s['wr']>=70 else 0,s['meanR'],s['wr'],min(s['n'],80))
        if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=prep(extract_crypto());dates=sorted(set(r['date'] for r in rows));allsel=[];detail={}
    for i,d in enumerate(dates):
        day=[r for r in rows if r['date']==d]
        if i<6:
            detail[d]={'warmup':True,'selected':{'n':0}};continue
        train=[r for r in rows if r['date']<d]
        best=choose(train)
        maps=stats_map(train);sel=apply_day(day,maps,best[1]) if best else []
        allsel+=sel
        detail[d]={'warmup':False,'rule':best[1] if best else None,'innerPerformance':best[2] if best else None,'selected':sm(sel)}
    out={'version':'CRYPTO V30 NESTED SYMBOL WALKFORWARD','providerCreditsUsed':0,
         'method':'Crypto-only chronological nested walk-forward. Per-symbol+regime Bayesian profile is rebuilt only from earlier dates. Threshold/topK is chosen only by expanding inner held-date tests inside the earlier training set, then applied once to the next date.',
         'dates':dates,'walkForward':sm(allsel),'byDate':detail,'targetMet':False,'hourlyManagement':'NOT_REPLAYABLE_FROM_COMMITTED_OLD_CRYPTO_DATA'}
    s=out['walkForward'];out['targetMet']=bool(s.get('n',0)>=20 and (s.get('wr') or 0)>=80 and 1.0<=(s.get('avgRR') or 0)<=1.5 and s.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v30_nested_symbol.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({'version':out['version'],'providerCreditsUsed':0,'walkForward':out['walkForward'],'byDate':out['byDate'],'targetMet':out['targetMet']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
