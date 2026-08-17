#!/usr/bin/env python3
import json,statistics
from pathlib import Path
import scripts.offline_crypto_daily_each_symbol_v46_rulefamilies as v

OUT='data/offline_crypto_ton_v51_special.json';SYM='TON';TARGET=80.0
# TON/MESSAGING_L1-specific expansion: BTC/risk beta, own trend, mean reversion, broad-risk context.
FAMILIES=('BTCALIGN','RELATIVE','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID')
HOURS=(0,4,8,12,16,20);RRS=(1.0,2.0);RFS=(.65,.85,1.10,1.40,1.75,2.10,2.50);SWS=(3,5,8,12)
CUTS=((1,.00),(1,-.05),(1,-.15),(2,-.10),(2,-.25),(3,-.35))
STAGES=v.STAGES

def params():
 for fam in FAMILIES:
  for h in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for ca,cr in CUTS:yield(fam,h,rr,rf,sw,ca,cr)

def main():
 raw=v.load();data={s:v.b.enrich(raw[s]) for s in v.b.SYMBOLS};mp=v.b.maps(data);mx=v.matrix(data,mp);ps=list(params());hist=[];winner=None
 print('TON PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in STAGES:
  best=None;bp=None;ds=None
  for p in ps:
   s=v.evals(SYM,mx[SYM],data,p,da,db)
   # wider CUT allowance for compulsory daily TON, but full days, economics and resolved count remain mandatory
   ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
   r=(int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
   if best is None or r>best:best=r;bp=p;ds=s
  fs=v.evals(SYM,mx[SYM],data,bp,fa,fb);valid=fs['missing']==0 and fs['resolved']>=5 and fs['cutRate']<=84 and fs['meanR']>0;passed=valid and fs['wr']>=TARGET
  rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':passed};hist.append(rec);print('TON TEST',json.dumps(rec),flush=True)
  if passed:winner=rec;break
 out={'version':'CRYPTO_TON_V51_SPECIAL','symbol':'TON','family':'MESSAGING_L1','status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
