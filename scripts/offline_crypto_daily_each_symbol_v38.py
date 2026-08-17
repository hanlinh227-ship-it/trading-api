#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
import scripts.offline_crypto_precision_evolver_v36 as base
import scripts.offline_crypto_precision_evolver_v36b as fixed

base.regime_at=fixed.fixed_regime_at
SNAP_MAIN='data/provider_snapshots/crypto_4h_feb_jul_2026.json'
SNAP_BUF='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json'
OUT='data/offline_crypto_daily_each_symbol_v38.json'
TARGET=80.0
STAGES=[
 ('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),
 ('JUNE','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),
 ('JULY','2026-06-01','2026-06-30','2026-07-01','2026-07-31'),
]
HOURS=(0,4,8,12,16,20)
MODEL_SPECS=(('LR',0,0),('ET',5,8),('ET',8,15))


def merge_docs():
    a=json.load(open(SNAP_MAIN,encoding='utf-8'));b=json.load(open(SNAP_BUF,encoding='utf-8'))
    if a.get('coverageCount')!=61 or b.get('coverageCount')!=61:raise RuntimeError('Need 61/61 Crypto coverage')
    out={}
    for s in base.SYMBOLS:
        d={x[0]:x for x in a['data'][s]}
        for x in b['data'][s]:d[x[0]]=x
        out[s]=[d[k] for k in sorted(d)]
    return out


def exec_cfgs():
    out=[]
    for rr in (1.0,2.0):
        holds=(4,6) if rr==1.0 else (6,9)
        for rf in (.65,.85,1.05):
            for sw in (3,5,8):
                for hold in holds:
                    out.append(('MARKET',rr,rf,sw,hold,0.0,1,0,0.0))
    return out


def train(rows,spec,seed):
    q=[x for x in rows if x['result'] in ('TP','SL')]
    if len(q)<65:return None
    X=np.asarray([x['x'] for x in q],float);y=np.asarray([1 if x['result']=='TP' else 0 for x in q],int)
    if len(set(y))<2:return None
    if spec[0]=='LR':m=LogisticRegression(C=.30,max_iter=800,class_weight='balanced',random_state=seed)
    else:m=ExtraTreesClassifier(n_estimators=90,max_depth=spec[1],min_samples_leaf=spec[2],max_features=.85,class_weight='balanced_subsample',n_jobs=-1,random_state=seed)
    m.fit(X,y);return m


def score_month(events,train_end,a,b,spec,seed):
    tr=[x for x in events if x['day']<=train_end];te=[x for x in events if a<=x['day']<=b]
    m=train(tr,spec,seed)
    if m is None or not te:return {}
    pr=m.predict_proba(np.asarray([x['x'] for x in te],float))[:,1]
    g=defaultdict(list)
    for e,p in zip(te,pr):g[(e['day'],e['time'])].append((float(p),e))
    byday=defaultdict(list)
    for (d,t),z in g.items():
        z=sorted(z,key=lambda x:x[0],reverse=True);best=z[0];other=z[1][0] if len(z)>1 else 0
        q=dict(best[1]);q['prob']=best[0];q['edge']=best[0]-other;byday[d].append(q)
    for d in byday:byday[d]=sorted(byday[d],key=lambda x:x['time'])
    return byday


def policies():
    out=[]
    for family in ('FIXED','FIRST'):
        for fb in HOURS:
            if family=='FIXED':out.append((family,fb,0.0,0.0))
            else:
                for th in (.54,.58,.62,.66,.70,.74,.78,.82):
                    for mg in (.00,.04,.08,.12,.16):out.append((family,fb,th,mg))
    return out


def choose(rows,pol):
    family,fb,th,mg=pol
    if not rows:return None
    eligible=[x for x in rows if x['time'].hour<=fb]
    if not eligible:eligible=rows
    if family=='FIRST':
        for x in eligible:
            if x['prob']>=th and x['edge']>=mg:return x
    return eligible[-1]


def expected_days(a,b):
    x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(b).date();n=0
    while x<=y:n+=1;x+=timedelta(days=1)
    return n


def sm(byday,pol,a,b):
    z=[]
    for d in sorted(byday):
        q=choose(byday[d],pol)
        if q:z.append(q)
    exp=expected_days(a,b);wins=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=len(z)-wins-sl;missing=max(0,exp-len(z))
    return {'expectedDays':exp,'tradedDays':len(z),'missingDays':missing,'tpDays':wins,'slDays':sl,'timeoutCutDays':cut,'dailyWinRateAllDays':round(100*wins/exp,2) if exp else 0,'dailyWinRateTraded':round(100*wins/len(z),2) if z else 0,'meanRTraded':round(statistics.mean(x['r'] for x in z),3) if z else -9}


def tune(byday,a,b):
    best=None;bp=None
    for p in policies():
        s=sm(byday,p,a,b);rank=(s['dailyWinRateAllDays'],s['meanRTraded'],-s['missingDays'])
        if best is None or rank>best:best=rank;bp={'policy':p,'stats':s}
    return bp


def passmonth(s):
    return s['missingDays']==0 and s['dailyWinRateAllDays']>=TARGET and s['meanRTraded']>0


def main():
    raw=merge_docs();data={s:base.enrich(raw[s]) for s in base.SYMBOLS};mp=base.maps(data)
    cache=[];cfgs=exec_cfgs()
    for ci,cfg in enumerate(cfgs):
        ev,_,_=base.build_events(data,mp,cfg);by=defaultdict(list)
        for e in ev:by[e['symbol']].append(e)
        cache.append((cfg,by));print('CACHE',ci+1,'/',len(cfgs),flush=True)

    results={}
    for si,sym in enumerate(base.SYMBOLS):
        passed=None;history=[]
        for sti,(name,dev_a,dev_b,fin_a,fin_b) in enumerate(STAGES):
            model_train_end=(datetime.fromisoformat(dev_a).date()-timedelta(days=1)).isoformat()
            best=None;choice=None
            for ci,(cfg,by) in enumerate(cache):
                ev=by.get(sym,[])
                if len(ev)<80:continue
                for mi,spec in enumerate(MODEL_SPECS):
                    dev=score_month(ev,model_train_end,dev_a,dev_b,spec,380000+si*1000+sti*100+ci*5+mi)
                    if not dev:continue
                    t=tune(dev,dev_a,dev_b);rank=(t['stats']['dailyWinRateAllDays'],t['stats']['meanRTraded'],-t['stats']['missingDays'])
                    if best is None or rank>best:best=rank;choice={'cfg':cfg,'model':spec,'policy':t['policy'],'development':t['stats']}
            if not choice:
                history.append({'stage':name,'status':'NO_MODEL'});continue
            ev=dict(cache[cfgs.index(choice['cfg'])][1]).get(sym,[])
            final=score_month(ev,dev_b,fin_a,fin_b,choice['model'],480000+si*100+sti)
            fs=sm(final,choice['policy'],fin_a,fin_b);ok=passmonth(fs)
            rec={'stage':name,'execution':choice['cfg'],'model':choice['model'],'policy':choice['policy'],'development':choice['development'],'final':fs,'pass':ok}
            history.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
            if ok:passed=rec;break
        results[sym]={'status':'PASS' if passed else 'FAIL','passedStage':passed['stage'] if passed else None,'history':history,'frozen':passed}

    passed=[s for s,r in results.items() if r['status']=='PASS'];failed=[s for s,r in results.items() if r['status']=='FAIL']
    out={'version':'CRYPTO_DAILY_EACH_SYMBOL_V38','definition':{'oneFilledTradeEveryCalendarDayPerCoin':True,'crossSymbolTopK':False,'dailyWinRate':'TP days / all calendar days; SL, CUT/TIMEOUT and missing days are non-wins','targetPerSymbolPct':TARGET,'rrAllowed':[1.0,2.0]},'universe':base.SYMBOLS,'passCount':len(passed),'failCount':len(failed),'symbolPassRatePct':round(100*len(passed)/len(base.SYMBOLS),2),'passed':passed,'failed':failed,'allSymbolsPass':not failed,'results':results}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2)
    print('SUMMARY',json.dumps({k:out[k] for k in ('version','passCount','failCount','symbolPassRatePct','passed','failed','allSymbolsPass')},indent=2),flush=True)

if __name__=='__main__':main()
