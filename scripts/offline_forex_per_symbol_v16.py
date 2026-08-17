#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
import scripts.offline_forex_precision_evolver_v15 as base

OUT='data/offline_forex_per_symbol_v16.json'
MIN_RESOLVED=5
TARGET_WR=80.0


def cfgs():
    out=[]
    for mode in ('MARKET','LIMIT'):
        offs=(0.0,) if mode=='MARKET' else (0.20,0.35,0.50,0.70)
        exps=(1,) if mode=='MARKET' else (2,4)
        for rr in (1.0,2.0):
            holds=(12,18,24) if rr==1.0 else (18,24,36)
            for rf in (0.65,0.85,1.05):
                for sw in (6,12):
                    for hold in holds:
                        for off in offs:
                            for exp in exps:
                                for ca,cr in ((0,0.0),(2,-0.45),(4,-0.30)):
                                    out.append((mode,rr,rf,sw,hold,off,exp,ca,cr))
    # Deterministic compact neighborhood first; full list is still available if needed.
    return out

MODEL_SPECS=[
    ('ET',4,8),('ET',7,12),('ET',9,20),
    ('HGB',3,12),('HGB',5,20)
]
THRESHOLDS=(0.58,0.62,0.66,0.70,0.74,0.78,0.82,0.86,0.90)
MARGINS=(0.02,0.06,0.10,0.14,0.18)
HOURS=(0,4,8,12,16,20)
DIRS=('BOTH','BUY','SELL')


def mdl(train,kind,depth,leaf,seed):
    q=[x for x in train if x['result'] in ('TP','SL')]
    if len(q)<80:return None
    X=np.asarray([x['x'] for x in q],float);y=np.asarray([1 if x['result']=='TP' else 0 for x in q],int)
    if len(set(y))<2:return None
    if kind=='ET':
        m=ExtraTreesClassifier(n_estimators=180,max_depth=depth,min_samples_leaf=leaf,max_features=.8,class_weight='balanced_subsample',n_jobs=-1,random_state=seed)
    else:
        m=HistGradientBoostingClassifier(max_iter=140,max_leaf_nodes=2**depth-1,min_samples_leaf=leaf,learning_rate=.055,l2_regularization=3.0,random_state=seed)
    m.fit(X,y);return m


def scored(events,train_end,a,b,spec,seed):
    tr=[x for x in events if x['day']<=train_end]
    te=[x for x in events if a<=x['day']<=b]
    m=mdl(tr,*spec,seed)
    if m is None or not te:return []
    pr=m.predict_proba(np.asarray([x['x'] for x in te],float))[:,1]
    g=defaultdict(list)
    for e,p in zip(te,pr):g[e['time']].append((float(p),e))
    rows=[]
    for t,z in sorted(g.items()):
        z=sorted(z,key=lambda x:x[0],reverse=True)
        best=z[0];other=z[1][0] if len(z)>1 else 0.0
        q=dict(best[1]);q['prob']=best[0];q['edge']=best[0]-other;rows.append(q)
    return rows


def pick(rows,th,margin,hour,direction):
    out=[];used_days=set()
    for x in rows:
        if x['time'].hour!=hour or x['prob']<th or x['edge']<margin:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        # One independent setup per symbol/day. This is online: first qualifying fixed-hour event only.
        if x['day'] in used_days:continue
        used_days.add(x['day']);out.append(x)
    return out


def sm(z):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cuts=[x for x in z if x['result']=='CUT'];den=tp+sl
    return {'n':len(z),'resolved':den,'tp':tp,'sl':sl,'cut':len(cuts),'wr':round(100*tp/den,2) if den else 0.0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9.0,'cutRate':round(100*len(cuts)/len(z),2) if z else 0.0}


def rank_stat(s):
    enough=s['resolved']>=MIN_RESOLVED
    hit=enough and s['wr']>=TARGET_WR and s['meanR']>0 and s['cutRate']<=50
    return (int(hit), min(s['wr'],100)-max(0,MIN_RESOLVED-s['resolved'])*12, s['meanR'], -s['cutRate'], s['resolved'])


def tune(scored_rows):
    best=None;bp=None
    for th in THRESHOLDS:
      for mg in MARGINS:
       for hr in HOURS:
        for dr in DIRS:
            z=pick(scored_rows,th,mg,hr,dr);s=sm(z);r=rank_stat(s)
            if best is None or r>best:
                best=r;bp={'threshold':th,'margin':mg,'hourUTC':hr,'direction':dr,'stats':s}
    return bp


def evaluate_with_params(rows,p):
    return sm(pick(rows,p['threshold'],p['margin'],p['hourUTC'],p['direction']))


def main():
    doc=json.load(open(base.SNAP,encoding='utf-8'))
    if doc.get('coverageCount')!=28:raise RuntimeError('Forex snapshot coverage !=28')
    data={p:base.enrich(doc['data'][p]) for p in base.PAIRS};maps,times=base.make_maps(data)
    # Build event cache per execution geometry once, then split by pair.
    configs=cfgs()
    # Prioritize neighborhoods around promoted V15 plus RR2 variants to control runtime.
    def pref(c):
        mode,rr,rf,sw,hold,off,exp,ca,cr=c
        score=0
        score+=0 if mode=='LIMIT' else 6
        score+=abs(rf-.65)*4+abs(sw-6)*.2+abs(off-.35)*3+abs(exp-4)*.2
        score+=0 if rr==1.0 else 1.5
        score+=0 if ca in (0,2) else 1
        return score
    configs=sorted(configs,key=pref)[:72]
    cache=[]
    for ci,cfg in enumerate(configs):
        ev,_=base.build_events(data,maps,times,cfg)
        by=defaultdict(list)
        for e in ev:by[e['symbol']].append(e)
        cache.append((cfg,by))
        if (ci+1)%12==0:print('EVENT_CACHE',ci+1,flush=True)

    results={};stageA=0;stageB=0
    for si,sym in enumerate(base.PAIRS):
        bestA=None;payloadA=None
        # A: choose on May using Feb-Apr training, then untouched June test.
        for ci,(cfg,by) in enumerate(cache):
            ev=by.get(sym,[])
            if len(ev)<100:continue
            for mi,spec in enumerate(MODEL_SPECS):
                may=scored(ev,'2026-04-30','2026-05-01','2026-05-31',spec,160000+si*100+ci*7+mi)
                if not may:continue
                p=tune(may);r=rank_stat(p['stats'])
                if bestA is None or r>bestA:
                    bestA=r;payloadA={'cfg':cfg,'model':spec,'selector':p}
        if payloadA:
            cfg=payloadA['cfg'];spec=payloadA['model'];ev=dict(cache[configs.index(cfg)][1]).get(sym,[])
            june=scored(ev,'2026-05-31','2026-06-01','2026-06-30',spec,260000+si)
            js=evaluate_with_params(june,payloadA['selector'])
        else:js=sm([])
        passA=rank_stat(js)[0]==1
        if passA:
            stageA+=1
            results[sym]={'status':'PASS','stage':'JUNE_FINAL','execution':payloadA['cfg'],'model':payloadA['model'],'selector':{k:v for k,v in payloadA['selector'].items() if k!='stats'},'developmentMay':payloadA['selector']['stats'],'finalMonth':js}
            print('PASS_A',sym,js,flush=True);continue

        # B: June becomes development for this failed pair; July remains untouched for this pair.
        bestB=None;payloadB=None
        for ci,(cfg,by) in enumerate(cache):
            ev=by.get(sym,[])
            if len(ev)<100:continue
            for mi,spec in enumerate(MODEL_SPECS):
                june_rows=scored(ev,'2026-05-31','2026-06-01','2026-06-30',spec,360000+si*100+ci*7+mi)
                if not june_rows:continue
                p=tune(june_rows);r=rank_stat(p['stats'])
                if bestB is None or r>bestB:
                    bestB=r;payloadB={'cfg':cfg,'model':spec,'selector':p}
        if payloadB:
            cfg=payloadB['cfg'];spec=payloadB['model'];ev=dict(cache[configs.index(cfg)][1]).get(sym,[])
            july=scored(ev,'2026-06-30','2026-07-01','2026-07-31',spec,460000+si)
            fs=evaluate_with_params(july,payloadB['selector'])
        else:fs=sm([])
        passB=rank_stat(fs)[0]==1
        if passB:stageB+=1
        results[sym]={'status':'PASS' if passB else 'FAIL','stage':'JULY_FINAL','execution':payloadB['cfg'] if payloadB else None,'model':payloadB['model'] if payloadB else None,'selector':({k:v for k,v in payloadB['selector'].items() if k!='stats'} if payloadB else None),'developmentJune':(payloadB['selector']['stats'] if payloadB else None),'finalMonth':fs,'previousJuneTest':js}
        print('PASS_B' if passB else 'FAIL',sym,fs,flush=True)

    passed=[s for s,r in results.items() if r['status']=='PASS'];failed=[s for s,r in results.items() if r['status']!='PASS']
    out={'version':'FOREX_PER_SYMBOL_V16','definition':{'independentPerSymbol':True,'crossSymbolTopK':False,'rrAllowed':[1.0,2.0],'minResolvedPerFinalMonth':MIN_RESOLVED,'targetWrPct':TARGET_WR,'noTradeCountsAsWin':False},'universeCount':28,'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'stageAPass':stageA,'stageBPass':stageB,'allPassed':len(failed)==0,'results':results}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2)
    print('SUMMARY',json.dumps({k:out[k] for k in ('version','passCount','failCount','passed','failed','allPassed')},indent=2),flush=True)

if __name__=='__main__':main()
