#!/usr/bin/env python3
import json,os,statistics
from datetime import datetime
from pathlib import Path
import scripts.offline_crypto_remaining13_v54_fresh_h1 as v

SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
TARGETS='DOT FLOKI INJ LDO ONDO POL TAO WLD'.split()
if SYM not in TARGETS:raise RuntimeError('TARGET_SYMBOL invalid')
# Predeclared compact expert pool. Each day selects only from prior completed-day performance.
FAMS=('OWN_H1','OWN_H4','BTC','ETH','RELBTC','RELETH','MOM','MEANREV','HYBRID')
HRS=(4,8,12,16,20)
RFS=(.75,1.25,2.0,3.0)
SWS=(6,12)
ENTS=((0.0,1),(.5,2))
MGS=((1,.10,.05),(1,.00,.10),(1,-.10,.20),(2,-.15,.20))
LOOKBACKS=(5,7,10,15,20)

def experts():
 for f in FAMS:
  for hr in HRS:
   for rf in RFS:
    for sw in SWS:
     for off,exp in ENTS:
      for ca,cr,prog in MGS:
       yield(f,hr,1.0,rf,sw,off,exp,ca,cr,prog)

def all_days(a,b):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(b).date();z=[]
 while x<=y:z.append(x.isoformat());x=x.fromordinal(x.toordinal()+1)
 return z

def outcome(mx,data,p,d):
 hs=mx.get(d)
 if not hs:return None
 f,hr,*_=p;hh=hr if hr in hs else max([x for x in hs if x<=hr],default=max(hs));i,r,c=hs[hh]
 return v.trade(data[SYM],i,v.side(f,r,c),p)

def score_hist(z):
 if not z:return -999
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);res=tp+sl;wr=tp/res if res else 0;mean=statistics.mean(x[1] for x in z);cut=(len(z)-res)/len(z)
 return 1.5*wr+.45*mean-.15*cut+.003*res

def online(days,cache,lb):
 out=[];last=0
 for di,d in enumerate(days):
  hist=days[max(0,di-lb):di];best=None;be=None
  for ei in range(len(cache)):
   z=[cache[ei].get(x) for x in hist];z=[x for x in z if x]
   if len(z)<3:continue
   sc=score_hist(z)
   if best is None or sc>best:best=sc;be=ei
  if be is None:be=last
  o=cache[be].get(d)
  if o is None:
   for ei in range(len(cache)):
    if cache[ei].get(d):be=ei;o=cache[ei][d];break
  if o:out.append((d,be,o));last=be
 return out

def stat(sel,exp):
 z=[x[2] for x in sel];tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=8 and s['cutRate']<=80 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def main():
 data=v.load();mx=v.matrix(data);ps=list(experts());days=all_days('2026-01-01','2026-03-31');cache=[];print('EXPERTS',SYM,len(ps),flush=True)
 for n,p in enumerate(ps):cache.append({d:o for d in days if (o:=outcome(mx,data,p,d)) is not None})
 # Jan chooses lookback policy; Feb+Mar is sequential out-of-month evaluation with that lookback locked.
 jan=[d for d in days if d.startswith('2026-01-')];best=None;lb0=None;js=None
 for lb in LOOKBACKS:
  s=stat([x for x in online(jan,cache,lb) if x[0] in jan],len(jan));r=rank(s)
  if best is None or r>best:best=r;lb0=lb;js=s
 evaldays=[d for d in days if d>='2026-02-01'];context=jan[-max(LOOKBACKS):]+evaldays;sel=online(context,cache,lb0);feb=[x for x in sel if '2026-02-01'<=x[0]<='2026-02-28'];mar=[x for x in sel if '2026-03-01'<=x[0]<='2026-03-31'];fs=stat(feb,28);ms=stat(mar,31);combined=stat(feb+mar,59)
 passed=rank(combined)[0]==1 and (rank(fs)[0]==1 or rank(ms)[0]==1)
 out={'version':'CRYPTO_REMAINING8_V57_ONLINE','symbol':SYM,'lockedLookback':lb0,'developmentJan':js,'feb':fs,'mar':ms,'combinedFebMar':combined,'status':'PASS' if passed else 'FAIL'};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v57.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
