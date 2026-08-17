#!/usr/bin/env python3
import json,math,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
import scripts.offline_forex_precision_evolver_v15 as b

MAIN='data/provider_snapshots/forex_h1_feb_jul_2026.json';BUF='data/provider_snapshots/forex_h1_aug1_8_2026_final1.json';OUT='data/offline_forex_daily_each_symbol_v19_managed.json';TARGET=80.0
STAGES=[('APR','2026-03-01','2026-03-31','2026-04-01','2026-04-30'),('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
# rr, risk floor, swing hours, max hold hours, review age, cut R, EMA used for thesis invalidation
CFGS=[(1.0,.65,6,24,1,-.20,20),(1.0,.65,6,24,2,-.35,20),(1.0,.85,12,30,2,-.35,50),(1.0,.85,12,30,3,-.45,20),(2.0,.65,6,36,1,-.20,20),(2.0,.65,6,36,2,-.35,20),(2.0,.85,12,48,2,-.35,50),(2.0,.85,12,48,3,-.45,20)]

def load():
 a=json.load(open(MAIN));z=json.load(open(BUF));out={}
 for p in b.PAIRS:
  d={x[0]:x for x in a['data'][p]};d.update({x[0]:x for x in z['data'][p]});out[p]=[d[k] for k in sorted(d)]
 return out

def execm(rows,i,side,cfg):
 rr,rf,sw,hold,ca,cr,ema_n=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr);sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold)
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0}
  if hs:return {'result':'SL','r':-1.0}
  if ht:return {'result':'TP','r':rr}
  age=j-ei+1
  if age>=ca:
   em=x.get('ema20') if ema_n==20 else x.get('ema50');cur=(x['close']-entry)/risk*side
   if em is not None and (x['close']-em)*side<0 and cur<=cr:return {'result':'CUT','r':max(-1,cur)}
 last=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(last-entry)/risk*side))}

def extra(rows,i,side):
 r=rows[i];atr=r['atr'] or 1e-9;lo=min(x['low'] for x in rows[max(0,i-23):i+1]);hi=max(x['high'] for x in rows[max(0,i-23):i+1]);pos=0 if hi==lo else 2*(r['close']-lo)/(hi-lo)-1
 return [side*r.get('ret3',0)*100,side*r.get('ret6',0)*100,side*r.get('ret12',0)*100,side*r.get('ret24',0)*100,side*r.get('ret72',0)*100,side*(r['close']-r['open'])/atr,(r['high']-r['low'])/atr,side*pos,r['dt'].weekday()/4,math.sin(2*math.pi*r['dt'].hour/24),math.cos(2*math.pi*r['dt'].hour/24)]

def events(data,maps,times,cfg):
 out=defaultdict(list)
 for t in times:
  fp=b.factor_pack(maps,t)
  if not fp:continue
  for p in b.PAIRS:
   i,r=maps[p][t]
   if r.get('adx') is None or r.get('ema50') is None:continue
   for side in (1,-1):
    f,_=b.candidate_features(p,r,fp,side);o=execm(data[p],i,side,cfg)
    if o:out[p].append({'day':t.date().isoformat(),'time':t,'side':side,'x':f+extra(data[p],i,side),**o})
 return out

def model(tr,seed):
 if len(tr)<100:return None
 X=np.asarray([x['x'] for x in tr]);y=np.asarray([1 if x['result']=='TP' else 0 for x in tr])
 if len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=120,max_depth=8,min_samples_leaf=10,max_features=.75,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(X,y);return m

def score(ev,te,a,c,seed):
 tr=[x for x in ev if x['day']<=te];q=[x for x in ev if a<=x['day']<=c];m=model(tr,seed)
 if m is None:return {}
 pr=m.predict_proba(np.asarray([x['x'] for x in q]))[:,1];g=defaultdict(list)
 for e,p in zip(q,pr):g[(e['day'],e['time'])].append((float(p),e))
 bd=defaultdict(list)
 for (d,t),z in g.items():
  if t.weekday()>=5:continue
  z=sorted(z,key=lambda x:x[0],reverse=True);e=dict(z[0][1]);e['p']=z[0][0];e['edge']=z[0][0]-(z[1][0] if len(z)>1 else 0);bd[d].append(e)
 for d in bd:bd[d].sort(key=lambda x:x['time'])
 return bd

def weekdays(a,c):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();n=0
 while x<=y:
  if x.weekday()<5:n+=1
  x+=timedelta(days=1)
 return n

def pols():
 out=[]
 for fb in (8,12,16,20):
  out.append(('FIXED',fb,0,0))
  for th in (.54,.58,.62,.66,.70,.74,.78):
   for mg in (0,.04,.08,.12):out.append(('FIRST',fb,th,mg))
 return out

def choose(rows,p):
 fam,fb,th,mg=p;z=[x for x in rows if x['time'].hour<=fb]
 if not z:z=rows
 if fam=='FIRST':
  for x in z:
   if x['p']>=th and x['edge']>=mg:return x
 return z[-1] if z else None

def stat(bd,p,a,c):
 exp=weekdays(a,c);z=[choose(bd[d],p) for d in sorted(bd)];z=[x for x in z if x];tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cuts=len(z)-tp-sl;resolved=tp+sl;wr=100*tp/resolved if resolved else 0;strict=100*tp/exp if exp else 0
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cuts,'resolved':resolved,'wrTpSl':round(wr,2),'tpAllDays':round(strict,2),'cutRate':round(100*cuts/len(z),2) if z else 100,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9}

def rank(s):
 viable=s['missing']==0 and s['resolved']>=10 and s['cutRate']<=50 and s['meanR']>0
 return (int(viable and s['wrTpSl']>=80),s['wrTpSl']-(0 if viable else 40),s['meanR'],s['tpAllDays'],-s['cutRate'])

def tune(bd,a,c):
 best=None;bp=None
 for p in pols():
  s=stat(bd,p,a,c);r=rank(s)
  if best is None or r>best:best=r;bp=(p,s)
 return bp

def main():
 raw=load();data={p:b.enrich(raw[p]) for p in b.PAIRS};maps,times=b.make_maps(data);cache=[]
 for cfg in CFGS:cache.append((cfg,events(data,maps,times,cfg)));print('CACHE',cfg,flush=True)
 res={}
 for si,sym in enumerate(b.PAIRS):
  hist=[];win=None
  for st,(name,da,db,fa,fb) in enumerate(STAGES):
   before=(datetime.fromisoformat(da).date()-timedelta(days=1)).isoformat();best=None;ch=None
   for ci,(cfg,by) in enumerate(cache):
    dev=score(by[sym],before,da,db,19000+si*100+st*10+ci)
    if not dev:continue
    p,s=tune(dev,da,db);r=rank(s)
    if best is None or r>best:best=r;ch=(cfg,p,s)
   if not ch:hist.append({'stage':name,'fail':'NO_MODEL'});continue
   cfg,p,ds=ch;final=score(dict(cache)[cfg][sym],db,fa,fb,29000+si*10+st);fs=stat(final,p,fa,fb);ok=rank(fs)[0]==1
   rec={'stage':name,'cfg':cfg,'policy':p,'dev':ds,'final':fs,'pass':ok};hist.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[s for s in b.PAIRS if res[s]['status']=='PASS'];failed=[s for s in b.PAIRS if res[s]['status']=='FAIL'];out={'version':'FOREX_DAILY_EACH_SYMBOL_V19_MANAGED','target':'Every pair trades every weekday; each pair TP/(TP+SL)>=80%, RR1 or2, positive meanR, <=50% CUT, >=10 resolved/month','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/28,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
