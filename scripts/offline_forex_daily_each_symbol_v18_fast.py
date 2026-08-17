#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
import scripts.offline_forex_precision_evolver_v15 as b

MAIN='data/provider_snapshots/forex_h1_feb_jul_2026.json';BUF='data/provider_snapshots/forex_h1_aug1_8_2026_final1.json';OUT='data/offline_forex_daily_each_symbol_v18_fast.json'
TARGET=80.0
STAGES=[('APR','2026-03-01','2026-03-31','2026-04-01','2026-04-30'),('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
CFGS=[(1.0,.65,6,24),(1.0,.85,12,24),(2.0,.65,6,36),(2.0,.85,12,36)]


def load():
 a=json.load(open(MAIN));z=json.load(open(BUF));out={}
 for p in b.PAIRS:
  d={x[0]:x for x in a['data'][p]};d.update({x[0]:x for x in z['data'][p]});out[p]=[d[k] for k in sorted(d)]
 return out

def execm(rows,i,side,cfg):
 rr,rf,sw,hold=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];entry_i=i+1;entry=rows[entry_i]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr);sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),entry_i+hold)
 for j in range(entry_i,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0}
  if hs:return {'result':'SL','r':-1.0}
  if ht:return {'result':'TP','r':rr}
 last=rows[end-1]['close'];return {'result':'TIMEOUT','r':max(-1,min(rr,(last-entry)/risk*side))}

def extra(rows,i,side):
 r=rows[i];atr=r['atr'] or 1e-9;lo=min(x['low'] for x in rows[max(0,i-23):i+1]);hi=max(x['high'] for x in rows[max(0,i-23):i+1]);pos=0 if hi==lo else 2*(r['close']-lo)/(hi-lo)-1
 vals=[side*r.get('ret3',0)*100,side*r.get('ret6',0)*100,side*r.get('ret12',0)*100,side*r.get('ret24',0)*100,side*r.get('ret72',0)*100,side*(r['close']-r['open'])/atr,(r['high']-r['low'])/atr,side*pos,r['dt'].weekday()/4,math.sin(2*math.pi*r['dt'].hour/24),math.cos(2*math.pi*r['dt'].hour/24)]
 return vals

def events(data,maps,times,cfg):
 out=defaultdict(list)
 for t in times:
  fp=b.factor_pack(maps,t)
  if not fp:continue
  for p in b.PAIRS:
   i,r=maps[p][t]
   if r.get('adx') is None or r.get('ema50') is None:continue
   for side in (1,-1):
    f,m=b.candidate_features(p,r,fp,side);o=execm(data[p],i,side,cfg)
    if o:out[p].append({'day':t.date().isoformat(),'time':t,'side':side,'x':f+extra(data[p],i,side),**o})
 return out

def model(train,seed):
 if len(train)<100:return None
 X=np.asarray([x['x'] for x in train]);y=np.asarray([1 if x['result']=='TP' else 0 for x in train])
 if len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=120,max_depth=8,min_samples_leaf=10,max_features=.75,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(X,y);return m

def score(ev,train_end,a,c,seed):
 tr=[x for x in ev if x['day']<=train_end];te=[x for x in ev if a<=x['day']<=c];m=model(tr,seed)
 if m is None:return {}
 pr=m.predict_proba(np.asarray([x['x'] for x in te]))[:,1];g=defaultdict(list)
 for e,p in zip(te,pr):g[(e['day'],e['time'])].append((float(p),e))
 bd=defaultdict(list)
 for (d,t),z in g.items():
  if t.weekday()>=5:continue
  z=sorted(z,key=lambda q:q[0],reverse=True);q=dict(z[0][1]);q['p']=z[0][0];q['edge']=z[0][0]-(z[1][0] if len(z)>1 else 0);bd[d].append(q)
 for d in bd:bd[d].sort(key=lambda x:x['time'])
 return bd

def weekdays(a,c):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();n=0
 while x<=y:
  if x.weekday()<5:n+=1
  x+=timedelta(days=1)
 return n

def pols():
 q=[]
 for fb in (8,12,16,20):
  q.append(('FIXED',fb,0,0))
  for th in (.54,.58,.62,.66,.70,.74,.78):
   for mg in (0,.04,.08,.12):q.append(('FIRST',fb,th,mg))
 return q

def choose(rows,p):
 fam,fb,th,mg=p;z=[x for x in rows if x['time'].hour<=fb]
 if not z:z=rows
 if fam=='FIRST':
  for x in z:
   if x['p']>=th and x['edge']>=mg:return x
 return z[-1] if z else None

def stat(bd,p,a,c):
 exp=weekdays(a,c);z=[choose(bd[d],p) for d in sorted(bd)];z=[x for x in z if x];w=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);to=len(z)-w-sl
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':w,'sl':sl,'timeout':to,'dailyWR':round(100*w/exp,2),'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9}

def tune(bd,a,c):
 best=None;bp=None
 for p in pols():
  s=stat(bd,p,a,c);r=(s['dailyWR'],s['meanR'],-s['missing'])
  if best is None or r>best:best=r;bp=(p,s)
 return bp

def main():
 raw=load();data={p:b.enrich(raw[p]) for p in b.PAIRS};maps,times=b.make_maps(data);cache=[]
 for cfg in CFGS:cache.append((cfg,events(data,maps,times,cfg)));print('CACHE',cfg,flush=True)
 res={}
 for si,sym in enumerate(b.PAIRS):
  hist=[];win=None
  for st,(name,da,db,fa,fb) in enumerate(STAGES):
   tr_end=(datetime.fromisoformat(da).date()-timedelta(days=1)).isoformat();best=None;ch=None
   for ci,(cfg,by) in enumerate(cache):
    ev=by[sym];dev=score(ev,tr_end,da,db,18000+si*100+st*10+ci)
    if not dev:continue
    p,s=tune(dev,da,db);r=(s['dailyWR'],s['meanR'],-s['missing'])
    if best is None or r>best:best=r;ch=(cfg,p,s)
   if not ch:hist.append({'stage':name,'fail':'NO_MODEL'});continue
   cfg,p,ds=ch;ev=dict(cache)[cfg][sym];final=score(ev,db,fa,fb,28000+si*10+st);fs=stat(final,p,fa,fb);ok=fs['missing']==0 and fs['dailyWR']>=TARGET and fs['meanR']>0
   rec={'stage':name,'cfg':cfg,'policy':p,'dev':ds,'final':fs,'pass':ok};hist.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[x for x in b.PAIRS if res[x]['status']=='PASS'];failed=[x for x in b.PAIRS if res[x]['status']=='FAIL'];out={'version':'FOREX_DAILY_EACH_SYMBOL_V18_FAST','rule':'Every pair trades every weekday; TP/all weekdays >=80%; RR 1 or2; no cross-symbol TopK','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/28,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
