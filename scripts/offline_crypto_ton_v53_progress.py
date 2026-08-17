#!/usr/bin/env python3
import json,statistics
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_daily_each_symbol_v46_rulefamilies as v

SYM='TON';OUT='data/offline_crypto_ton_v53_progress.json';TARGET=80.0
FAMILIES=('BTCALIGN','RELATIVE','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID');HOURS=(0,4,8,12,16,20)
# rr, risk floor, swing bars, hold bars, review age, current R floor, required favorable progress
CFGS=[]
for rr in (1.0,2.0):
 for rf in (1.25,1.5,1.75,2.0,2.5,3.0,3.5):
  for sw in (3,5,8,12):
   for age,cr,prog in ((1,.05,.00),(1,.00,.05),(1,-.10,.10),(1,-.20,.20),(2,-.10,.15),(2,-.25,.25),(3,-.35,.30)):
    CFGS.append((rr,rf,sw,12 if rr==1 else 18,age,cr,prog))

def raw(rows,i,sd,cfg):
 rr,rf,sw,hold,age0,cr,prog=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if sd==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if sd==1 else swing-entry)+.08*atr)
 if risk<=0:return None
 sl=entry-sd*risk;tp=entry+sd*rr*risk;end=min(len(rows),ei+hold);best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if sd==1 else x['high']>=sl;ht=x['high']>=tp if sd==1 else x['low']<=tp
  if hs and ht:return ('SL',-1.0)
  if hs:return ('SL',-1.0)
  if ht:return ('TP',rr)
  age=j-ei+1;cur=(x['close']-entry)/risk*sd;fav=(x['high']-entry)/risk if sd==1 else (entry-x['low'])/risk;best=max(best,fav)
  if age>=age0:
   em20=x.get('ema20');em50=x.get('ema50');broken20=em20 is not None and (x['close']-em20)*sd<0;broken50=em50 is not None and (x['close']-em50)*sd<0
   if cur<=cr or best<prog or (broken20 and cur<.10) or (broken50 and cur<.20):return ('CUT',max(-1,cur))
 last=rows[end-1]['close'];return ('CUT',max(-1,min(rr,(last-entry)/risk*sd)))
def evalp(ds,data,p,a,c):
 fam,h,cfg=p;exp=v.days(a,c);z=[]
 for d in sorted(k for k in ds if a<=k<=c):
  hs=ds[d];hh=h if h in hs else max([x for x in hs if x<=h],default=max(hs));i,m=hs[hh];o=raw(data[SYM],i,v.side(fam,m),cfg)
  if o:z.append(o)
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def main():
 rawd=v.load();data={s:v.b.enrich(rawd[s]) for s in v.b.SYMBOLS};mp=v.b.maps(data);mx=v.matrix(data,mp);params=[(f,h,c) for f in FAMILIES for h in HOURS for c in CFGS];hist=[];winner=None;print('TON PARAMS',len(params),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  best=None;bp=None;ds=None
  for p in params:
   s=evalp(mx[SYM],data,p,da,db);r=rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=evalp(mx[SYM],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TON',name,json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'CRYPTO_TON_V53_PROGRESS','status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
