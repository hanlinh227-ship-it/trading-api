#!/usr/bin/env python3
import json, os, math, statistics
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_crypto
from scripts.offline_crypto_v28_separate import PROFILE, FAMILY_WEIGHTS, base_symbol

try:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
except Exception as e:
    raise SystemExit(f'scikit-learn required: {e}')


def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0: continue
        z=dict(r); z['coin']=base_symbol(r['symbol']); z['family']=PROFILE.get(z['coin'],'L1')
        z['targetRR']=min(r['rr'],1.5); z['y']=1 if r['r']>0 else 0; z['targetR']=z['targetRR'] if z['y'] else -1.0
        b=r.get('breadth'); z['breadthAlign']=0.0 if b is None else ((b-.5)*2*(1 if r['side']=='BUY' else -1))
        z['microAlign']=0.0 if r['micro']==0 else (1.0 if (r['side']=='BUY' and r['micro']>0) or (r['side']=='SELL' and r['micro']<0) else -1.0)
        wb,wm,wh,wc=FAMILY_WEIGHTS.get(z['family'],(1,1,1,.8))
        z['driverStrength']=wb*z['breadthAlign'] + wm*(r['macro']/6.0) + wh*(r['htf']/10.0) + .6*z['microAlign'] - wc*r['chase']
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['y'] for r in rows);n=len(rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if not n:return 0.0
    p=w/n;den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def day_state(rows):
    by=defaultdict(list)
    for r in rows:by[r['date']].append(r)
    out={}
    for d,x in by.items():
        bs=[r['breadth'] for r in x if r.get('breadth') is not None]
        out[d]={
          'breadth':statistics.median(bs) if bs else .5,
          'medMacro':statistics.median(r['macro'] for r in x),
          'medHTF':statistics.median(r['htf'] for r in x),
          'medChase':statistics.median(r['chase'] for r in x),
          'buyShare':sum(r['side']=='BUY' for r in x)/len(x),
          'trendShare':sum(r['regime']=='trend' for r in x)/len(x),
          'transitionShare':sum(r['regime']=='transition' for r in x)/len(x),
        }
    return out

def priors(train):
    global_p=(sum(r['y'] for r in train)+4)/(len(train)+8)
    def mk(key,alpha):
        by=defaultdict(list)
        for r in train:by[key(r)].append(r['y'])
        return {k:(sum(v)+alpha*global_p)/(len(v)+alpha) for k,v in by.items()}
    return global_p,mk(lambda r:r['coin'],6),mk(lambda r:r['family'],10),mk(lambda r:(r['family'],r['side']),10)

def rowdict(r,days,pr):
    gp,sp,fp,fsp=pr; d=days[r['date']]
    return {
      'score':r['score'],'macro':r['macro'],'htf':r['htf'],'microAlign':r['microAlign'],'chase':r['chase'],
      'breadthAlign':r['breadthAlign'],'driverStrength':r['driverStrength'],
      'dayBreadth':d['breadth'],'dayExtreme':abs(d['breadth']-.5)*2,'dayMedMacro':d['medMacro'],'dayMedHTF':d['medHTF'],
      'dayMedChase':d['medChase'],'dayBuyShare':d['buyShare'],'dayTrendShare':d['trendShare'],'dayTransitionShare':d['transitionShare'],
      'symbolPrior':sp.get(r['coin'],gp),'familyPrior':fp.get(r['family'],gp),'familySidePrior':fsp.get((r['family'],r['side']),gp),
      'coin='+r['coin']:1,'family='+r['family']:1,'side='+r['side']:1,'regime='+r['regime']:1
    }

def make_model(kind):
    if kind=='LOGIT':return LogisticRegression(C=.25,max_iter=2500,class_weight='balanced',solver='liblinear')
    if kind=='RF':return RandomForestClassifier(n_estimators=450,max_depth=5,min_samples_leaf=10,class_weight='balanced_subsample',random_state=31,n_jobs=-1)
    return ExtraTreesClassifier(n_estimators=500,max_depth=6,min_samples_leaf=8,class_weight='balanced',random_state=41,n_jobs=-1)

def fit_predict(train,test,kind,days):
    pr=priors(train);vec=DictVectorizer(sparse=False)
    X=vec.fit_transform([rowdict(r,days,pr) for r in train]);Xt=vec.transform([rowdict(r,days,pr) for r in test]);y=[r['y'] for r in train]
    m=make_model(kind);m.fit(X,y);return m.predict_proba(Xt)[:,1].tolist()

def scored_select(scored,k,thr,align_only):
    by=defaultdict(list)
    for r,p in scored:
        if p<thr:continue
        if align_only and r['breadthAlign']<=0:continue
        by[r['date']].append((r,p))
    out=[]
    for d,x in by.items():out += [r for r,p in sorted(x,key=lambda z:z[1],reverse=True)[:k]]
    return out

def inner_oof(train,kind,days,warm=4):
    ds=sorted(set(r['date'] for r in train));out=[]
    for i,d in enumerate(ds):
        if i<warm:continue
        tr=[r for r in train if r['date']<d];te=[r for r in train if r['date']==d]
        if len(tr)<150 or len(set(r['y'] for r in tr))<2:continue
        ps=fit_predict(tr,te,kind,days);out += list(zip(te,ps))
    return out

def choose(train,days):
    best=None
    for kind in ('LOGIT','RF','ET'):
        scored=inner_oof(train,kind,days)
        for k in (3,4,5,6,8):
            for thr in (.48,.52,.56,.60,.64,.68,.72):
                for align in (False,True):
                    z=scored_select(scored,k,thr,align);s=sm(z)
                    if s['n']<12 or s['dates']<3:continue
                    lb=100*wilson(s['wins'],s['n'])
                    score=(1 if s['wr']>=80 else 0,lb,s['wr'],s['meanR'],min(s['n'],40))
                    if best is None or score>best[0]:best=(score,(kind,k,thr,align),s)
    return best

def walk(rows):
    days=day_state(rows);ds=sorted(set(r['date'] for r in rows));out=[];detail={}
    for i,d in enumerate(ds):
        if i<6:detail[d]={'warmup':True};continue
        tr=[r for r in rows if r['date']<d];te=[r for r in rows if r['date']==d];best=choose(tr,days)
        if not best:detail[d]={'warmup':False,'selected':{'n':0}};continue
        kind,k,thr,align=best[1];ps=fit_predict(tr,te,kind,days);sel=scored_select(list(zip(te,ps)),k,thr,align);out+=sel
        detail[d]={'warmup':False,'rule':best[1],'inner':best[2],'selected':sm(sel),
                   'selectedSymbols':[r['coin'] for r in sel]}
    return out,detail

def main():
    rows=prep(extract_crypto());sel,detail=walk(rows);res=sm(sel)
    out={'version':'CRYPTO V31 SYMBOL-SPECIFIC ML','providerCreditsUsed':0,
      'method':'Crypto-only V24/Apr16 continuation. Each coin uses its own symbol prior and linked family drivers plus BTC/breadth proxy, HTF/macro/micro/anti-chase. Chronological nested walk-forward; no Forex factors.',
      'walkForward':res,'byDate':detail,'targetMet':bool(res.get('n',0)>=20 and res.get('wr',0)>=80 and 1<=res.get('avgRR',0)<=1.5 and res.get('meanR',-9)>0),
      'hourlyManagement':'NOT_REPLAYABLE_FROM_COMMITTED_OLD_CRYPTO_DATA'}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v31_symbol_ml.json','w'),indent=2)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
