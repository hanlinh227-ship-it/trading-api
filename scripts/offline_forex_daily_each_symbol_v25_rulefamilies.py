#!/usr/bin/env python3
import json,math,statistics
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
import scripts.offline_forex_precision_evolver_v15 as b
MAIN='data/provider_snapshots/forex_h1_feb_jul_2026.json';BUF='data/provider_snapshots/forex_h1_aug1_8_2026_final1.json';OUT='data/offline_forex_daily_each_symbol_v25_rulefamilies.json';TARGET=80.0
STAGES=[('APR','2026-03-01','2026-03-31','2026-04-01','2026-04-30'),('MAY','2026-04-01','2026-04-30','2026-05-01','2026-05-31'),('JUN','2026-05-01','2026-05-31','2026-06-01','2026-06-30'),('JUL','2026-06-01','2026-06-30','2026-07-01','2026-07-31')]
FAMILIES=('FACTOR','H4TREND','SESSION','MEANREV','IMPULSE','REGIME','H1TREND')
HOURS=(0,4,8,12,16,20);RRS=(1.0,2.0);RFS=(.65,.85,1.1,1.4);SWS=(6,12);CUTS=((1,-.10),(1,.0),(2,-.20),(2,-.10),(3,-.30))

def load():
 a=json.load(open(MAIN));z=json.load(open(BUF));out={}
 for p in b.PAIRS:
  d={x[0]:x for x in a['data'][p]};d.update({x[0]:x for x in z['data'][p]});out[p]=[d[k] for k in sorted(d)]
 return out

def side_for(fam,meta):
 if fam=='FACTOR':x=meta['g3']*1.4+meta['g6']+meta['g24']*.8
 elif fam=='H4TREND':return meta['h4'] if meta['h4'] else (meta['h1'] or 1)
 elif fam=='H1TREND':return meta['h1'] or (1 if meta['g3']>=0 else -1)
 elif fam=='SESSION':x=meta['sess']
 elif fam=='MEANREV':return -1 if meta['dev']>0 else 1
 elif fam=='IMPULSE':x=meta['g3']*1.8+meta['g6']*.8-meta['g24']*.2
 else:x=meta['g24']+meta['g72']*.7
 return 1 if x>=0 else -1

def trade(rows,i,side,rr,rf,sw,cut_age,cut_r):
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);risk=max(rf*atr,(entry-swing if side==1 else swing-entry)+.08*atr);sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+(24 if rr==1 else 36));best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return 'SL',-1.0
  if hs:return 'SL',-1.0
  if ht:return 'TP',rr
  age=j-ei+1;cur=(x['close']-entry)/risk*side;fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;best=max(best,fav)
  if age>=cut_age:
   em=x.get('ema20');broken=em is not None and (x['close']-em)*side<0
   if cur<=cut_r or (broken and cur<.10) or (age>=2 and best<.10):return 'CUT',max(-1,cur)
 last=rows[end-1]['close'];return 'CUT',max(-1,min(rr,(last-entry)/risk*side))

def build(data,maps,times):
 out=defaultdict(lambda:defaultdict(dict))
 for t in times:
  fp=b.factor_pack(maps,t)
  if not fp:continue
  for p in b.PAIRS:
   i,r=maps[p][t]
   if r.get('adx') is None or r.get('ema50') is None:continue
   _,meta=b.candidate_features(p,r,fp,1)
   out[p][t.date().isoformat()][t.hour]=(i,meta)
 return out

def weekdays(a,c):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();n=0
 while x<=y:
  if x.weekday()<5:n+=1
  x+=timedelta(days=1)
 return n

def evaluate(sym,days,data,par,a,c):
 fam,hour,rr,rf,sw,ca,cr=par;exp=weekdays(a,c);rows=[]
 for d in sorted(k for k in days if a<=k<=c):
  if datetime.fromisoformat(d).weekday()>=5:continue
  hours=days[d];h=hour if hour in hours else (max([x for x in hours if x<=hour],default=max(hours)))
  i,meta=hours[h];side=side_for(fam,meta);o=trade(data[sym],i,side,rr,rf,sw,ca,cr)
  if o:rows.append(o)
 tp=sum(x[0]=='TP' for x in rows);sl=sum(x[0]=='SL' for x in rows);cu=len(rows)-tp-sl;res=tp+sl;wr=100*tp/res if res else 0;mean=statistics.mean(x[1] for x in rows) if rows else -9
 return {'expectedDays':exp,'tradedDays':len(rows),'missing':exp-len(rows),'tp':tp,'sl':sl,'cut':cu,'resolved':res,'wr':round(wr,2),'cutRate':round(100*cu/len(rows),2) if rows else 100,'meanR':round(mean,3)}

def rank(s):
 ok=s['missing']==0 and s['resolved']>=6 and s['cutRate']<=75 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],s['resolved'],-s['cutRate'])

def params():
 for f in FAMILIES:
  for h in HOURS:
   for rr in RRS:
    for rf in RFS:
     for sw in SWS:
      for ca,cr in CUTS:yield(f,h,rr,rf,sw,ca,cr)

def main():
 raw=load();data={p:b.enrich(raw[p]) for p in b.PAIRS};maps,times=b.make_maps(data);matrix=build(data,maps,times);res={}
 ps=list(params())
 for sym in b.PAIRS:
  hist=[];win=None
  for name,da,db,fa,fb in STAGES:
   best=None;bp=None;bs=None
   for p in ps:
    s=evaluate(sym,matrix[sym],data,p,da,db);r=rank(s)
    if best is None or r>best:best=r;bp=p;bs=s
   fs=evaluate(sym,matrix[sym],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'dev':bs,'final':fs,'pass':ok};hist.append(rec);print(sym,name,bp,fs,'PASS' if ok else 'FAIL',flush=True)
   if ok:win=rec;break
  res[sym]={'status':'PASS' if win else 'FAIL','frozen':win,'history':hist}
 passed=[p for p in b.PAIRS if res[p]['status']=='PASS'];failed=[p for p in b.PAIRS if res[p]['status']=='FAIL'];out={'version':'FOREX_DAILY_EACH_SYMBOL_V25_RULEFAMILIES','target':'Each pair one weekday trade; own rule family; TP/SL WR>=80; RR1 or2; CUT<=75; positive meanR','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/28,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
