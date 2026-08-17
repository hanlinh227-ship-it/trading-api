#!/usr/bin/env python3
import json,statistics
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import scripts.offline_crypto_precision_evolver_v36 as b

SNAP='data/provider_snapshots/crypto_4h_jul_dec_2025.json'
OUT='data/offline_crypto_daily_each_symbol_v48_2025_remaining.json'
TARGET=80.0
REMAINING='AAVE ALGO ARB AVAX DOT FIL FLOKI GRASS INJ JUP LDO LINK LIT MOODENG NEAR ONDO POL S SUI TAO TON WIF WLD XPL'.split()
STAGES=[('JUL_AUG','2025-07-01','2025-07-31','2025-08-01','2025-08-31'),('AUG_SEP','2025-08-01','2025-08-31','2025-09-01','2025-09-30'),('SEP_OCT','2025-09-01','2025-09-30','2025-10-01','2025-10-31'),('OCT_NOV','2025-10-01','2025-10-31','2025-11-01','2025-11-30'),('NOV_DEC','2025-11-01','2025-11-30','2025-12-01','2025-12-31')]
FAMILIES=('BTCALIGN','RELATIVE','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID')
HOURS=(0,4,8,12,16,20)
RRS=(1.0,2.0);RFS=(.85,1.25,1.75,2.25);SWS=(5,10)
ENTRIES=(('MARKET',0.0),('HYBRID',.35),('HYBRID',.70))
MGMTS=((1,-.05,.00),(1,-.15,.05),(2,-.20,.10),(2,-.35,.20))

def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def days(a,c):return (datetime.fromisoformat(c).date()-datetime.fromisoformat(a).date()).days+1
def side(f,m):
 if f=='BTCALIGN':x=m['btc24']+.5*m['btc72']
 elif f=='RELATIVE':x=1.5*m['rel24']+.5*m['rel72']
 elif f=='H4TREND':return m['h4'] or (1 if m['mom']>=0 else -1)
 elif f=='D1TREND':return m['d1'] or m['h4'] or 1
 elif f=='MOMENTUM':x=m['mom']+.25*m['rel24']
 elif f=='MEANREV':return -1 if m['dev']>0 else 1
 elif f=='BREADTH':return 1 if m['breadth']>=.5 else -1
 else:x=m['rel24']+.7*m['btc24']+.25*m['mom']
 return 1 if x>=0 else -1

def context(mp,t,covered):
 elig={s:q for s in covered if (q:=mp[s].get(t)) and q[1].get('ret24') is not None and q[1].get('ema50') is not None}
 if len(elig)<20:return None
 rets=[q[1]['ret24'] for q in elig.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);btc=elig.get('BTC');btc24=btc[1]['ret24'] if btc else med;btc72=btc[1]['ret72'] if btc else 0
 return elig,{'breadth':breadth,'btc24':btc24,'btc72':btc72}
def meta(r,reg):
 h4=1 if r['close']>r['ema20']>r['ema50'] else -1 if r['close']<r['ema20']<r['ema50'] else (1 if r['close']>r['ema20'] else -1)
 return {'h4':h4,'d1':r.get('d1',0),'mom':r.get('mom24atr',0),'dev':r.get('dev',0),'rel24':r['ret24']-reg['btc24'],'rel72':r['ret72']-reg['btc72'],'btc24':reg['btc24'],'btc72':reg['btc72'],'breadth':reg['breadth']}
def execute(rows,i,sd,p):
 fam,h,rr,rf,sw,em,off,ca,cr,prog=p
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];entry=None;ei=None
 if em=='MARKET':ei=i+1;entry=rows[ei]['open']
 else:
  target=sig['close']-sd*off*atr;last=min(len(rows)-1,i+1)
  if rows[last]['low']<=target<=rows[last]['high']:ei=last;entry=target
  else:ei=last;entry=rows[last]['close']
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if sd==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if sd==1 else swing-entry)+.08*atr)
 if risk<=0:return None
 sl=entry-sd*risk;tp=entry+sd*rr*risk;hold=9 if rr==1 else 15;end=min(len(rows),ei+hold);best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if sd==1 else x['high']>=sl;ht=x['high']>=tp if sd==1 else x['low']<=tp
  if hs and ht:return ('SL',-1.0)
  if hs:return ('SL',-1.0)
  if ht:return ('TP',rr)
  age=j-ei+1;cur=(x['close']-entry)/risk*sd;fav=(x['high']-entry)/risk if sd==1 else (entry-x['low'])/risk;best=max(best,fav)
  if age>=ca:
   e=x.get('ema20');broken=e is not None and (x['close']-e)*sd<0
   if cur<=cr or (broken and cur<.1) or (age>=2 and best<prog):return ('CUT',max(-1,cur))
 last=rows[end-1]['close'];return ('CUT',max(-1,min(rr,(last-entry)/risk*sd)))
def full(ds,a,c):return len([d for d in ds if a<=d<=c])==days(a,c)
def evaluate(sym,ds,data,p,a,c):
 fam,h,*_=p;exp=days(a,c);z=[]
 for d in sorted(k for k in ds if a<=k<=c):
  hs=ds[d];hh=h if h in hs else max([x for x in hs if x<=h],default=max(hs));i,m=hs[hh];o=execute(data[sym],i,side(fam,m),p)
  if o:z.append(o)
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':exp,'tradedDays':len(z),'missing':exp-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=84 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def params():
 for fam in FAMILIES:
  for h in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for em,off in ENTRIES:
       for ca,cr,prog in MGMTS:yield(fam,h,rr,rf,sw,em,off,ca,cr,prog)
def main():
 doc=json.load(open(SNAP));covered=set(doc['data']);data={s:b.enrich(doc['data'][s]) for s in covered};mp=b.maps(data);mx=defaultdict(lambda:defaultdict(dict));times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  pack=context(mp,t,covered)
  if not pack:continue
  elig,reg=pack
  for s,q in elig.items():
   if t.hour not in HOURS:continue
   i,r=q;mx[s][t.date().isoformat()][t.hour]=(i,meta(r,reg))
 ps=list(params());print('PARAMS',len(ps),flush=True);res={}
 for sym in REMAINING:
  if sym not in covered:
   res[sym]={'status':'NO_2025_DATA','history':[]};continue
  hist=[];win=None
  for name,da,db,fa,fb in STAGES:
   if not full(mx[sym],da,db) or not full(mx[sym],fa,fb):hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
   best=None;bp=None;ds=None
   for p in ps:
    s=evaluate(sym,mx[sym],data,p,da,db);r=rank(s)
    if best is None or r>best:best=r;bp=p;ds=s
   fs=evaluate(sym,mx[sym],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[s for s in REMAINING if res[s]['status']=='PASS'];failed=[s for s in REMAINING if res[s]['status']!='PASS'];out={'version':'CRYPTO_DAILY_EACH_SYMBOL_V48_2025_REMAINING','independentDataset':SNAP,'testedRemaining':REMAINING,'rule':'Only prior month selects each coin own family/hour/entry/RR/management. Next month must trade daily, TP/SL WR>=80, RR1 or2, meanR>0, >=5 resolved, CUT<=84%.','passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed},indent=2),flush=True)
if __name__=='__main__':main()
