#!/usr/bin/env python3
import json, os, math, statistics
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx

try:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
except Exception as e:
    raise SystemExit(f'scikit-learn required: {e}')


def prep(rows):
    out=[]
    for r in rows:
        if r['rr'] < 1.0: continue
        z=dict(r); z['targetRR']=min(r['rr'],1.5); z['y']=1 if r['r']>0 else 0; z['targetR']=z['targetRR'] if z['y'] else -1.0
        sg=1 if r['side']=='BUY' else -1
        z['h1Align']=1 if r['h1']==sg else 0
        z['h4Align']=1 if r['h4']==sg else 0
        z['h1h4Align']=1 if z['h1Align'] and z['h4Align'] else 0
        z['rsiDev']=abs(r['rsi']-50)/50.0
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['y'] for r in rows); n=len(rows); l=n-w
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if not n:return 0.0
    p=w/n; den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def day_features(rows):
    by=defaultdict(list)
    for r in rows: by[r['date']].append(r)
    out={}
    for d,x in by.items():
        out[d]={
          'dayH1Align':sum(r['h1Align'] for r in x)/len(x),
          'dayH4Align':sum(r['h4Align'] for r in x)/len(x),
          'dayBuyShare':sum(r['side']=='BUY' for r in x)/len(x),
          'dayMedAdx':statistics.median(r['adx'] for r in x),
          'dayMedCoh3':statistics.median(r['coh3'] for r in x),
          'dayMedImpulse':statistics.median(r['impulse'] for r in x),
          'dayRegimeShare':sum(r['mode']=='REGIME_24H' for r in x)/len(x),
        }
    return out

def rowdict(r,days):
    d=days[r['date']]
    return {
      'score':r['score'],'adx':r['adx'],'rsiDev':r['rsiDev'],'dev':r['dev'],'fq3':r['fq3'],'fq24':r['fq24'],
      'coh3':r['coh3'],'coh24':r['coh24'],'impulse':r['impulse'],'regimeEv':r['regimeEv'],'session':r['session'],
      'h1Align':r['h1Align'],'h4Align':r['h4Align'],'h1h4Align':r['h1h4Align'],
      'dayH1Align':d['dayH1Align'],'dayH4Align':d['dayH4Align'],'dayBuyShare':d['dayBuyShare'],
      'dayMedAdx':d['dayMedAdx'],'dayMedCoh3':d['dayMedCoh3'],'dayMedImpulse':d['dayMedImpulse'],'dayRegimeShare':d['dayRegimeShare'],
      'side='+r['side']:1,'mode='+r['mode']:1,'group='+r['group']:1,'symbol='+r['symbol']:1
    }

def make_model(kind):
    if kind=='LOGIT': return LogisticRegression(C=.35,max_iter=2000,class_weight='balanced',solver='liblinear')
    if kind=='RF': return RandomForestClassifier(n_estimators=350,max_depth=4,min_samples_leaf=8,class_weight='balanced_subsample',random_state=17,n_jobs=-1)
    return ExtraTreesClassifier(n_estimators=450,max_depth=5,min_samples_leaf=6,class_weight='balanced',random_state=29,n_jobs=-1)

def fit_predict(train,test,kind,days):
    vec=DictVectorizer(sparse=False)
    X=vec.fit_transform([rowdict(r,days) for r in train]); y=[r['y'] for r in train]
    Xt=vec.transform([rowdict(r,days) for r in test])
    model=make_model(kind); model.fit(X,y)
    return model.predict_proba(Xt)[:,1].tolist()

def inner_oof(train,kind,days,warmup=3):
    dates=sorted(set(r['date'] for r in train)); preds=[]
    for i,d in enumerate(dates):
        if i<warmup: continue
        tr=[r for r in train if r['date']<d]; te=[r for r in train if r['date']==d]
        if len(tr)<50 or len(set(r['y'] for r in tr))<2: continue
        ps=fit_predict(tr,te,kind,days)
        preds += [(r,p) for r,p in zip(te,ps)]
    return preds

def select_from_scored(scored,topk,thr,buy_only=False):
    by=defaultdict(list)
    for r,p in scored:
        if buy_only and r['side']!='BUY': continue
        if p>=thr: by[r['date']].append((r,p))
    out=[]
    for d,x in by.items():
        x=sorted(x,key=lambda z:z[1],reverse=True)[:topk]
        out += [r for r,p in x]
    return out

def choose(train,days):
    best=None
    for kind in ('LOGIT','RF','ET'):
        scored=inner_oof(train,kind,days)
        for topk in (3,4,5,6,8):
            for thr in (.50,.55,.60,.65,.70,.75):
                for buy_only in (False,True):
                    z=select_from_scored(scored,topk,thr,buy_only); s=sm(z)
                    if s['n']<15 or s['dates']<3: continue
                    lb=100*wilson(s['wins'],s['n'])
                    score=(1 if s['wr']>=80 else 0,lb,s['wr'],s['meanR'],min(s['n'],50))
                    if best is None or score>best[0]: best=(score,(kind,topk,thr,buy_only),s)
    return best

def outer_walk(rows):
    days=day_features(rows); dates=sorted(set(r['date'] for r in rows)); allsel=[]; detail={}
    for i,d in enumerate(dates):
        if i<5: detail[d]={'warmup':True}; continue
        train=[r for r in rows if r['date']<d]; test=[r for r in rows if r['date']==d]
        best=choose(train,days)
        if not best: detail[d]={'warmup':False,'selected':{'n':0}}; continue
        kind,k,thr,buy_only=best[1]; ps=fit_predict(train,test,kind,days)
        sel=select_from_scored(list(zip(test,ps)),k,thr,buy_only); allsel+=sel
        detail[d]={'warmup':False,'rule':best[1],'inner':best[2],'selected':sm(sel)}
    return allsel,detail

def h3_cut(rows,threshold=-.35):
    out=[]
    for r in rows:
        z=dict(r);z['managed']='TP' if r['y'] else 'SL';z['managedR']=r['targetR']
        if r.get('checkpoint3Available') and r.get('bars',0)>12 and r.get('cut3r') is not None and r['cut3r']<=threshold:
            z['managed']='CUT';z['managedR']=r['cut3r']
        out.append(z)
    return out

def msm(rows):
    if not rows:return {'n':0}
    tp=sum(r['managed']=='TP' for r in rows);sl=sum(r['managed']=='SL' for r in rows);cut=sum(r['managed']=='CUT' for r in rows)
    den=tp+sl
    return {'n':len(rows),'TP':tp,'SL':sl,'CUT':cut,'wrExcludingCut':round(100*tp/den,2) if den else None,
            'meanManagedR':round(statistics.mean(r['managedR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def main():
    rows=prep(extract_fx());sel,detail=outer_walk(rows); base=sm(rows)
    managed=msm(h3_cut(sel,-.35))
    out={'version':'FOREX V10 ML ENSEMBLE INDEPENDENT','providerCreditsUsed':0,
      'method':'Forex-only nonlinear ensemble. Separate Forex factors/structure only; chronological nested model/config selection, no crypto features. BUY-only is a candidate branch, not forced. RR capped conservatively to 1.5.',
      'baseline':base,'walkForward':sm(sel),'H3Managed':managed,'byDate':detail,'targetMet':False}
    w=managed.get('wrExcludingCut') or 0; out['targetMet']=bool(managed.get('n',0)>=20 and w>=80 and 1<=managed.get('avgRR',0)<=1.5 and managed.get('meanManagedR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v10_ml_ensemble.json','w'),indent=2)
    print(json.dumps({'version':out['version'],'providerCreditsUsed':0,'baseline':base,'walkForward':out['walkForward'],'H3Managed':managed,'targetMet':out['targetMet'],'byDate':detail},indent=2))
if __name__=='__main__':main()
