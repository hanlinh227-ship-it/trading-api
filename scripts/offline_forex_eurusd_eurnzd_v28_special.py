#!/usr/bin/env python3
import json,math,statistics
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

SNAP='data/provider_snapshots/forex_eurusd_eurnzd_h1_jan_jun_2025.json';OUT='data/offline_forex_eurusd_eurnzd_v28_special.json';PAIRS=['EURUSD','EURNZD'];TARGET=80.0
STAGES=[('FEB_MAR','2025-02-01','2025-02-28','2025-03-01','2025-03-31'),('MAR_APR','2025-03-01','2025-03-31','2025-04-01','2025-04-30'),('APR_MAY','2025-04-01','2025-04-30','2025-05-01','2025-05-31'),('MAY_JUN','2025-05-01','2025-05-31','2025-06-01','2025-06-30')]
FAMILIES=('H1TREND','H4TREND','MOM6','MOM24','MIXMOM','MEANREV','BREAKOUT','RANGEFADE','RSITREND','SESSIONMOM')
HOURS=(0,2,4,6,8,10,12,14,16,18,20)
RRS=(1.0,2.0);RFS=(.75,1.0,1.25,1.5,1.75,2.0,2.5);SWS=(6,12,18,24)
ENTRIES=(('MARKET',0.0,1),('HYBRID',.2,1),('HYBRID',.35,2),('HYBRID',.5,2),('HYBRID',.7,3))
MGMTS=((1,.00,.00),(1,-.05,.05),(1,-.15,.10),(2,-.10,.10),(2,-.25,.15),(3,-.35,.20),(4,-.45,.25))

def dt(s):return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
def ema(v,n):
 o=[None]*len(v)
 if len(v)<n:return o
 e=sum(v[:n])/n;o[n-1]=e;k=2/(n+1)
 for i in range(n,len(v)):e=v[i]*k+e*(1-k);o[i]=e
 return o
def enrich(raw):
 rows=[{'dt':dt(x[0]),'open':x[1],'high':x[2],'low':x[3],'close':x[4]} for x in raw];c=[r['close'] for r in rows];e20=ema(c,20);e50=ema(c,50);tr=[0.0]*len(rows);atr=[None]*len(rows);rsi=[None]*len(rows)
 for i in range(1,len(rows)):tr[i]=max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-c[i-1]),abs(rows[i]['low']-c[i-1]))
 if len(rows)>15:
  a=sum(tr[1:15])/14;ag=sum(max(c[i]-c[i-1],0) for i in range(1,15))/14;al=sum(max(c[i-1]-c[i],0) for i in range(1,15))/14
  for i in range(14,len(rows)):
   if i>14:
    a=(a*13+tr[i])/14;d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
   atr[i]=a;rsi[i]=100 if al==0 else 100-100/(1+ag/al)
 # completed H4 trend from 4-hour closes
 hb=defaultdict(list)
 for i,r in enumerate(rows):hb[r['dt'].replace(hour=(r['dt'].hour//4)*4,minute=0,second=0,microsecond=0)].append((i,r))
 seq=[]
 for k in sorted(hb):
  z=hb[k]
  if len(z)==4:seq.append((z[-1][0],z[-1][1]['close']))
 hc=[x[1] for x in seq];h20=ema(hc,20);h50=ema(hc,50);hm={}
 for j,(idx,cl) in enumerate(seq):
  if h20[j] is not None and h50[j] is not None:hm[idx]=1 if cl>h20[j]>h50[j] else -1 if cl<h20[j]<h50[j] else (1 if cl>h20[j] else -1)
 lh=0
 for i,r in enumerate(rows):
  if i in hm:lh=hm[i]
  r.update({'ema20':e20[i],'ema50':e50[i],'atr':atr[i],'rsi':rsi[i],'h4':lh})
  if i>=72 and atr[i]:
   for h in (3,6,12,24,72):r[f'ret{h}']=math.log(c[i]/c[i-h])
   r['dev']=(c[i]-e20[i])/atr[i] if e20[i] else 0;r['mom6']=(c[i]-c[i-6])/atr[i];r['mom24']=(c[i]-c[i-24])/atr[i]
 return rows
def side(f,r,rows,i):
 h1=1 if r['close']>r['ema20']>r['ema50'] else -1 if r['close']<r['ema20']<r['ema50'] else (1 if r['close']>r['ema20'] else -1)
 if f=='H1TREND':return h1
 if f=='H4TREND':return r['h4'] or h1
 if f=='MOM6':x=r['mom6']
 elif f=='MOM24':x=r['mom24']
 elif f=='MIXMOM':x=1.6*r['mom6']+.7*r['mom24']
 elif f=='MEANREV':return -1 if r['dev']>0 else 1
 elif f=='BREAKOUT':
  hi=max(x['high'] for x in rows[max(0,i-23):i]);lo=min(x['low'] for x in rows[max(0,i-23):i]);x=(r['close']-(hi+lo)/2)
 elif f=='RANGEFADE':
  hi=max(x['high'] for x in rows[max(0,i-23):i]);lo=min(x['low'] for x in rows[max(0,i-23):i]);return -1 if r['close']>(hi+lo)/2 else 1
 elif f=='RSITREND':return 1 if (r['rsi'] or 50)>=50 else -1
 else:x=r['mom6']+(r['ret3']*100)*.15
 return 1 if x>=0 else -1
def execute(rows,i,sd,p):
 fam,h,rr,rf,sw,em,off,exp,ca,cr,prog=p
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];ei=None;entry=None
 if em=='MARKET':ei=i+1;entry=rows[ei]['open']
 else:
  target=sig['close']-sd*off*atr;last=min(len(rows)-1,i+exp)
  for j in range(i+1,last+1):
   if rows[j]['low']<=target<=rows[j]['high']:ei=j;entry=target;break
  if ei is None:ei=last;entry=rows[ei]['close']
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if sd==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if sd==1 else swing-entry)+.08*atr)
 if risk<=0:return None
 sl=entry-sd*risk;tp=entry+sd*rr*risk;end=min(len(rows),ei+(30 if rr==1 else 48));best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if sd==1 else x['high']>=sl;ht=x['high']>=tp if sd==1 else x['low']<=tp
  if hs and ht:return ('SL',-1.0)
  if hs:return ('SL',-1.0)
  if ht:return ('TP',rr)
  age=j-ei+1;cur=(x['close']-entry)/risk*sd;fav=(x['high']-entry)/risk if sd==1 else (entry-x['low'])/risk;best=max(best,fav)
  if age>=ca:
   broken=x.get('ema20') is not None and (x['close']-x['ema20'])*sd<0
   if cur<=cr or (broken and cur<.1) or (age>=2 and best<prog):return ('CUT',max(-1,cur))
 last=rows[end-1]['close'];return ('CUT',max(-1,min(rr,(last-entry)/risk*sd)))
def weekdays(a,c):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();n=0
 while x<=y:
  if x.weekday()<5:n+=1
  x+=timedelta(days=1)
 return n
def evaluate(rows,p,a,c):
 fam,h,*_=p;exp=weekdays(a,c);by={r['dt']:(i,r) for i,r in enumerate(rows)};z=[]
 dates=sorted(set(r['dt'].date().isoformat() for r in rows if a<=r['dt'].date().isoformat()<=c and r['dt'].weekday()<5))
 for d in dates:
  t=datetime.fromisoformat(d).replace(tzinfo=timezone.utc)+timedelta(hours=h);q=by.get(t)
  if not q:continue
  i,r=q
  if r.get('ema50') is None or r.get('mom24') is None:continue
  o=execute(rows,i,side(fam,r,rows,i),p)
  if o:z.append(o)
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def params():
 for f in FAMILIES:
  for h in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for em,off,exp in ENTRIES:
       for ca,cr,prog in MGMTS:yield(f,h,rr,rf,sw,em,off,exp,ca,cr,prog)
def main():
 doc=json.load(open(SNAP));ps=list(params());print('PARAMS',len(ps),flush=True);res={}
 for pair in PAIRS:
  rows=enrich(doc['data'][pair]);hist=[];winner=None
  for name,da,db,fa,fb in STAGES:
   best=None;bp=None;ds=None
   for p in ps:
    s=evaluate(rows,p,da,db);r=rank(s)
    if best is None or r>best:best=r;bp=p;ds=s
   fs=evaluate(rows,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print(pair,name,json.dumps(rec),flush=True)
   if ok:winner=rec;break
  res[pair]={'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist}
 out={'version':'FOREX_EURUSD_EURNZD_V28_SPECIAL','dataset':SNAP,'rule':'Each pair one weekday trade; own price-family/hour/entry/management selected on prior month, next month TP/SL WR>=80, RR1/2, full coverage, meanR>0, >=5 resolved, CUT<=84','results':res,'allPass':all(x['status']=='PASS' for x in res.values())};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
