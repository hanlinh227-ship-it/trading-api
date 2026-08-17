#!/usr/bin/env python3
import json,os
from pathlib import Path
import scripts.offline_forex_eurusd_eurnzd_v28_special as v

PAIR=os.environ.get('TARGET_PAIR','').strip().upper()
if PAIR not in v.PAIRS:raise RuntimeError('TARGET_PAIR must be EURUSD/EURNZD')

def compact():
 for f in v.FAMILIES:
  for h in (4,8,12,16,20):
   for rr in (1.0,2.0):
    for rf in (1.0,1.5,2.0,2.5,3.0):
     for sw in (6,18,30):
      for em,off,exp in (('MARKET',0,1),('HYBRID',.35,2),('HYBRID',.70,3)):
       for ca,cr,prog in ((1,.0,0),(1,-.1,.05),(2,-.2,.1),(3,-.35,.2),(4,-.5,.25)):
        yield(f,h,rr,rf,sw,em,off,exp,ca,cr,prog)

def main():
 doc=json.load(open(v.SNAP));rows=v.enrich(doc['data'][PAIR]);ps=list(compact());hist=[];winner=None;print('FAST',PAIR,'PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  best=None;bp=None;ds=None
  for p in ps:
   s=v.evaluate(rows,p,da,db);r=v.rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(rows,bp,fa,fb);ok=v.rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',PAIR,json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'FOREX_EURUSD_EURNZD_V29_FAST','pair':PAIR,'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/forex_{PAIR.lower()}_v29.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
