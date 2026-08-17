#!/usr/bin/env python3
import json
from pathlib import Path
import scripts.offline_forex_eurusd_eurnzd_v28_special as v
PAIR='EURUSD';OUT='data/offline_forex_eurusd_v32_protective_dev.json'

def params():
 for f in v.FAMILIES:
  for h in (4,8,12,16,20):
   for rr in (1.0,2.0):
    for rf in (2.0,2.5,3.0,3.5,4.0,5.0):
     for sw in (12,24,36):
      for em,off,exp in (('MARKET',0,1),('HYBRID',.35,2),('HYBRID',.70,3)):
       for ca,cr,prog in ((1,.10,.00),(1,.05,.05),(1,.00,.10),(1,-.10,.15),(2,.00,.15),(2,-.15,.20),(3,-.25,.25)):
        yield(f,h,rr,rf,sw,em,off,exp,ca,cr,prog)
def devscore(stats):
 # Development objective across all 4 month-to-month tests; do not claim blind.
 viable=[s for s in stats if s['missing']==0 and s['resolved']>=4 and s['meanR']>0]
 if not viable:return (-999,)
 hit=sum(s['wr']>=80 for s in viable);avg=sum(s['wr'] for s in viable)/len(viable);mn=min(s['wr'] for s in viable);er=sum(s['meanR'] for s in viable)/len(viable)
 return (hit,mn,avg,er,-sum(s['cutRate'] for s in viable)/len(viable))
def main():
 doc=json.load(open(v.SNAP));rows=v.enrich(doc['data'][PAIR]);best=None;bp=None;bmonths=None;tested=0
 for p in params():
  stats=[]
  # Evaluate candidate on March-June month blocks; this is development only, all already exposed.
  for _,da,db,fa,fb in v.STAGES:
   stats.append(v.evaluate(rows,p,fa,fb))
  q=devscore(stats);tested+=1
  if best is None or q>best:best=q;bp=p;bmonths=stats;print('BEST',tested,q,p,stats,flush=True)
 out={'version':'FOREX_EURUSD_V32_PROTECTIVE_DEV','status':'CANDIDATE_LOCK_READY' if best and best[0]>=2 else 'WEAK','developmentOnly':True,'tested':tested,'params':bp,'monthStats':bmonths,'quality':best};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
