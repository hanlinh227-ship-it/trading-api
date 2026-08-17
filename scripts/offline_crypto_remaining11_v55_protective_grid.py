#!/usr/bin/env python3
import json,os,statistics
from datetime import datetime,timedelta
from pathlib import Path
import scripts.offline_crypto_remaining13_v54_fresh_h1 as v

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='DOT FLOKI INJ LDO LIT ONDO POL S TAO WLD XPL'.split()
if SYM not in TARGETS: raise RuntimeError('TARGET_SYMBOL invalid')
TARGET=80.0
# Broader, symbol-specific protective grid. Parameters are still selected on prior month only.
RFS=(.50,.75,1.0,1.25,1.5,2.0,2.5,3.0,4.0,5.0,6.0)
SWS=(3,6,12,24,36)
HOURS=(0,2,4,6,8,10,12,14,16,18,20)
FAMILIES=v.FAMILIES
ENTRIES=((0.0,1),(.20,1),(.35,2),(.50,2),(.75,3), (1.0,3))
MGMTS=((1,.15,.00),(1,.10,.05),(1,.05,.10),(1,.00,.15),(1,-.10,.20),(2,.05,.10),(2,-.05,.15),(2,-.20,.25),(3,-.20,.25),(4,-.35,.30))
RRS=(1.0,2.0)

def params():
 for f in FAMILIES:
  for h in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for off,exp in ENTRIES:
       for ca,cr,prog in MGMTS:
        yield(f,h,rr,rf,sw,off,exp,ca,cr,prog)

def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=85 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 65),s['meanR'],s['resolved'],-s['cutRate'])

def main():
 data=v.load();mx=v.matrix(data);ps=list(params());hist=[];win=None;print('SYMBOL',SYM,'PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  if not v.full(mx,da,db) or not v.full(mx,fa,fb):hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
  best=None;bp=None;ds=None
  for n,p in enumerate(ps):
   s=v.evaluate(mx,data,p,da,db);r=rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(mx,data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',SYM,json.dumps(rec),flush=True)
  if ok:win=rec;break
 out={'version':'CRYPTO_REMAINING11_V55_PROTECTIVE','symbol':SYM,'status':'PASS' if win else 'FAIL','frozen':win,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v55.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
