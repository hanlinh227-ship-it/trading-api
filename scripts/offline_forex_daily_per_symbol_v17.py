#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
import scripts.offline_forex_precision_evolver_v15 as b

OUT='data/offline_forex_daily_per_symbol_v17.json'
TARGET=80.0
WINDOWS={'ALL':(0,4,8,12,16,20),'ASIA':(0,4,8),'LONDON':(8,12),'NY':(12,16,20),'EU_US':(8,12,16)}
DIRS=('BOTH','BUY','SELL')
MODELS=((3,12),(5,20))
# MARKET only: every symbol must actually enter every weekday.
CFGS=[]
for rr in (1.0,2.0):
  for rf in (.55,.70,.90,1.10):
    for sw in (6,12):
      hold=18 if rr==1.0 else 36
      for ca,cr,cm in ((0,0,'NONE'),(1,.20,'R'),(1,0.0,'R'),(2,.10,'R'),(2,-.20,'EMA'),(3,-.35,'EMA')):
        CFGS.append((rr,rf,sw,hold,ca,cr,cm))

def exec_mkt(rows,i,side,cfg):
    rr,rf,sw,hold,ca,cr,cm=cfg
    if i+1>=len(rows) or not rows[i].get('atr'): return None
    sig=rows[i]; atr=sig['atr']; ei=i+1; entry=rows[ei]['open']
    recent=rows[max(0,i-sw+1):i+1]
    swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent)
    struct=entry-swing if side==1 else swing-entry
    risk=max(rf*atr,struct+.05*atr,.25*atr)
    sl=entry-side*risk; tp=entry+side*rr*risk; end=min(len(rows),ei+hold)
    for j in range(ei,end):
        x=rows[j]; hs=x['low']<=sl if side==1 else x['high']>=sl; ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0,j-ei+1)
        if hs:return ('SL',-1.0,j-ei+1)
        if ht:return ('TP',rr,j-ei+1)
        age=j-ei+1
        if ca and age>=ca:
            cur=(x['close']-entry)/risk*side
            if cm=='R' and cur<=cr:return ('CUT',max(-1,cur),age)
            if cm=='EMA' and x.get('ema20') is not None and (x['close']-x['ema20'])*side<0 and cur<=cr:return ('CUT',max(-1,cur),age)
    last=rows[max(ei,end-1)]['close']; cur=(last-entry)/risk*side
    return ('CUT',max(-1,min(rr,cur)),end-ei)

def raw_candidates(data,maps,times):
    out=defaultdict(list)
    for t in times:
        if t.weekday()>=5: continue
        fp=b.factor_pack(maps,t)
        if not fp: continue
        for sym in b.PAIRS:
            i,row=maps[sym][t]
            if any(row.get(k) is None for k in ('adx','rsi','ema50','atr')):continue
            for side in (1,-1):
                x,meta=b.candidate_features(sym,row,fp,side)
                out[sym].append({'time':t,'day':t.date().isoformat(),'i':i,'side':side,'x':x,'meta':meta})
    return out

def attach(sym,raw,rows,cfg):
    z=[]
    for e in raw:
        o=exec_mkt(rows,e['i'],e['side'],cfg)
        if o:
            q=dict(e);q['result'],q['r'],q['bars']=o;z.append(q)
    return z

def model(train,depth,leaf,seed):
    if len(train)<80:return None
    X=np.asarray([x['x'] for x in train],float); y=np.asarray([1 if x['result']=='TP' else 0 for x in train],int)
    if len(set(y))<2:return None
    m=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=2**depth-1,min_samples_leaf=leaf,learning_rate=.055,l2_regularization=4.0,random_state=seed)
    m.fit(X,y);return m

def scored(ev,train_end,a,begend,spec,seed):
    start,end=begend
    tr=[x for x in ev if x['day']<=train_end]; te=[x for x in ev if start<=x['day']<=end]
    m=model(tr,*spec,seed)
    if m is None or not te:return []
    p=m.predict_proba(np.asarray([x['x'] for x in te],float))[:,1]
    return [dict(x,prob=float(v)) for x,v in zip(te,p)]

def choose_daily(rows,window,direction):
    hours=WINDOWS[window]; g=defaultdict(list)
    for x in rows:
        if x['time'].hour not in hours:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        g[x['day']].append(x)
    return [max(v,key=lambda q:q['prob']) for d,v in sorted(g.items())]

def weekdays(a,begend):
    import datetime as dt
    s=dt.date.fromisoformat(a); e=dt.date.fromisoformat(begend);n=0
    while s<=e:
        if s.weekday()<5:n+=1
        s+=dt.timedelta(days=1)
    return n

def sm(z,expected):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=sum(x['result']=='CUT' for x in z);den=tp+sl
    return {'days':len(z),'expectedDays':expected,'coveragePct':round(100*len(z)/expected,2) if expected else 0,'tp':tp,'sl':sl,'cut':cut,'resolved':den,'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'cutRatePct':round(100*cut/len(z),2) if z else 0}

def rank(s):
    minres=max(5,math.ceil(s['expectedDays']*.25))
    hit=s['coveragePct']>=99.9 and s['resolved']>=minres and s['wr']>=TARGET and s['meanR']>0
    return (int(hit),s['wr']-max(0,minres-s['resolved'])*8,s['meanR'],-s['cutRatePct'],s['resolved'])

def tune(rows,expected):
    best=None;bp=None
    for w in WINDOWS:
      for d in DIRS:
        z=choose_daily(rows,w,d);s=sm(z,expected);r=rank(s)
        if best is None or r>best:best=r;bp={'window':w,'direction':d,'stats':s}
    return bp

def stage(sym,raw,rows,dev_train_end,dev_range,final_train_end,final_range,seed0):
    edev=weekdays(*dev_range); efinal=weekdays(*final_range)
    best=None;payload=None
    for ci,cfg in enumerate(CFGS):
        ev=attach(sym,raw,rows,cfg)
        for mi,spec in enumerate(MODELS):
            sr=scored(ev,dev_train_end,'',dev_range,spec,seed0+ci*7+mi)
            if not sr:continue
            p=tune(sr,edev);r=rank(p['stats'])
            if best is None or r>best:best=r;payload=(cfg,spec,p,ev)
    if not payload:return None,sm([],efinal)
    cfg,spec,p,ev=payload
    fr=scored(ev,final_train_end,'',final_range,spec,seed0+9000)
    fs=sm(choose_daily(fr,p['window'],p['direction']),efinal)
    return {'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingHours':cfg[2],'maxHoldH':cfg[3],'cutAfterH':cfg[4],'cutR':cfg[5],'cutMode':cfg[6]},'model':{'depth':spec[0],'leaf':spec[1]},'selector':{'window':p['window'],'direction':p['direction']},'development':p['stats']},fs

def main():
    doc=json.load(open(b.SNAP,encoding='utf-8')); data={s:b.enrich(doc['data'][s]) for s in b.PAIRS};maps,times=b.make_maps(data);raw=raw_candidates(data,maps,times)
    results={}
    for si,sym in enumerate(b.PAIRS):
        p,fs=stage(sym,raw[sym],data[sym],'2026-04-30',('2026-05-01','2026-05-31'),'2026-05-31',('2026-06-01','2026-06-30'),170000+si*100)
        if p and rank(fs)[0]: results[sym]={'status':'PASS','stage':'JUNE','method':p,'final':fs};print('PASS_JUNE',sym,fs,flush=True);continue
        p2,fs2=stage(sym,raw[sym],data[sym],'2026-05-31',('2026-06-01','2026-06-30'),'2026-06-30',('2026-07-01','2026-07-31'),270000+si*100)
        ok=bool(p2 and rank(fs2)[0]);results[sym]={'status':'PASS' if ok else 'FAIL','stage':'JULY','method':p2,'final':fs2,'previousJune':fs};print('PASS_JULY' if ok else 'FAIL',sym,fs2,flush=True)
    passed=[s for s in b.PAIRS if results[s]['status']=='PASS'];failed=[s for s in b.PAIRS if results[s]['status']!='PASS']
    ans={'version':'FOREX_DAILY_PER_SYMBOL_V17','definition':{'oneMarketTradeEveryWeekdayPerPair':True,'crossSymbolRanking':False,'rrAllowed':[1.0,2.0],'wr':'TP/(TP+SL)','cutSeparate':True},'universeCount':28,'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','passed','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
