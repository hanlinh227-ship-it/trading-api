#!/usr/bin/env python3
import json,math,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
import scripts.offline_crypto_precision_evolver_v36 as b
import scripts.offline_crypto_precision_evolver_v36b as fixed
b.regime_at=fixed.fixed_regime_at
MAIN='data/provider_snapshots/crypto_4h_feb_jul_2026.json';BUF='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json';OUT='data/offline_crypto_daily_each_symbol_v42_mgmtml.json';TARGET=80.0
STAGES=[('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
EXECS=[(1.0,.65,5,6),(1.0,.85,8,9),(2.0,.65,5,9)]
ENTRY_THS=(.52,.56,.60,.64,.68,.72,.76);ENTRY_MGS=(0,.04,.08,.12,.16);FALLBACKS=(8,12,16,20);MGMT_THS=(.20,.30,.40,.50,.60,.70);MIN_AGES=(1,2,3)

def load():
 a=json.load(open(MAIN));z=json.load(open(BUF));out={}
 for s in b.SYMBOLS:
  d={x[0]:x for x in a['data'][s]};d.update({x[0]:x for x in z['data'][s]});out[s]=[d[k] for k in sorted(d)]
 return out

def execraw(rows,i,side,cfg):
 rr,rf,sw,hold=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr)
 if risk<=0:return None
 sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold);states=[];best=-9;worst=9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0,'states':states}
  if hs:return {'result':'SL','r':-1.0,'states':states}
  if ht:return {'result':'TP','r':rr,'states':states}
  fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;adv=(x['low']-entry)/risk if side==1 else (entry-x['high'])/risk;best=max(best,fav);worst=min(worst,adv);cur=(x['close']-entry)/risk*side;em20=(x['close']-x['ema20'])/x['atr']*side if x.get('ema20') is not None and x.get('atr') else 0;em50=(x['close']-x['ema50'])/x['atr']*side if x.get('ema50') is not None and x.get('atr') else 0
  states.append({'age':j-ei+1,'r':cur,'best':best,'worst':worst,'ema20':em20,'ema50':em50,'rsi':(x.get('rsi') or 50)/100,'adx':(x.get('adx') or 0)/50,'mom':side*(x.get('mom24atr') or 0)/4,'d1':side*(x.get('d1') or 0)})
 last=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(last-entry)/risk*side)),'states':states}

def entryextra(rows,i,side):
 r=rows[i];atr=r['atr'] or 1e-9;lo=min(x['low'] for x in rows[max(0,i-5):i+1]);hi=max(x['high'] for x in rows[max(0,i-5):i+1]);pos=0 if hi==lo else 2*(r['close']-lo)/(hi-lo)-1
 return [side*(r['close']-r['open'])/atr,(r['high']-r['low'])/atr,side*pos,r['dt'].weekday()/6,math.sin(2*math.pi*r['dt'].hour/24),math.cos(2*math.pi*r['dt'].hour/24)]

def build(data,mp,cfg):
 out=defaultdict(list);times=sorted(set().union(*(set(x) for x in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<'2026-02-10' or d>'2026-07-31':continue
  pack=b.regime_at(mp,t)
  if not pack:continue
  eligible,reg=pack
  for sym,q in eligible.items():
   i,r=q
   for side in (1,-1):
    f,_=b.features(sym,r,reg,side);o=execraw(data[sym],i,side,cfg)
    if o:out[sym].append({'day':d,'time':t,'side':side,'x':f+entryextra(data[sym],i,side),**o})
 return out

def emodel(rows,seed):
 if len(rows)<90:return None
 X=np.asarray([x['x'] for x in rows]);y=np.asarray([1 if x['result']=='TP' else 0 for x in rows])
 if len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=100,max_depth=8,min_samples_leaf=9,max_features=.8,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(X,y);return m

def score_entries(ev,train_end,a,c,seed):
 tr=[x for x in ev if x['day']<=train_end];te=[x for x in ev if a<=x['day']<=c];m=emodel(tr,seed)
 if m is None or not te:return {}
 pr=m.predict_proba(np.asarray([x['x'] for x in te]))[:,1];g=defaultdict(list)
 for e,p in zip(te,pr):g[(e['day'],e['time'])].append((float(p),e))
 bd=defaultdict(list)
 for (d,t),z in g.items():
  z=sorted(z,key=lambda q:q[0],reverse=True);e=dict(z[0][1]);e['p']=z[0][0];e['edge']=z[0][0]-(z[1][0] if len(z)>1 else 0);bd[d].append(e)
 for d in bd:bd[d].sort(key=lambda x:x['time'])
 return bd

def days(a,c):return (datetime.fromisoformat(c).date()-datetime.fromisoformat(a).date()).days+1

def entry_pols():
 out=[]
 for fb in FALLBACKS:
  out.append(('FIXED',fb,0,0))
  for th in ENTRY_THS:
   for mg in ENTRY_MGS:out.append(('FIRST',fb,th,mg))
 return out

def choose(rows,p):
 fam,fb,th,mg=p;z=[x for x in rows if x['time'].hour<=fb]
 if not z:z=rows
 if fam=='FIRST':
  for x in z:
   if x['p']>=th and x['edge']>=mg:return x
 return z[-1] if z else None

def select(bd,p):return [q for q in (choose(bd[d],p) for d in sorted(bd)) if q]

def statevec(s):return [s['age']/12,s['r'],s['best'],s['worst'],s['ema20'],s['ema50'],s['rsi'],s['adx'],s['mom'],s['d1']]

def mmodel(ev,train_end,seed):
 X=[];y=[]
 for e in ev:
  if e['day']>train_end:continue
  label=1 if e['result']=='TP' else 0
  for s in e['states'][:4]:X.append(statevec(s));y.append(label)
 if len(X)<120 or len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=120,max_depth=7,min_samples_leaf=10,max_features=.85,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(np.asarray(X),np.asarray(y));return m

def managed(trades,mm,th,min_age):
 out=[]
 for e in trades:
  q=dict(e);cut=None
  for s in e['states']:
   if s['age']<min_age:continue
   p=float(mm.predict_proba(np.asarray([statevec(s)]))[0,1])
   if p<th:cut=max(-1,min(2,s['r']));break
  if cut is not None:q['managedResult']='CUT';q['managedR']=cut
  else:q['managedResult']=e['result'];q['managedR']=e['r']
  out.append(q)
 return out

def stat(z,exp):
 tp=sum(x['managedResult']=='TP' for x in z);sl=sum(x['managedResult']=='SL' for x in z);cuts=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cuts,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cuts/len(z),2) if z else 100,'meanR':round(statistics.mean(x['managedR'] for x in z),3) if z else -9}

def rank(s):
 ok=s['missing']==0 and s['resolved']>=12 and s['cutRate']<=50 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],-s['cutRate'],s['resolved'])

def tune(devbd,ev,train_end,a,c,seed):
 mm=mmodel(ev,train_end,seed)
 if mm is None:return None
 best=None;bp=None;exp=days(a,c)
 for ep in entry_pols():
  tr=select(devbd,ep)
  for mt in MGMT_THS:
   for ma in MIN_AGES:
    s=stat(managed(tr,mm,mt,ma),exp);r=rank(s)
    if best is None or r>best:best=r;bp=(ep,mt,ma,s)
 return bp

def main():
 raw=load();data={s:b.enrich(raw[s]) for s in b.SYMBOLS};mp=b.maps(data);cache=[]
 for cfg in EXECS:cache.append((cfg,build(data,mp,cfg)));print('CACHE',cfg,flush=True)
 res={}
 for si,sym in enumerate(b.SYMBOLS):
  hist=[];win=None
  for st,(name,da,db,fa,fb) in enumerate(STAGES):
   before=(datetime.fromisoformat(da).date()-timedelta(days=1)).isoformat();best=None;choice=None
   for ci,(cfg,by) in enumerate(cache):
    ev=by.get(sym,[]);devbd=score_entries(ev,before,da,db,62000+si*100+st*10+ci)
    if not devbd:continue
    p=tune(devbd,ev,before,da,db,72000+si*100+st*10+ci)
    if not p:continue
    ep,mt,ma,ds=p;r=rank(ds)
    if best is None or r>best:best=r;choice=(cfg,ep,mt,ma,ds)
   if not choice:hist.append({'stage':name,'fail':'NO_MODEL'});continue
   cfg,ep,mt,ma,ds=choice;ev=dict(cache)[cfg].get(sym,[]);finalbd=score_entries(ev,db,fa,fb,82000+si*10+st);mm=mmodel(ev,db,92000+si*10+st);fz=managed(select(finalbd,ep),mm,mt,ma);fs=stat(fz,days(fa,fb));ok=rank(fs)[0]==1
   rec={'stage':name,'cfg':cfg,'entryPolicy':ep,'mgmtThreshold':mt,'minReviewAge4H':ma,'dev':ds,'final':fs,'pass':ok};hist.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[s for s in b.SYMBOLS if res[s]['status']=='PASS'];failed=[s for s in b.SYMBOLS if res[s]['status']=='FAIL'];out={'version':'CRYPTO_DAILY_EACH_SYMBOL_V42_MGMTML','target':'1 trade each calendar day per coin; per-coin TP/(TP+SL)>=80; RR1 or2; CUT<=50%; >=12 resolved; positive expectancy','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/61,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
