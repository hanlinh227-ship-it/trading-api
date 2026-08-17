#!/usr/bin/env python3
import json,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import scripts.offline_crypto_precision_evolver_v36 as b
import scripts.offline_crypto_precision_evolver_v36b as fixed
b.regime_at=fixed.fixed_regime_at
MAIN='data/provider_snapshots/crypto_4h_feb_jul_2026.json';BUF='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json';OUT='data/offline_crypto_daily_each_symbol_v46_rulefamilies.json';TARGET=80.0
STAGES=[('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
FAMILIES=('BTCALIGN','RELATIVE','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID')
HOURS=(0,4,8,12,16,20);RRS=(1.0,2.0);RFS=(.65,.85,1.1,1.4);SWS=(3,5,8);CUTS=((1,-.10),(1,.0),(2,-.20),(2,-.10))

def load():
 a=json.load(open(MAIN));z=json.load(open(BUF));out={}
 for s in b.SYMBOLS:
  d={x[0]:x for x in a['data'][s]};d.update({x[0]:x for x in z['data'][s]});out[s]=[d[k] for k in sorted(d)]
 return out

def side(fam,m):
 if fam=='BTCALIGN':x=m['btc24']*1.2+m['btc72']*.6
 elif fam=='RELATIVE':x=m['rel24']*1.4+m['rel72']*.5
 elif fam=='H4TREND':return m['h4'] or (1 if m['mom']>=0 else -1)
 elif fam=='D1TREND':return m.get('d1',0) or m['h4'] or 1
 elif fam=='MOMENTUM':x=m['mom']
 elif fam=='MEANREV':return -1 if m['dev']>0 else 1
 elif fam=='BREADTH':return 1 if m['breadth']>=.5 else -1
 else:x=m['rel24']+m['btc24']*.7+m['mom']*.15
 return 1 if x>=0 else -1

def trade(rows,i,sd,rr,rf,sw,ca,cr):
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if sd==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if sd==1 else swing-entry)+.08*atr);sl=entry-sd*risk;tp=entry+sd*rr*risk;end=min(len(rows),ei+(6 if rr==1 else 9));best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if sd==1 else x['high']>=sl;ht=x['high']>=tp if sd==1 else x['low']<=tp
  if hs and ht:return 'SL',-1.0
  if hs:return 'SL',-1.0
  if ht:return 'TP',rr
  age=j-ei+1;cur=(x['close']-entry)/risk*sd;fav=(x['high']-entry)/risk if sd==1 else (entry-x['low'])/risk;best=max(best,fav);em=x.get('ema20')
  if age>=ca and (cur<=cr or (em is not None and (x['close']-em)*sd<0 and cur<.10) or (age>=2 and best<.10)):return 'CUT',max(-1,cur)
 last=rows[end-1]['close'];return 'CUT',max(-1,min(rr,(last-entry)/risk*sd))

def matrix(data,mp):
 out=defaultdict(lambda:defaultdict(dict));times=sorted(set().union(*(set(x) for x in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<'2026-02-10' or d>'2026-07-31':continue
  pack=b.regime_at(mp,t)
  if not pack:continue
  eligible,reg=pack
  for s,q in eligible.items():
   i,r=q;_,m=b.features(s,r,reg,1);m['d1']=r.get('d1',0);out[s][d][t.hour]=(i,m)
 return out

def days(a,c):return (datetime.fromisoformat(c).date()-datetime.fromisoformat(a).date()).days+1

def evals(sym,ds,data,p,a,c):
 fam,h,rr,rf,sw,ca,cr=p;exp=days(a,c);z=[]
 for d in sorted(k for k in ds if a<=k<=c):
  hs=ds[d];hh=h if h in hs else max([x for x in hs if x<=h],default=max(hs));i,m=hs[hh];o=trade(data[sym],i,side(fam,m),rr,rf,sw,ca,cr)
  if o:z.append(o)
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}

def rank(s):
 ok=s['missing']==0 and s['resolved']>=7 and s['cutRate']<=75 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],s['resolved'],-s['cutRate'])
def params():
 for f in FAMILIES:
  for h in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for ca,cr in CUTS:yield(f,h,rr,rf,sw,ca,cr)
def main():
 raw=load();data={s:b.enrich(raw[s]) for s in b.SYMBOLS};mp=b.maps(data);mx=matrix(data,mp);ps=list(params());res={}
 for sym in b.SYMBOLS:
  hist=[];win=None
  for name,da,db,fa,fb in STAGES:
   best=None;bp=None;bs=None
   for p in ps:
    s=evals(sym,mx[sym],data,p,da,db);r=rank(s)
    if best is None or r>best:best=r;bp=p;bs=s
   fs=evals(sym,mx[sym],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'dev':bs,'final':fs,'pass':ok};hist.append(rec);print(sym,name,bp,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[s for s in b.SYMBOLS if res[s]['status']=='PASS'];failed=[s for s in b.SYMBOLS if res[s]['status']=='FAIL'];out={'version':'CRYPTO_DAILY_EACH_SYMBOL_V46_RULEFAMILIES','target':'Each coin daily; own rule family; TP/SL WR>=80; RR1 or2; CUT<=75; positive meanR','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/61,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
