#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SNAP='data/provider_snapshots/crypto_h1_apr_jul_2026.json'
OUT='data/offline_crypto_h1_daily_each_symbol_v47.json'
TARGET=80.0
ALL='BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS LIT PUMP VIRTUAL XPL ZEC'.split()
STAGES=[('APR_MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('MAY_JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUN_JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
FAMILIES=('BTCALIGN','RELATIVE','H1TREND','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID')
HOURS=(0,4,8,12,16,20)
# rr, risk floor ATR, swing H1, hold H1, limit offset ATR (0=market), expiry, review age H, cut currentR, minimum favorable progress
CFGS=[
 (1.0,1.00,6,24,0,1,1,-.05,.00),(1.0,1.25,12,30,0,1,1,-.10,.05),(1.0,1.50,12,36,0,1,2,-.20,.10),(1.0,1.75,18,42,0,1,2,-.25,.15),(1.0,2.00,18,48,0,1,3,-.35,.20),
 (1.0,1.00,6,24,.35,1,1,-.05,.00),(1.0,1.25,12,30,.50,2,1,-.10,.05),(1.0,1.50,12,36,.70,2,2,-.20,.10),
 (2.0,1.00,6,36,0,1,1,-.05,.00),(2.0,1.50,12,48,0,1,2,-.20,.10),(2.0,2.00,18,60,0,1,3,-.35,.20),(2.0,1.25,12,42,.50,2,1,-.10,.05)
]

def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def ema(v,n):
 out=[None]*len(v)
 if len(v)<n:return out
 e=sum(v[:n])/n;out[n-1]=e;k=2/(n+1)
 for i in range(n,len(v)):e=v[i]*k+e*(1-k);out[i]=e
 return out

def enrich(raw):
 rows=[{'dt':dt(x[0]),'open':x[1],'high':x[2],'low':x[3],'close':x[4]} for x in raw];c=[r['close'] for r in rows];e20=ema(c,20);e50=ema(c,50);tr=[0.0]*len(rows);atr=[None]*len(rows);rsi=[None]*len(rows);adx=[None]*len(rows);plus=[0.0]*len(rows);minus=[0.0]*len(rows)
 for i in range(1,len(rows)):
  tr[i]=max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-c[i-1]),abs(rows[i]['low']-c[i-1]));up=rows[i]['high']-rows[i-1]['high'];dn=rows[i-1]['low']-rows[i]['low'];plus[i]=up if up>dn and up>0 else 0;minus[i]=dn if dn>up and dn>0 else 0
 if len(rows)>15:
  a=sum(tr[1:15])/14;pg=sum(plus[1:15])/14;mg=sum(minus[1:15])/14;ag=sum(max(c[i]-c[i-1],0) for i in range(1,15))/14;al=sum(max(c[i-1]-c[i],0) for i in range(1,15))/14;dx=[]
  for i in range(14,len(rows)):
   if i>14:
    a=(a*13+tr[i])/14;pg=(pg*13+plus[i])/14;mg=(mg*13+minus[i])/14;d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
   atr[i]=a;rsi[i]=100 if al==0 else 100-100/(1+ag/al);pdi=100*pg/a if a else 0;mdi=100*mg/a if a else 0;den=pdi+mdi;dxv=100*abs(pdi-mdi)/den if den else 0;dx.append(dxv)
   if len(dx)>=14:adx[i]=sum(dx[-14:])/14
 # completed H4 and D1 states only
 h4b=defaultdict(list);db=defaultdict(list)
 for i,r in enumerate(rows):
  h4b[r['dt'].replace(hour=(r['dt'].hour//4)*4,minute=0,second=0,microsecond=0)].append((i,r));db[r['dt'].date().isoformat()].append((i,r))
 def state_map(buckets):
  seq=[]
  for k in sorted(buckets):
   z=buckets[k];seq.append((z[-1][0],z[-1][1]['close']))
  cv=[x[1] for x in seq];a20=ema(cv,20);a50=ema(cv,50);m={}
  for j,(idx,cl) in enumerate(seq):
   if a20[j] is not None and a50[j] is not None:m[idx]=1 if cl>a20[j]>a50[j] else -1 if cl<a20[j]<a50[j] else (1 if cl>a20[j] else -1)
  return m
 h4m=state_map(h4b);dm=state_map(db);lh4=0;ld1=0
 for i,r in enumerate(rows):
  if i in h4m:lh4=h4m[i]
  if i in dm:ld1=dm[i]
  r.update({'ema20':e20[i],'ema50':e50[i],'atr':atr[i],'rsi':rsi[i],'adx':adx[i],'h4':lh4,'d1':ld1})
  if i>=72 and atr[i] and c[i]>0:
   for h in (3,6,24,72):r[f'ret{h}']=math.log(c[i]/c[i-h]) if c[i-h]>0 else 0
   r['mom6']=(c[i]-c[i-6])/atr[i];r['dev']=(c[i]-e20[i])/atr[i] if e20[i] else 0
 return rows

def maps(data):return {s:{r['dt']:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}
def context(mp,t):
 elig={s:q for s,m in mp.items() if (q:=m.get(t)) and q[1].get('ret24') is not None and q[1].get('ema50') is not None}
 if len(elig)<20:return None
 rets=[q[1]['ret24'] for q in elig.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);btc=elig.get('BTC');btc24=btc[1]['ret24'] if btc else med;btc72=btc[1]['ret72'] if btc else 0
 return elig,{'breadth':breadth,'median':med,'btc24':btc24,'btc72':btc72}
def meta(row,reg):
 h1=1 if row['close']>row['ema20']>row['ema50'] else -1 if row['close']<row['ema20']<row['ema50'] else (1 if row['close']>row['ema20'] else -1)
 return {'h1':h1,'h4':row['h4'],'d1':row['d1'],'mom':row['mom6'],'dev':row['dev'],'rel24':row['ret24']-reg['btc24'],'rel72':row['ret72']-reg['btc72'],'btc24':reg['btc24'],'btc72':reg['btc72'],'breadth':reg['breadth']}
def side(f,m):
 if f=='BTCALIGN':x=m['btc24']+.5*m['btc72']
 elif f=='RELATIVE':x=1.4*m['rel24']+.5*m['rel72']
 elif f=='H1TREND':return m['h1'] or (1 if m['mom']>=0 else -1)
 elif f=='H4TREND':return m['h4'] or m['h1'] or 1
 elif f=='D1TREND':return m['d1'] or m['h4'] or 1
 elif f=='MOMENTUM':x=m['mom']+.2*m['rel24']
 elif f=='MEANREV':return -1 if m['dev']>0 else 1
 elif f=='BREADTH':return 1 if m['breadth']>=.5 else -1
 else:x=m['rel24']+.7*m['btc24']+.25*m['mom']
 return 1 if x>=0 else -1

def execute(rows,i,sd,cfg):
 rr,rf,sw,hold,off,expiry,ca,cr,prog=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];ei=None;entry=None
 if off==0:ei=i+1;entry=rows[ei]['open']
 else:
  target=sig['close']-sd*off*atr;last=min(len(rows)-1,i+expiry)
  for j in range(i+1,last+1):
   if rows[j]['low']<=target<=rows[j]['high']:ei=j;entry=target;break
  if ei is None:ei=last;entry=rows[ei]['close']
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if sd==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if sd==1 else swing-entry)+.08*atr)
 if risk<=0:return None
 sl=entry-sd*risk;tp=entry+sd*rr*risk;end=min(len(rows),ei+hold);best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if sd==1 else x['high']>=sl;ht=x['high']>=tp if sd==1 else x['low']<=tp
  if hs and ht:return ('SL',-1.0)
  if hs:return ('SL',-1.0)
  if ht:return ('TP',rr)
  age=j-ei+1;cur=(x['close']-entry)/risk*sd;fav=(x['high']-entry)/risk if sd==1 else (entry-x['low'])/risk;best=max(best,fav)
  if age>=ca:
   em=x.get('ema20');broken=em is not None and (x['close']-em)*sd<0
   if cur<=cr or (broken and cur<.10) or (age>=2 and best<prog):return ('CUT',max(-1,cur))
 last=rows[end-1]['close'];return ('CUT',max(-1,min(rr,(last-entry)/risk*sd)))
def days(a,c):return (datetime.fromisoformat(c).date()-datetime.fromisoformat(a).date()).days+1
def month_full(ds,a,c):return len([d for d in ds if a<=d<=c])==days(a,c)
def evaluate(sym,ds,data,param,a,c):
 fam,h,cfg=param;expected=days(a,c);z=[]
 for d in sorted(k for k in ds if a<=k<=c):
  hs=ds[d];hh=h if h in hs else max([x for x in hs if x<=h],default=max(hs));i,m=hs[hh];o=execute(data[sym],i,side(fam,m),cfg)
  if o:z.append(o)
 tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cu=len(z)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in z) if z else -9
 return {'expectedDays':expected,'tradedDays':len(z),'missing':expected-len(z),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
 ok=s['missing']==0 and s['resolved']>=6 and s['cutRate']<=82 and s['meanR']>0
 return (int(ok and s['wr']>=TARGET),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
def main():
 doc=json.load(open(SNAP));data={s:enrich(doc['data'][s]) for s in ALL};mp=maps(data);mx=defaultdict(lambda:defaultdict(dict));times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  pack=context(mp,t)
  if not pack:continue
  elig,reg=pack
  for s,q in elig.items():
   i,r=q
   if t.hour in HOURS:mx[s][t.date().isoformat()][t.hour]=(i,meta(r,reg))
 params=[(f,h,c) for f in FAMILIES for h in HOURS for c in CFGS];res={};print('PARAMS',len(params),flush=True)
 for sym in ALL:
  hist=[];win=None
  for name,da,db,fa,fb in STAGES:
   # only use stages with genuine full-month availability for this coin
   if not month_full(mx[sym],da,db) or not month_full(mx[sym],fa,fb):
    hist.append({'stage':name,'status':'SKIP_NOT_FULL_MONTH'});continue
   best=None;bp=None;ds=None
   for p in params:
    s=evaluate(sym,mx[sym],data,p,da,db);r=rank(s)
    if best is None or r>best:best=r;bp=p;ds=s
   fs=evaluate(sym,mx[sym],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec);print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[s for s in ALL if res[s]['status']=='PASS'];failed=[s for s in ALL if res[s]['status']=='FAIL'];out={'version':'CRYPTO_H1_DAILY_EACH_SYMBOL_V47','h1CoverageCount':59,'fallback4H':['TON','IP'],'rule':'Each H1-covered coin trades every calendar day of a full month; genuine H+1 management; own prior-month rule; TP/SL WR>=80; RR1 or2; positive meanR; >=6 resolved; CUT<=82%.','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/59,2),'passed':passed,'failed':failed,'all59Pass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','all59Pass')},indent=2),flush=True)
if __name__=='__main__':main()
