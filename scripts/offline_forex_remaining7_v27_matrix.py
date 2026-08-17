#!/usr/bin/env python3
import json,os
from pathlib import Path
import scripts.offline_forex_daily_each_symbol_v26_2025_walkforward as v

PAIR=os.environ.get('TARGET_PAIR','').strip().upper()
REMAINING=['EURUSD','EURNZD','GBPJPY','GBPCAD','AUDNZD','AUDCHF','CADJPY']
if PAIR not in REMAINING:raise RuntimeError('TARGET_PAIR must be one remaining pair')

# Targeted but predeclared compact family grid, independent of holdout outcomes.
def compact_params():
 for fam in v.FAMILIES:
  for h in v.HOURS:
   for rr in (1.0,2.0):
    for rf in (.85,1.25,1.75,2.25):
     for sw in (6,18):
      for em,off,exp in (('MARKET',0.0,1),('HYBRID',.35,2),('HYBRID',.70,3)):
       for ca,cr,prog in ((1,-.05,.00),(1,-.15,.05),(2,-.25,.10),(3,-.40,.20)):
        yield(fam,h,rr,rf,sw,em,off,exp,ca,cr,prog)

def main():
 data=v.load_data();mp,times=v.make_maps(data);mx=v.matrix(data,mp,times);ps=list(compact_params());hist=[];winner=None
 print('PAIR',PAIR,'PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  best=None;bp=None;ds=None
  for p in ps:
   s=v.evaluate(PAIR,mx[PAIR],data,p,da,db);r=v.rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(PAIR,mx[PAIR],data,bp,fa,fb);ok=v.rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',PAIR,name,json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'FOREX_REMAINING7_V27_MATRIX','pair':PAIR,'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};path=f'data/remaining/forex_{PAIR.lower()}_v27.json';Path(path).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(path,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
