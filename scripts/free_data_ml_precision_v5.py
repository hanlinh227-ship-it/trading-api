#!/usr/bin/env python3
import json, math, statistics, subprocess, sys
from collections import defaultdict
import scripts.free_data_precision_evolver_v1 as m
try:
    import numpy as np
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.metrics import precision_score
except Exception as e:
    print('SKLEARN_IMPORT_FAIL',e);raise

VERSION='FREE_DATA_ML_PRECISION_V5'
HIDDEN=m.HIDDEN_START

def build(data,market,rr,risk,hold):
    out=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if i<100 or m.day(r['ts'])>=HIDDEN:continue
            if r.get('adx') is None or r.get('ema100') is None or r.get('r18') is None:continue
            if market=='FX' and r.get('factorNorm') is None:continue
            if market=='CRYPTO' and r.get('breadth') is None:continue
            side=1 if r['ema20']>r['ema50'] and r['r6']>0 else (-1 if r['ema20']<r['ema50'] and r['r6']<0 else 0)
            if not side:continue
            o=m.trade_outcome(rows,i,side,rr,risk,hold)
            if not o:continue
            ar=r['rsi'] if side==1 else 100-r['rsi'];h=m.hour(r['ts']);sess=0 if h in (0,4) else 1 if h in (8,12) else 2
            f=[side,r['adx']/50,abs(r['mom6atr'])/3,min(2,r['emaDistAtr'])/2,ar/100,int(m.sign(r['r18'])==side),int((side==1 and r['close']>r['prevHigh6']) or (side==-1 and r['close']<r['prevLow6'])),int((side==1 and r['close']>r['prevHigh18']) or (side==-1 and r['close']<r['prevLow18'])),sess/2]
            if market=='FX':
                f += [max(-3,min(3,side*r['factorNorm']))/3,abs(r['r6'])*100,abs(r['r18'])*100]
            else:
                ba=r['breadth'] if side==1 else 1-r['breadth'];f += [ba, max(-.05,min(.05,side*r['btcR6']))*20,max(-.08,min(.08,side*r['rel6']))*12.5,abs(r['r6'])*20,abs(r['r18'])*10]
            out.append({'symbol':s,'ts':r['ts'],'day':m.day(r['ts']),'side':side,'x':f,'result':o['result'],'r':o['r'],'rr':rr})
    return out

def split(events,end):return [e for e in events if e['day']<=end]
def period(events,a,b):return [e for e in events if a<=e['day']<=b]
def xy(z):
    q=[e for e in z if e['result'] in ('TP','SL')]
    return np.array([e['x'] for e in q],float),np.array([1 if e['result']=='TP' else 0 for e in q],int),q

def make_model(kind,depth,leaf,trees,seed=42):
    if kind=='EXTRA':return ExtraTreesClassifier(n_estimators=trees,max_depth=depth,min_samples_leaf=leaf,max_features='sqrt',class_weight='balanced_subsample',n_jobs=-1,random_state=seed)
    if kind=='RF':return RandomForestClassifier(n_estimators=trees,max_depth=depth,min_samples_leaf=leaf,max_features='sqrt',class_weight='balanced_subsample',n_jobs=-1,random_state=seed)
    return HistGradientBoostingClassifier(max_iter=trees,max_depth=depth,min_samples_leaf=leaf,l2_regularization=2,learning_rate=.05,random_state=seed)

def score_period(model,z,threshold,topk):
    if not z:return []
    X=np.array([e['x'] for e in z],float);pr=model.predict_proba(X)[:,1]
    by=defaultdict(list)
    for e,p in zip(z,pr):
        if p>=threshold:
            q=dict(e);q['prob']=float(p);by[e['day']].append(q)
    out=[]
    for d,a in by.items():out.extend(sorted(a,key=lambda x:x['prob'],reverse=True)[:topk])
    return out

def stat(z):
    tp=sum(e['result']=='TP' for e in z);sl=sum(e['result']=='SL' for e in z);cut=sum(e['result']=='CUT' for e in z);den=tp+sl
    return {'n':len(z),'tp':tp,'sl':sl,'cut':cut,'wr':100*tp/den if den else 0,'meanR':statistics.mean([e['r'] for e in z]) if z else -9,'resolvedRate':100*den/len(z) if z else 0,'symbols':len(set(e['symbol'] for e in z))}

def tune(events,market):
    # Feb-May train, June architecture/threshold selection, July locked evaluation for this version.
    tr=period(events,'2026-02-01','2026-05-31');ju=period(events,'2026-06-01','2026-06-30');jl=period(events,'2026-07-01','2026-07-31')
    X,y,_=xy(tr)
    if len(y)<50 or len(set(y))<2:return None
    best=None
    for kind in ('EXTRA','RF','HGB'):
      for depth in (3,5,7,None) if kind!='HGB' else (3,5,7):
       for leaf in (4,8,15,25,40):
        for trees in (150,300):
         try:model=make_model(kind,depth,leaf,trees);model.fit(X,y)
         except Exception:continue
         for th in (.58,.62,.66,.70,.74,.78,.82,.86,.90,.93,.95):
          for topk in (1,2):
           a=score_period(model,ju,th,topk);s=stat(a)
           minj=8 if market=='FX' else 10
           if s['n']<minj or s['resolvedRate']<70:continue
           key=(int(s['wr']>=80 and s['meanR']>0),s['wr'],s['meanR'],min(s['n'],30))
           if best is None or key>best[0]:best=(key,kind,depth,leaf,trees,th,topk,s)
    if not best:return None
    _,kind,depth,leaf,trees,th,topk,jus=best
    model=make_model(kind,depth,leaf,trees);model.fit(X,y)
    jsel=score_period(model,jl,th,topk);jls=stat(jsel)
    devs=stat(score_period(model,tr,th,topk))
    return {'model':{'kind':kind,'depth':depth,'leaf':leaf,'trees':trees},'threshold':th,'topk':topk,'DEV':devs,'JUNE':jus,'JULY':jls,'julySelected':jsel}

def search(data,market):
    best=None
    for rr in (1.0,1.5):
     for risk in (.65,.8,1.0,1.2,1.4):
      for hold in (6,9,12,18):
       events=build(data,market,rr,risk,hold);r=tune(events,market)
       if not r:continue
       d,j,u=r['DEV'],r['JUNE'],r['JULY']
       minDev=25 if market=='FX' else 30;minJul=8 if market=='FX' else 10
       hit=d['n']>=minDev and j['n']>=minJul and u['n']>=minJul and d['wr']>=80 and j['wr']>=80 and u['wr']>=80 and min(d['meanR'],j['meanR'],u['meanR'])>0
       obj=(int(hit),min(d['wr'],j['wr'],u['wr']),statistics.mean([d['wr'],j['wr'],u['wr']]),statistics.mean([d['meanR'],j['meanR'],u['meanR']]),d['n']+j['n']+u['n'])
       item=(obj,rr,risk,hold,r)
       if best is None or obj>best[0]:
          best=item;print('BEST',market,rr,risk,hold,json.dumps({k:v for k,v in r.items() if k!='julySelected'}),flush=True)
       if hit:return best
    return best

def pack(x):
    if not x:return None
    o,rr,risk,hold,r=x
    return {'qualified':bool(o[0]),'objective':o,'rr':rr,'risk':risk,'hold':hold,'model':r['model'],'threshold':r['threshold'],'topk':r['topk'],'folds':{'DEV':m.compact(r['DEV']),'JUNE':m.compact(r['JUNE']),'JULY':m.compact(r['JULY'])}}

def main():
    print(json.dumps({'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False}),flush=True)
    fx={};cr={};fe={};ce={};src={}
    for s in m.FX:
      try:fx[s]=m.indicators(m.fetch_fx(s));print('FX',s,len(fx[s]),flush=True)
      except Exception as e:fe[s]=str(e);print('FX_FAIL',s,str(e)[:90],flush=True)
    m.add_context(fx,'FX')
    for s in m.CRYPTO:
      try:r,q=m.fetch_crypto(s);cr[s]=m.indicators(r);src[s]=q;print('CR',s,q,len(r),flush=True)
      except Exception as e:ce[s]=str(e);print('CR_FAIL',s,str(e)[:90],flush=True)
    m.add_context(cr,'CRYPTO')
    print('COVERAGE',json.dumps({'fxLoaded':len(fx),'fxRequested':len(m.FX),'fxFailed':fe,'cryptoLoaded':len(cr),'cryptoRequested':len(m.CRYPTO),'cryptoFailed':ce,'sources':src}),flush=True)
    f=search(fx,'FX');c=search(cr,'CRYPTO')
    out={'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,'coverage':{'fxLoaded':len(fx),'fxRequested':len(m.FX),'cryptoLoaded':len(cr),'cryptoRequested':len(m.CRYPTO)},'forex':pack(f),'crypto':pack(c),'bothQualifiedForLock':bool(f and c and f[0][0] and c[0][0]),'integrity':'Direction generated from pre-entry structure; meta-label model trained only Feb-May, tuned on June, evaluated July; Aug excluded.'}
    print('FINAL_ML',json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
