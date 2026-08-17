#!/usr/bin/env python3
import json,statistics
from datetime import datetime
from pathlib import Path
import scripts.offline_crypto_ton_v53_progress as t
import scripts.offline_crypto_daily_each_symbol_v46_rulefamilies as base

SYM='TON';OUT='data/offline_crypto_ton_v59_online_2month.json';TARGET=80.0
FAMS=('BTCALIGN','RELATIVE','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID');HRS=(0,4,8,12,16,20)
RFS=(1.25,1.75,2.5,3.5,4.5);SWS=(3,5,8);MG=((1,.15,.00),(1,.10,.05),(1,.00,.10),(1,-.10,.20),(2,-.10,.20),(2,-.25,.30));LOOKBACKS=(5,7,10,15,20)

def methods():
 for f in FAMS:
  for h in HRS:
   for rf in RFS:
    for sw in SWS:
     for age,cr,prog in MG:yield(f,h,(1.0,rf,sw,12,age,cr,prog))
def dates(a,b):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(b).date();z=[]
 while x<=y:z.append(x.isoformat());x=x.fromordinal(x.toordinal()+1)
 return z
def outcome(mx,data,p,d):
 f,h,cfg=p;hs=mx[SYM].get(d)
 if not hs:return None
 hh=h if h in hs else max([x for x in hs if x<=h],default=max(hs));i,m=hs[hh];return t.raw(data[SYM],i,base.side(f,m),cfg)
def hscore(z):
 if not z:return -999
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);res=tp+sl;wr=tp/res if res else 0;mean=statistics.mean(x[1] for x in z);cut=(len(z)-res)/len(z)
 return 2*wr+.55*mean-.1*cut+.004*res
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
 rawd=base.load();data={s:base.b.enrich(rawd[s]) for s in base.b.SYMBOLS};mp=base.b.maps(data);mx=base.matrix(data,mp);ps=list(methods());days=dates('2026-05-01','2026-07-31');cache=[];print('TON_METHODS',len(ps),flush=True)
 for p in ps:cache.append({d:o for d in days if (o:=outcome(mx,data,p,d)) is not None})
 may=dates('2026-05-01','2026-05-31');best=None;lb0=None;ms=None
 for lb in LOOKBACKS:
  s=stat([x for x in online(may,cache,lb) if x[0] in may],31);q=(s['wr'],s['meanR'],-s['cutRate'])
  if best is None or q>best:best=q;lb0=lb;ms=s
 test=dates('2026-06-01','2026-07-31');sel=online(may[-20:]+test,cache,lb0);final=[x for x in sel if x[0]>='2026-06-01'];fs=stat(final,61);out={'version':'CRYPTO_TON_V59_ONLINE_2MONTH','lockedLookback':lb0,'developmentMay':ms,'finalJuneJuly':fs,'status':'PASS' if valid(fs) else 'FAIL'};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
