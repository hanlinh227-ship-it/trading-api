#!/usr/bin/env python3
import json,os,statistics
from datetime import datetime
from pathlib import Path
import scripts.offline_crypto_remaining13_v54_fresh_h1 as v

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='DOT FLOKI INJ LDO ONDO POL TAO WLD'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')
TARGET=80.0
FAMS=('OWN_H1','OWN_H4','BTC','ETH','SOL','RELBTC','RELETH','MOM','MEANREV','HYBRID')
HRS=(0,2,4,6,8,10,12,14,16,18,20)
RFS=(.75,1.0,1.25,1.5,2.0,2.5,3.0,4.0,5.0)
SWS=(3,6,12,24)
ENT=((0.0,1),(.25,1),(.50,2),(.75,3),(1.0,3))
# Aggressive management is legitimate under user's CUT-separate convention; economics remains mandatory.
MG=((1,.20,.00),(1,.15,.05),(1,.10,.10),(1,.05,.15),(1,.00,.20),(1,-.10,.25),(2,.10,.10),(2,.00,.20),(2,-.15,.30),(3,-.25,.35))

def params():
 for f in FAMS:
  for h in HRS:
   for rf in RFS:
    for sw in SWS:
     for off,exp in ENT:
      for ca,cr,prog in MG:
       yield(f,h,1.0,rf,sw,off,exp,ca,cr,prog)
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 70),s['meanR'],s['resolved'],-s['cutRate'])
def main():
 data=v.load();mx=v.matrix(data);ps=list(params());hist=[];win=None;print('V60',SYM,'PARAMS',len(ps),flush=True)
 # Stage 1 Jan -> Feb; if fail, Stage 2 Feb -> Mar. This is sequential and uses no future month in parameter selection.
 for name,da,db,fa,fb in v.STAGES:
  if not v.full(mx,da,db) or not v.full(mx,fa,fb):hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
  best=None;bp=None;ds=None
  for p in ps:
   s=v.evaluate(mx,data,p,da,db);r=rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evaluate(mx,data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',SYM,json.dumps(rec),flush=True)
  if ok:win=rec;break
 out={'version':'CRYPTO_V60_USERCRITERIA_REMAINING','symbol':SYM,'criteria':'daily coverage; TP/(TP+SL)>=80; RR1; >=5 resolved; meanR incl CUT>0; CUT reported separately with no artificial cap','status':'PASS' if win else 'FAIL','frozen':win,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v60.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
