#!/usr/bin/env python3
import json,os
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as v

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='AAVE ARB AVAX DOT FLOKI GRASS INJ LDO LINK LIT ONDO POL S SUI TAO WIF WLD XPL'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')
FAMILIES=v.FAMILIES
HOURS=(0,2,4,6,8,10,12,14,16,18,20)
# Broad genuine-H1 management; RR always 1 or 2.
CFGS=[]
for rr in (1.0,2.0):
 for rf in (.75,1.0,1.25,1.5,1.75,2.0,2.5):
  for sw in (4,8,12,18):
   for off,exp in ((0,1),(.25,1),(.50,2),(.75,2)):
    for ca,cr,prog in ((1,.00,.00),(1,-.05,.05),(1,-.15,.10),(2,-.15,.10),(2,-.30,.20),(3,-.40,.25)):
     hold=(30 if rr==1 else 48)
     CFGS.append((rr,rf,sw,hold,off,exp,ca,cr,prog))

def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])

def main():
 doc=json.load(open(v.SNAP));
 if SYM not in doc['data']:raise RuntimeError(SYM+' not H1 covered')
 data={s:v.enrich(doc['data'][s]) for s in v.ALL};mp=v.maps(data);mx=__import__('collections').defaultdict(lambda:__import__('collections').defaultdict(dict));times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  pack=v.context(mp,t)
  if not pack:continue
  elig,reg=pack;q=elig.get(SYM)
  if not q or t.hour not in HOURS:continue
  i,r=q;mx[SYM][t.date().isoformat()][t.hour]=(i,v.meta(r,reg))
 params=[(f,h,c) for f in FAMILIES for h in HOURS for c in CFGS];hist=[];winner=None;print('PARAMS',SYM,len(params),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  if not v.month_full(mx[SYM],da,db) or not v.month_full(mx[SYM],fa,fb):hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
  best=None;bp=None;ds=None
  for p in params:
   s=v.evaluate(SYM,mx[SYM],data,p,da,db);r=rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(SYM,mx[SYM],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',SYM,json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'CRYPTO_H1_REMAINING_V52_RULES','symbol':SYM,'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v52.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
