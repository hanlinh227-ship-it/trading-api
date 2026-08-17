#!/usr/bin/env python3
import json,math,os,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
import scripts.offline_forex_eurusd_eurnzd_v28_special as b

PAIR=os.environ.get('TARGET_PAIR','').strip().upper()
if PAIR not in b.PAIRS:raise RuntimeError('TARGET_PAIR invalid')
STAGES=b.STAGES
CFGS=[(1.0,.85,6,30,0,1),(1.0,1.25,12,36,0,1),(1.0,1.75,18,42,.35,2),(2.0,1.0,12,48,0,1),(2.0,1.5,18,54,.35,2)]
HOURS=tuple(range(0,21,2));ENTRY_THS=(.50,.55,.60,.65,.70,.75,.80,.85);EDGES=(0,.03,.06,.10,.14);FALLBACKS=(12,16,20);MGMT_THS=(.15,.25,.35,.45,.55,.65,.75,.85);AGES=(1,2,3,4,6)

def feat(rows,i,side):
 r=rows[i];atr=r['atr'] or 1e-9;h1=1 if r['close']>r['ema20']>r['ema50'] else -1 if r['close']<r['ema20']<r['ema50'] else (1 if r['close']>r['ema20'] else -1);lo=min(x['low'] for x in rows[max(0,i-23):i+1]);hi=max(x['high'] for x in rows[max(0,i-23):i+1]);pos=0 if hi==lo else 2*(r['close']-lo)/(hi-lo)-1
 return [side*h1,side*r['h4'],side*r['ret3']*100,side*r['ret6']*100,side*r['ret12']*100,side*r['ret24']*100,side*r['ret72']*100,side*r['mom6']/3,side*r['mom24']/5,side*r['dev']/3,(r['rsi'] if side==1 else 100-r['rsi'])/100,side*(r['close']-r['open'])/atr,(r['high']-r['low'])/atr,side*pos,r['dt'].weekday()/4,math.sin(2*math.pi*r['dt'].hour/24),math.cos(2*math.pi*r['dt'].hour/24)]
def raw(rows,i,side,cfg):
 rr,rf,sw,hold,off,expiry=cfg;r=rows[i]
 if i+1>=len(rows) or not r.get('atr'):return None
 atr=r['atr'];ei=None;entry=None
 if off==0:ei=i+1;entry=rows[ei]['open']
 else:
  target=r['close']-side*off*atr;last=min(len(rows)-1,i+expiry)
  for j in range(i+1,last+1):
   if rows[j]['low']<=target<=rows[j]['high']:ei=j;entry=target;break
  if ei is None:ei=last;entry=rows[ei]['close']
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if side==1 else swing-entry)+.08*atr);sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold);states=[];best=-9;worst=9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0,'states':states}
  if hs:return {'result':'SL','r':-1.0,'states':states}
  if ht:return {'result':'TP','r':rr,'states':states}
  cur=(x['close']-entry)/risk*side;fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;adv=(x['low']-entry)/risk if side==1 else (entry-x['high'])/risk;best=max(best,fav);worst=min(worst,adv);states.append([(j-ei+1)/48,cur,best,worst,side*(x['close']-(x.get('ema20') or x['close']))/(x.get('atr') or 1),side*(x['close']-(x.get('ema50') or x['close']))/(x.get('atr') or 1),(x.get('rsi') or 50)/100,side*(x.get('mom6') or 0)/3,side*(x.get('mom24') or 0)/5,side*(x.get('h4') or 0)])
 last=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(last-entry)/risk*side)),'states':states}
def events(rows,cfg):
 out=[]
 for i,r in enumerate(rows):
  if r['dt'].hour not in HOURS or r['dt'].weekday()>=5 or r.get('mom24') is None:continue
  for sd in (1,-1):
   o=raw(rows,i,sd,cfg)
   if o:out.append({'day':r['dt'].date().isoformat(),'time':r['dt'],'side':sd,'x':feat(rows,i,sd),**o})
 return out
def model_entry(tr,seed):
 if len(tr)<100:return None
 X=np.asarray([x['x'] for x in tr]);y=np.asarray([1 if x['result']=='TP' else 0 for x in tr])
 if len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=140,max_depth=8,min_samples_leaf=9,max_features=.85,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(X,y);return m
def score(ev,train_end,a,c,seed):
 tr=[x for x in ev if x['day']<=train_end];te=[x for x in ev if a<=x['day']<=c];m=model_entry(tr,seed)
 if m is None or not te:return {}
 pr=m.predict_proba(np.asarray([x['x'] for x in te]))[:,1];g=defaultdict(list)
 for e,p in zip(te,pr):g[(e['day'],e['time'])].append((float(p),e))
 bd=defaultdict(list)
 for (d,t),z in g.items():
  z=sorted(z,key=lambda q:q[0],reverse=True);e=dict(z[0][1]);e['p']=z[0][0];e['edge']=z[0][0]-(z[1][0] if len(z)>1 else 0);bd[d].append(e)
 for d in bd:bd[d].sort(key=lambda x:x['time'])
 return bd
def model_mgmt(ev,train_end,seed):
 X=[];y=[]
 for e in ev:
  if e['day']>train_end:continue
  lab=1 if e['result']=='TP' else 0
  for s in e['states'][:12]:X.append(s);y.append(lab)
 if len(X)<160 or len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=150,max_depth=7,min_samples_leaf=10,max_features=.85,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(np.asarray(X),np.asarray(y));return m
def choose(rows,th,ed,fb):
 z=[x for x in rows if x['time'].hour<=fb]
 if not z:z=rows
 for x in z:
  if x['p']>=th and x['edge']>=ed:return x
 return z[-1] if z else None
def managed(z,mm,mt,age):
 out=[]
 for e in z:
  q=dict(e);cut=None
  for s in e['states']:
   if s[0]*48<age:continue
   p=float(mm.predict_proba(np.asarray([s]))[0,1])
   if p<mt:cut=max(-1,min(2,s[1]));break
  q['mr']='CUT' if cut is not None else e['result'];q['mR']=cut if cut is not None else e['r'];out.append(q)
 return out
def weekdays(a,c):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();n=0
 while x<=y:
  if x.weekday()<5:n+=1
  x+=timedelta(days=1)
 return n
def stat(z,exp):
 tp=sum(x['mr']=='TP' for x in z);sl=sum(x['mr']=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x['mR'] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def main():
 doc=json.load(open(b.SNAP));rows=b.enrich(doc['data'][PAIR]);hist=[];winner=None
 for ci,cfg in enumerate(CFGS):
  ev=events(rows,cfg);print('CFG',cfg,'events',len(ev),flush=True)
  for sti,(name,da,db,fa,fb) in enumerate(STAGES):
   before=(datetime.fromisoformat(da).date()-timedelta(days=1)).isoformat();dev=score(ev,before,da,db,600000+ci*100+sti);mm=model_mgmt(ev,before,610000+ci*100+sti)
   if not dev or mm is None:continue
   best=None;bp=None
   for th in ENTRY_THS:
    for ed in EDGES:
     for fh in FALLBACKS:
      dz=[q for d in sorted(dev) if da<=d<=db for q in [choose(dev[d],th,ed,fh)] if q]
      for mt in MGMT_THS:
       for age in AGES:
        ds=stat(managed(dz,mm,mt,age),weekdays(da,db));r=rank(ds)
        if best is None or r>best:best=r;bp=(th,ed,fh,mt,age,ds)
   th,ed,fh,mt,age,ds=bp;final=score(ev,db,fa,fb,620000+ci*100+sti);mf=model_mgmt(ev,db,630000+ci*100+sti)
   if not final or mf is None:continue
   fz=[q for d in sorted(final) if fa<=d<=fb for q in [choose(final[d],th,ed,fh)] if q];fs=stat(managed(fz,mf,mt,age),weekdays(fa,fb));ok=rank(fs)[0]==1;rec={'cfg':cfg,'stage':name,'entryThreshold':th,'edge':ed,'fallbackHour':fh,'mgmtThreshold':mt,'minReviewH':age,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',PAIR,json.dumps(rec),flush=True)
   if ok:winner=rec;break
  if winner:break
 out={'version':'FOREX_EURUSD_EURNZD_V30_MGMTML','pair':PAIR,'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/forex_{PAIR.lower()}_v30.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
