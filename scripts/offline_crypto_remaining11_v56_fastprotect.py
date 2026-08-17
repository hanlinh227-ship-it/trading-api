#!/usr/bin/env python3
import json,os
from pathlib import Path
import scripts.offline_crypto_remaining13_v54_fresh_h1 as v

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='DOT FLOKI INJ LDO LIT ONDO POL S TAO WLD XPL'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')
TARGET=80.0
# Compact, targeted H+1 protective search.
FAMS=('OWN_H1','OWN_H4','BTC','ETH','RELBTC','RELETH','MOM','MEANREV','HYBRID')
HRS=(4,8,12,16,20)
RFS=(.75,1.0,1.25,1.5,2.0,2.5,3.0)
SWS=(3,6,12)
ENT=((0.0,1),(.25,1),(.50,2),(.75,2))
MG=((1,.15,.00),(1,.10,.05),(1,.05,.10),(1,.00,.15),(1,-.10,.20),(2,.00,.10),(2,-.15,.20))

def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=85 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 65),s['meanR'],s['resolved'],-s['cutRate'])
def params():
 for f in FAMS:
  for h in HRS:
   for rf in RFS:
    for sw in SWS:
     for off,exp in ENT:
      for ca,cr,prog in MG:
       yield(f,h,1.0,rf,sw,off,exp,ca,cr,prog)
def main():
 data=v.load();mx=v.matrix(data);ps=list(params());hist=[];winner=None;print('FASTPROTECT',SYM,'PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in v.STAGES:
  if not v.full(mx,da,db) or not v.full(mx,fa,fb):hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
  best=None;bp=None;ds=None
  for p in ps:
   s=v.evaluate(mx,data,p,da,db);r=rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(mx,data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',SYM,json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'CRYPTO_REMAINING11_V56_FASTPROTECT','symbol':SYM,'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v56.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
