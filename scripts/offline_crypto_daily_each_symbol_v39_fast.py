#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
import scripts.offline_crypto_precision_evolver_v36 as b
import scripts.offline_crypto_precision_evolver_v36b as fixed
b.regime_at=fixed.fixed_regime_at
MAIN='data/provider_snapshots/crypto_4h_feb_jul_2026.json';BUF='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json';OUT='data/offline_crypto_daily_each_symbol_v39_fast.json';TARGET=80.0
STAGES=[('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
CFGS=[(1.0,.65,5,6),(1.0,.85,8,6),(2.0,.65,5,9),(2.0,.85,8,9)]

def load():
 a=json.load(open(MAIN));z=json.load(open(BUF));out={}
 for s in b.SYMBOLS:
  d={x[0]:x for x in a['data'][s]};d.update({x[0]:x for x in z['data'][s]});out[s]=[d[k] for k in sorted(d)]
 return out

def execm(rows,i,side,cfg):
 rr,rf,sw,hold=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr);sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold)
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0}
  if hs:return {'result':'SL','r':-1.0}
  if ht:return {'result':'TP','r':rr}
 last=rows[end-1]['close'];return {'result':'TIMEOUT','r':max(-1,min(rr,(last-entry)/risk*side))}

def extra(rows,i,side):
 r=rows[i];atr=r['atr'] or 1e-9;lo=min(x['low'] for x in rows[max(0,i-5):i+1]);hi=max(x['high'] for x in rows[max(0,i-5):i+1]);pos=0 if hi==lo else 2*(r['close']-lo)/(hi-lo)-1
 return [side*r.get('ret8',0)*20,side*r.get('ret24',0)*20,side*r.get('ret72',0)*10,side*(r['close']-r['open'])/atr,(r['high']-r['low'])/atr,side*pos,r['dt'].weekday()/6,math.sin(2*math.pi*r['dt'].hour/24),math.cos(2*math.pi*r['dt'].hour/24)]

def events(data,mp,cfg):
 out=defaultdict(list);times=sorted(set().union(*(set(x) for x in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<'2026-02-10' or d>'2026-07-31':continue
  pack=b.regime_at(mp,t)
  if not pack:continue
  eligible,reg=pack
  for s,q in eligible.items():
   i,r=q
   for side in (1,-1):
    f,m=b.features(s,r,reg,side);o=execm(data[s],i,side,cfg)
    if o:out[s].append({'day':d,'time':t,'side':side,'x':f+extra(data[s],i,side),**o})
 return out

def model(train,seed):
 if len(train)<90:return None
 X=np.asarray([x['x'] for x in train]);y=np.asarray([1 if x['result']=='TP' else 0 for x in train])
 if len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=110,max_depth=8,min_samples_leaf=9,max_features=.8,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(X,y);return m

def score(ev,train_end,a,c,seed):
 tr=[x for x in ev if x['day']<=train_end];te=[x for x in ev if a<=x['day']<=c];m=model(tr,seed)
 if m is None:return {}
 pr=m.predict_proba(np.asarray([x['x'] for x in te]))[:,1];g=defaultdict(list)
 for e,p in zip(te,pr):g[(e['day'],e['time'])].append((float(p),e))
 bd=defaultdict(list)
 for (d,t),z in g.items():
  z=sorted(z,key=lambda q:q[0],reverse=True);q=dict(z[0][1]);q['p']=z[0][0];q['edge']=z[0][0]-(z[1][0] if len(z)>1 else 0);bd[d].append(q)
 for d in bd:bd[d].sort(key=lambda x:x['time'])
 return bd

def days(a,c):return (datetime.fromisoformat(c).date()-datetime.fromisoformat(a).date()).days+1

def pols():
 out=[]
 for fb in (8,12,16,20):
  out.append(('FIXED',fb,0,0))
  for th in (.52,.56,.60,.64,.68,.72,.76,.80):
   for mg in (0,.04,.08,.12,.16):out.append(('FIRST',fb,th,mg))
 return out

def choose(rows,p):
 fam,fb,th,mg=p;z=[x for x in rows if x['time'].hour<=fb]
 if not z:z=rows
 if fam=='FIRST':
  for x in z:
   if x['p']>=th and x['edge']>=mg:return x
 return z[-1] if z else None

def stat(bd,p,a,c):
 exp=days(a,c);z=[choose(bd[d],p) for d in sorted(bd)];z=[x for x in z if x];w=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);to=len(z)-w-sl
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':w,'sl':sl,'timeout':to,'dailyWR':round(100*w/exp,2),'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9}

def tune(bd,a,c):
 best=None;bp=None
 for p in pols():
  s=stat(bd,p,a,c);r=(s['dailyWR'],s['meanR'],-s['missing'])
  if best is None or r>best:best=r;bp=(p,s)
 return bp

def main():
 raw=load();data={s:b.enrich(raw[s]) for s in b.SYMBOLS};mp=b.maps(data);cache=[]
 for cfg in CFGS:cache.append((cfg,events(data,mp,cfg)));print('CACHE',cfg,flush=True)
 res={}
 for si,sym in enumerate(b.SYMBOLS):
  hist=[];win=None
  for st,(name,da,db,fa,fb) in enumerate(STAGES):
   tr_end=(datetime.fromisoformat(da).date()-timedelta(days=1)).isoformat();best=None;ch=None
   for ci,(cfg,by) in enumerate(cache):
    ev=by.get(sym,[]);dev=score(ev,tr_end,da,db,39000+si*100+st*10+ci)
    if not dev:continue
    p,s=tune(dev,da,db);r=(s['dailyWR'],s['meanR'],-s['missing'])
    if best is None or r>best:best=r;ch=(cfg,p,s)
   if not ch:hist.append({'stage':name,'fail':'NO_MODEL'});continue
   cfg,p,ds=ch;ev=dict(cache)[cfg].get(sym,[]);final=score(ev,db,fa,fb,49000+si*10+st);fs=stat(final,p,fa,fb);ok=fs['missing']==0 and fs['dailyWR']>=TARGET and fs['meanR']>0
   rec={'stage':name,'cfg':cfg,'policy':p,'dev':ds,'final':fs,'pass':ok};hist.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[x for x in b.SYMBOLS if res[x]['status']=='PASS'];failed=[x for x in b.SYMBOLS if res[x]['status']=='FAIL'];out={'version':'CRYPTO_DAILY_EACH_SYMBOL_V39_FAST','rule':'Every coin trades every calendar day; TP/all days >=80%; RR1 or2; no cross-symbol TopK','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/61,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
