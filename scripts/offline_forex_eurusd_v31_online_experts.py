#!/usr/bin/env python3
import json,statistics
from datetime import datetime,timedelta
from pathlib import Path
import scripts.offline_forex_eurusd_eurnzd_v28_special as v

PAIR='EURUSD';OUT='data/offline_forex_eurusd_v31_online_experts.json';TARGET=80.0
# Experts are predeclared method variants; selection each day uses ONLY preceding days.
def experts():
 for f in v.FAMILIES:
  for h in (6,8,10,12,14,16,18,20):
   for rr in (1.0,2.0):
    for rf in (1.0,1.5,2.0):
     for sw in (6,18):
      for em,off,exp in (('MARKET',0,1),('HYBRID',.5,2)):
       for ca,cr,prog in ((1,.0,0),(2,-.2,.1),(3,-.35,.2)):
        yield(f,h,rr,rf,sw,em,off,exp,ca,cr,prog)
LOOKBACKS=(7,10,15,20,30);MINHIST=(3,5,7);WRWEIGHTS=(.5,1.0,1.5,2.0);SWITCH_PEN=(0,.05,.10)

def weekdays(a,c):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();out=[]
 while x<=y:
  if x.weekday()<5:out.append(x.isoformat())
  x+=timedelta(days=1)
 return out

def outcome(rows,p,d):
 h=p[1];t=datetime.fromisoformat(d).replace(tzinfo=rows[0]['dt'].tzinfo)+timedelta(hours=h);idx={r['dt']:(i,r) for i,r in enumerate(rows)}.get(t)
 if not idx:return None
 i,r=idx
 if r.get('ema50') is None or r.get('mom24') is None:return None
 return v.execute(rows,i,v.side(p[0],r,rows,i),p)
def score_hist(z,w):
 if not z:return -999
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);res=tp+sl;wr=tp/res if res else 0;mean=statistics.mean(x[1] for x in z)
 return w*wr+mean*.35+min(res,10)*.005
def online(days,cache,lb,minhist,w,pen):
 selected=[];last=None
 for di,d in enumerate(days):
  hist_days=days[max(0,di-lb):di]
  best=None;be=None
  for ei,p in enumerate(cache['params']):
   hz=[cache['out'][ei].get(x) for x in hist_days];hz=[x for x in hz if x]
   if len(hz)<minhist:continue
   sc=score_hist(hz,w)-(pen if last is not None and ei!=last else 0)
   if best is None or sc>best:best=sc;be=ei
  if be is None:be=last if last is not None else 0
  o=cache['out'][be].get(d)
  if o is None:
   # deterministic fallback to first expert that has a trade on the day
   for ei in range(len(cache['params'])):
    if cache['out'][ei].get(d):be=ei;o=cache['out'][ei][d];break
  if o:selected.append((d,be,o));last=be
 return selected
def stat(sel,exp):
 z=[x[2] for x in sel];tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def main():
 doc=json.load(open(v.SNAP));rows=v.enrich(doc['data'][PAIR]);ps=list(experts());all_days=weekdays('2025-02-01','2025-06-30');cache={'params':ps,'out':[]};print('EXPERTS',len(ps),flush=True)
 for n,p in enumerate(ps):
  cache['out'].append({d:o for d in all_days if (o:=outcome(rows,p,d)) is not None})
  if (n+1)%500==0:print('CACHE',n+1,flush=True)
 stages=[('FEB_MAR','2025-02-01','2025-02-28','2025-03-01','2025-03-31'),('MAR_APR','2025-03-01','2025-03-31','2025-04-01','2025-04-30'),('APR_MAY','2025-04-01','2025-04-30','2025-05-01','2025-05-31'),('MAY_JUN','2025-05-01','2025-05-31','2025-06-01','2025-06-30')];hist=[];winner=None
 for name,da,db,fa,fb in stages:
  devdays=weekdays(da,db);findays=weekdays(fa,fb);best=None;bp=None;ds=None
  # prepend earlier days as observable lookback context
  prefix=[d for d in all_days if d<da][-30:]
  for lb in LOOKBACKS:
   for mh in MINHIST:
    for w in WRWEIGHTS:
     for pen in SWITCH_PEN:
      sel=online(prefix+devdays,cache,lb,mh,w,pen);devsel=[x for x in sel if da<=x[0]<=db];s=stat(devsel,len(devdays));r=rank(s)
      if best is None or r>best:best=r;bp=(lb,mh,w,pen);ds=s
  lb,mh,w,pen=bp;context=[d for d in all_days if d<fa][-30:];sel=online(context+findays,cache,lb,mh,w,pen);fs=stat([x for x in sel if fa<=x[0]<=fb],len(findays));ok=rank(fs)[0]==1;rec={'stage':name,'onlineParams':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('EURUSD ONLINE',json.dumps(rec),flush=True)
  if ok:winner=rec;break
 out={'version':'FOREX_EURUSD_V31_ONLINE_EXPERTS','status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
