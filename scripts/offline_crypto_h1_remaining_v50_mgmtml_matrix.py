#!/usr/bin/env python3
import json,math,os,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from scripts.offline_crypto_v28_separate import PROFILE
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h

SNAP='data/provider_snapshots/crypto_h1_apr_jul_2026.json'
SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='AAVE ALGO ARB AVAX DOT FIL FLOKI GRASS INJ JUP LDO LINK LIT MOODENG NEAR ONDO POL S SUI TAO TON WIF WLD XPL'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')
if SYM in ('TON','IP'):raise RuntimeError('TON/IP have no verified H1 snapshot; use 4H branch')
STAGES=[('APR_MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('MAY_JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUN_JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
# rr, risk floor ATR, swing H1, hold H1, limit offset ATR (0=market), expiry
CFGS=[(1.0,.75,6,24,0,1),(1.0,1.0,12,30,0,1),(1.0,1.25,12,36,.35,2),(1.0,1.5,18,42,.50,2),(2.0,1.0,12,42,0,1),(2.0,1.5,18,54,.35,2)]
ENTRY_THS=(.52,.56,.60,.64,.68,.72,.76,.80,.84)
EDGES=(0,.03,.06,.10,.14);FALLBACKS=(12,16,20)
MGMT_THS=(.15,.25,.35,.45,.55,.65,.75,.85);MIN_AGES=(1,2,3,4)
SCAN_HOURS=tuple(range(0,21,2))

def load():
 doc=json.load(open(SNAP));covered=doc['data']
 if SYM not in covered:raise RuntimeError(SYM+' not H1 covered')
 return {s:h.enrich(covered[s]) for s in covered}
def ctx(mp,t):
 elig={s:q for s,m in mp.items() if (q:=m.get(t)) and q[1].get('ret24') is not None and q[1].get('ema50') is not None}
 if len(elig)<20:return None
 rets=[q[1]['ret24'] for q in elig.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);btc=elig.get('BTC');btc24=btc[1]['ret24'] if btc else med;btc72=btc[1]['ret72'] if btc else 0
 fam=PROFILE.get(SYM,'OTHER');fr=[q[1]['ret24'] for s,q in elig.items() if PROFILE.get(s,'OTHER')==fam]
 fammed=statistics.median(fr) if fr else med;famb=sum(x>0 for x in fr)/len(fr) if fr else breadth
 return elig,{'breadth':breadth,'median':med,'btc24':btc24,'btc72':btc72,'family':fam,'familyMedian':fammed,'familyBreadth':famb}
def feat(row,reg,side):
 h1=1 if row['close']>row['ema20']>row['ema50'] else -1 if row['close']<row['ema20']<row['ema50'] else (1 if row['close']>row['ema20'] else -1)
 ar=(row['rsi'] or 50) if side==1 else 100-(row['rsi'] or 50);ba=reg['breadth'] if side==1 else 1-reg['breadth'];fb=reg['familyBreadth'] if side==1 else 1-reg['familyBreadth'];relbtc=side*(row['ret24']-reg['btc24']);relfam=side*(row['ret24']-reg['familyMedian'])
 return [side*h1,side*row['h4'],side*row['d1'],(row['adx'] or 0)/50,ar/100,side*row['mom6']/4,side*row['dev']/3,ba,fb,side*reg['btc24']*20,side*reg['btc72']*10,relbtc*20,relfam*20,side*reg['familyMedian']*20,row['dt'].weekday()/6,math.sin(2*math.pi*row['dt'].hour/24),math.cos(2*math.pi*row['dt'].hour/24)]
def rawtrade(rows,i,side,cfg,static):
 rr,rf,sw,hold,off,expiry=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];ei=None;entry=None
 if off==0:ei=i+1;entry=rows[ei]['open']
 else:
  target=sig['close']-side*off*atr;last=min(len(rows)-1,i+expiry)
  for j in range(i+1,last+1):
   if rows[j]['low']<=target<=rows[j]['high']:ei=j;entry=target;break
  if ei is None:ei=last;entry=rows[ei]['close']
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if side==1 else swing-entry)+.08*atr)
 if risk<=0:return None
 sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold);states=[];best=-9;worst=9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0,'states':states}
  if hs:return {'result':'SL','r':-1.0,'states':states}
  if ht:return {'result':'TP','r':rr,'states':states}
  fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;adv=(x['low']-entry)/risk if side==1 else (entry-x['high'])/risk;best=max(best,fav);worst=min(worst,adv);cur=(x['close']-entry)/risk*side
  states.append([ (j-ei+1)/48,cur,best,worst,side*(x['close']-(x.get('ema20') or x['close']))/(x.get('atr') or 1),side*(x['close']-(x.get('ema50') or x['close']))/(x.get('atr') or 1),(x.get('rsi') or 50)/100,(x.get('adx') or 0)/50,side*(x.get('mom6') or 0)/4,static[0],static[1],static[2],static[3] ])
 last=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(last-entry)/risk*side)),'states':states}
def build(data,cfg):
 mp=h.maps(data);ev=[];times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<'2026-04-01' or d>'2026-07-31' or t.hour not in SCAN_HOURS:continue
  pack=ctx(mp,t)
  if not pack:continue
  elig,reg=pack;q=elig.get(SYM)
  if not q:continue
  i,r=q;static=(reg['breadth'],reg['familyBreadth'],reg['btc24']*20,(r['ret24']-reg['familyMedian'])*20)
  for side in (1,-1):
   o=rawtrade(data[SYM],i,side,cfg,static)
   if o:ev.append({'day':d,'time':t,'side':side,'x':feat(r,reg,side),**o})
 return ev
def emodel(rows,seed):
 if len(rows)<100:return None
 X=np.asarray([x['x'] for x in rows]);y=np.asarray([1 if x['result']=='TP' else 0 for x in rows])
 if len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=140,max_depth=8,min_samples_leaf=9,max_features=.8,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(X,y);return m
def score(ev,train_end,a,c,seed):
 tr=[x for x in ev if x['day']<=train_end];te=[x for x in ev if a<=x['day']<=c];m=emodel(tr,seed)
 if m is None or not te:return {}
 pr=m.predict_proba(np.asarray([x['x'] for x in te]))[:,1];g=defaultdict(list)
 for e,p in zip(te,pr):g[(e['day'],e['time'])].append((float(p),e))
 bd=defaultdict(list)
 for (d,t),z in g.items():
  z=sorted(z,key=lambda q:q[0],reverse=True);e=dict(z[0][1]);e['p']=z[0][0];e['edge']=z[0][0]-(z[1][0] if len(z)>1 else 0);bd[d].append(e)
 for d in bd:bd[d].sort(key=lambda x:x['time'])
 return bd
def mmodel(ev,train_end,seed):
 X=[];y=[]
 for e in ev:
  if e['day']>train_end:continue
  lab=1 if e['result']=='TP' else 0
  for s in e['states'][:12]:X.append(s);y.append(lab)
 if len(X)<180 or len(set(y))<2:return None
 m=ExtraTreesClassifier(n_estimators=140,max_depth=7,min_samples_leaf=12,max_features=.8,class_weight='balanced',n_jobs=-1,random_state=seed);m.fit(np.asarray(X),np.asarray(y));return m
def choose(rows,th,edge,fb):
 z=[x for x in rows if x['time'].hour<=fb]
 if not z:z=rows
 for x in z:
  if x['p']>=th and x['edge']>=edge:return x
 return z[-1] if z else None
def managed(trades,mm,mt,age):
 out=[]
 for e in trades:
  q=dict(e);cut=None
  for s in e['states']:
   if s[0]*48<age:continue
   p=float(mm.predict_proba(np.asarray([s]))[0,1])
   if p<mt:cut=max(-1,min(2,s[1]));break
  q['managedResult']='CUT' if cut is not None else e['result'];q['managedR']=cut if cut is not None else e['r'];out.append(q)
 return out
def days(a,c):return (datetime.fromisoformat(c).date()-datetime.fromisoformat(a).date()).days+1
def full(bd,a,c):return len([d for d in bd if a<=d<=c])==days(a,c)
def stat(z,exp):
 tp=sum(x['managedResult']=='TP' for x in z);sl=sum(x['managedResult']=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x['managedR'] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def tune(bd,mm,a,c):
 best=None;bp=None;exp=days(a,c)
 for th in ENTRY_THS:
  for ed in EDGES:
   for fb in FALLBACKS:
    tr=[q for d in sorted(bd) if a<=d<=c for q in [choose(bd[d],th,ed,fb)] if q]
    for mt in MGMT_THS:
     for ma in MIN_AGES:
      s=stat(managed(tr,mm,mt,ma),exp);r=rank(s)
      if best is None or r>best:best=r;bp=(th,ed,fb,mt,ma,s)
 return bp
def main():
 data=load();hist=[];winner=None
 for ci,cfg in enumerate(CFGS):
  ev=build(data,cfg);print('CFG',cfg,'EVENTS',len(ev),flush=True)
  for sti,(name,da,db,fa,fb) in enumerate(STAGES):
   before=(datetime.fromisoformat(da).date()-timedelta(days=1)).isoformat();dev=score(ev,before,da,db,500000+ci*100+sti);mm=mmodel(ev,before,510000+ci*100+sti)
   if not dev or mm is None or not full(dev,da,db):continue
   p=tune(dev,mm,da,db)
   if not p:continue
   th,ed,fh,mt,ma,ds=p;final=score(ev,db,fa,fb,520000+ci*100+sti);mf=mmodel(ev,db,530000+ci*100+sti)
   if not final or mf is None:continue
   z=[q for d in sorted(final) if fa<=d<=fb for q in [choose(final[d],th,ed,fh)] if q];fs=stat(managed(z,mf,mt,ma),days(fa,fb));ok=rank(fs)[0]==1;rec={'cfg':cfg,'stage':name,'entryThreshold':th,'edge':ed,'fallbackHour':fh,'mgmtThreshold':mt,'minReviewH':ma,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',json.dumps(rec),flush=True)
   if ok:winner=rec;break
  if winner:break
 out={'version':'CRYPTO_H1_REMAINING_V50_MGMTML','symbol':SYM,'family':PROFILE.get(SYM),'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v50.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
