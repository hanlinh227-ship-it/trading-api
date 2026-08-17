#!/usr/bin/env python3
import json,os,statistics
from datetime import datetime
from pathlib import Path
import scripts.offline_crypto_remaining13_v54_fresh_h1 as v

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='DOT FLOKI INJ LDO ONDO POL TAO WLD'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')
FAMS=('OWN_H1','OWN_H4','BTC','ETH','RELBTC','RELETH','MOM','MEANREV','HYBRID')
HRS=(4,8,12,16,20);RFS=(1.25,1.75,2.5,3.5);SWS=(6,12);ENTS=((0.0,1),(.5,2))
# Protective H+1 profiles. Wider hard risk prevents pre-review SL; early soft cut protects capital.
MGS=((1,.15,.00),(1,.10,.05),(1,.05,.10),(1,.00,.15),(1,-.10,.20),(2,.00,.15),(2,-.15,.25))
LOOKBACKS=(5,7,10,15,20);TARGET=80.0

def methods():
 for f in FAMS:
  for hr in HRS:
   for rf in RFS:
    for sw in SWS:
     for off,exp in ENTS:
      for ca,cr,prog in MGS:
       yield(f,hr,1.0,rf,sw,off,exp,ca,cr,prog)
def dates(a,b):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(b).date();z=[]
 while x<=y:z.append(x.isoformat());x=x.fromordinal(x.toordinal()+1)
 return z
def outcome(mx,data,p,d):
 hs=mx.get(d)
 if not hs:return None
 fam,hr,*_=p;hh=hr if hr in hs else max([x for x in hs if x<=hr],default=max(hs));i,r,c=hs[hh]
 return v.trade(data[SYM],i,v.side(fam,r,c),p)
def hscore(z):
 if not z:return -999
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);res=tp+sl;wr=tp/res if res else 0;mean=statistics.mean(x[1] for x in z);cuts=(len(z)-res)/len(z)
 return 2.0*wr+.55*mean-.10*cuts+.004*res
def online(ds,cache,lb):
 out=[];last=0
 for di,d in enumerate(ds):
  hist=ds[max(0,di-lb):di];best=None;be=None
  for ei,c in enumerate(cache):
   z=[c.get(x) for x in hist];z=[x for x in z if x]
   if len(z)<3:continue
   sc=hscore(z)
   if best is None or sc>best:best=sc;be=ei
  if be is None:be=last
  o=cache[be].get(d)
  if o is None:
   for ei,c in enumerate(cache):
    if c.get(d):be=ei;o=c[d];break
  if o:out.append((d,be,o));last=be
 return out
def stat(sel,exp):
 z=[x[2] for x in sel];tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def valid(s):return s['missing']==0 and s['resolved']>=10 and s['cutRate']<=85 and s['meanR']>0 and s['wr']>=TARGET
def main():
 data=v.load();mx=v.matrix(data);ps=list(methods());all_ds=dates('2026-01-01','2026-03-31');cache=[];print('V58',SYM,'METHODS',len(ps),flush=True)
 for p in ps:cache.append({d:o for d in all_ds if (o:=outcome(mx,data,p,d)) is not None})
 jan=dates('2026-01-01','2026-01-31');best=None;lb0=None;js=None
 for lb in LOOKBACKS:
  s=stat([x for x in online(jan,cache,lb) if x[0] in jan],31);q=(s['wr'],s['meanR'],-s['cutRate'])
  if best is None or q>best:best=q;lb0=lb;js=s
 test=dates('2026-02-01','2026-03-31');context=jan[-20:]+test;sel=online(context,cache,lb0);final=[x for x in sel if x[0]>='2026-02-01'];fs=stat(final,59);out={'version':'CRYPTO_V58_ONLINE_PROTECT_2MONTH','symbol':SYM,'lockedLookback':lb0,'developmentJan':js,'finalFebMar':fs,'status':'PASS' if valid(fs) else 'FAIL'};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v58.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
