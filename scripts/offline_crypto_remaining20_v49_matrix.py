#!/usr/bin/env python3
import json,os
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_daily_each_symbol_v48_2025_remaining as v
import scripts.offline_crypto_precision_evolver_v36 as b

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='AAVE ALGO ARB AVAX DOT FIL FLOKI INJ JUP LDO LINK MOODENG NEAR ONDO POL S SUI WIF WLD XPL'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')

def compact_params():
 for fam in v.FAMILIES:
  for h in v.HOURS:
   for rr in (1.0,2.0):
    for rf in (.85,1.25,1.75,2.25):
     for sw in (5,10):
      for em,off in (('MARKET',0.0),('HYBRID',.35),('HYBRID',.70)):
       for ca,cr,prog in ((1,-.05,.00),(1,-.15,.05),(2,-.25,.10),(2,-.40,.20)):
        yield(fam,h,rr,rf,sw,em,off,ca,cr,prog)

def main():
 doc=json.load(open(v.SNAP));covered=set(doc['data'])
 if SYM not in covered:raise RuntimeError(SYM+' not in 2025 snapshot')
 data={s:b.enrich(doc['data'][s]) for s in covered};mp=b.maps(data);mx=defaultdict(lambda:defaultdict(dict));times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  pack=v.context(mp,t,covered)
  if not pack:continue
  elig,reg=pack
  if SYM in elig and t.hour in v.HOURS:
   i,r=elig[SYM];mx[SYM][t.date().isoformat()][t.hour]=(i,v.meta(r,reg))
 ps=list(compact_params());hist=[];winner=None;print('SYMBOL',SYM,'PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  if not v.full(mx[SYM],da,db) or not v.full(mx[SYM],fa,fb):
   hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
  best=None;bp=None;ds=None
  for p in ps:
   s=v.evaluate(SYM,mx[SYM],data,p,da,db);r=v.rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(SYM,mx[SYM],data,bp,fa,fb);ok=v.rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',SYM,name,json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'CRYPTO_REMAINING20_V49_MATRIX','symbol':SYM,'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v49.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
