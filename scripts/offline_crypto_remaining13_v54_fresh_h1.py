#!/usr/bin/env python3
import json,math,os,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h
from scripts.offline_crypto_v28_separate import PROFILE

TARGETS='AAVE AVAX DOT FLOKI INJ LDO LIT ONDO POL S TAO WLD XPL'.split()
SYM=os.environ.get('TARGET_SYMBOL','').strip().upper()
if SYM not in TARGETS: raise RuntimeError('TARGET_SYMBOL invalid')
SNAP='data/provider_snapshots/crypto_remaining13_h1_jan_mar_2026.json';CTX='data/provider_snapshots/crypto_context_h1_jan_mar_2026.json';TARGET=80.0
STAGES=[('JAN_FEB','2026-01-01','2026-01-31','2026-02-01','2026-02-28'),('FEB_MAR','2026-02-01','2026-02-28','2026-03-01','2026-03-31')]
FAMILIES=('OWN_H1','OWN_H4','BTC','ETH','SOL','RELBTC','RELETH','MOM','MEANREV','HYBRID')
HOURS=(0,2,4,6,8,10,12,14,16,18,20)
RRS=(1.0,2.0);RFS=(.75,1.0,1.25,1.5,2.0,2.5,3.0,4.0);SWS=(6,12,24)
ENTRIES=((0.0,1),(.25,1),(.5,2),(.75,2))
MGMTS=((1,.10,.00),(1,.00,.05),(1,-.10,.10),(1,-.20,.15),(2,-.10,.10),(2,-.25,.20),(3,-.35,.25),(3,-.50,.30))

def load():
 d=json.load(open(SNAP));c=json.load(open(CTX));raw={SYM:d['data'][SYM],**c['data']};return {s:h.enrich(v) for s,v in raw.items()}
def maps(data):return {s:{r['dt']:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}
def core(mp,t):
 q={s:mp[s].get(t) for s in ('BTC','ETH','SOL')};
 if any(v is None or v[1].get('ret24') is None for v in q.values()):return None
 return {s:{'r24':q[s][1]['ret24'],'r72':q[s][1]['ret72']} for s in q}
def side(f,r,c):
 h1=1 if r['close']>r['ema20']>r['ema50'] else -1 if r['close']<r['ema20']<r['ema50'] else (1 if r['close']>r['ema20'] else -1)
 if f=='OWN_H1':return h1
 if f=='OWN_H4':return r['h4'] or h1
 if f in ('BTC','ETH','SOL'):
  x=c[f]['r24']+.4*c[f]['r72'];return 1 if x>=0 else -1
 if f=='RELBTC':x=(r['ret24']-c['BTC']['r24'])+.4*(r['ret72']-c['BTC']['r72'])
 elif f=='RELETH':x=(r['ret24']-c['ETH']['r24'])+.4*(r['ret72']-c['ETH']['r72'])
 elif f=='MOM':x=r['mom6']+.25*r['ret24']*20
 elif f=='MEANREV':return -1 if r['dev']>0 else 1
 else:x=r['mom6']+.3*(r['ret24']-c['BTC']['r24'])*20+.2*c['BTC']['r24']*20
 return 1 if x>=0 else -1
def trade(rows,i,sd,p):
 fam,hour,rr,rf,sw,off,exp,ca,cr,prog=p
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];ei=None;entry=None
 if off==0:ei=i+1;entry=rows[ei]['open']
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
  age=j-ei+1;cur=(x['close']-entry)/risk*sd;fav=(x['high']-entry)/risk if sd==1 else (entry-x['low'])/risk;best=max(best,fav);em=x.get('ema20');broken=em is not None and (x['close']-em)*sd<0
  if age>=ca and (cur<=cr or (broken and cur<.10) or best<prog):return ('CUT',max(-1,cur))
 last=rows[end-1]['close'];return ('CUT',max(-1,min(rr,(last-entry)/risk*sd)))
def days(a,b):return (datetime.fromisoformat(b).date()-datetime.fromisoformat(a).date()).days+1
def full(mx,a,b):return len([d for d in mx if a<=d<=b])==days(a,b)
def matrix(data):
 mp=maps(data);mx=defaultdict(dict);times=sorted(set(mp[SYM]) & set(mp['BTC']) & set(mp['ETH']) & set(mp['SOL']))
 for t in times:
  if t.hour not in HOURS:continue
  q=mp[SYM].get(t);c=core(mp,t)
  if not q or not c:continue
  i,r=q
  if r.get('ret72') is None or r.get('ema50') is None:continue
  mx[t.date().isoformat()][t.hour]=(i,r,c)
 return mx
def evaluate(mx,data,p,a,b):
 fam,hour,*_=p;exp=days(a,b);z=[]
 for d in sorted(k for k in mx if a<=k<=b):
  hs=mx[d];hh=hour if hour in hs else max([x for x in hs if x<=hour],default=max(hs));i,r,c=hs[hh];o=trade(data[SYM],i,side(fam,r,c),p)
  if o:z.append(o)
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def params():
 for f in FAMILIES:
  for h0 in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for off,exp in ENTRIES:
       for ca,cr,prog in MGMTS:yield(f,h0,rr,rf,sw,off,exp,ca,cr,prog)
def main():
 data=load();mx=matrix(data);ps=list(params());hist=[];win=None;print('SYMBOL',SYM,'FAMILY',PROFILE.get(SYM),'PARAMS',len(ps),flush=True)
 for name,da,db,fa,fb in STAGES:
  if not full(mx,da,db) or not full(mx,fa,fb):hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
  best=None;bp=None;ds=None
  for p in ps:
   s=evaluate(mx,data,p,da,db);r=rank(s)
   if best is None or r>best:best=r;bp=p;ds=s
  fs=evaluate(mx,data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print('TEST',SYM,json.dumps(rec),flush=True)
  if ok:win=rec;break
 out={'version':'CRYPTO_REMAINING13_V54_FRESH_H1','symbol':SYM,'profile':PROFILE.get(SYM),'status':'PASS' if win else 'FAIL','frozen':win,'history':hist};Path('data/remaining').mkdir(parents=True,exist_ok=True);json.dump(out,open(f'data/remaining/crypto_{SYM.lower()}_v54.json','w'),indent=2);print('FINAL',json.dumps(out),flush=True)
if __name__=='__main__':main()
