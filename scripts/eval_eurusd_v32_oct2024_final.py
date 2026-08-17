#!/usr/bin/env python3
import json,statistics
from datetime import datetime,timedelta,timezone
from pathlib import Path
import scripts.offline_forex_eurusd_eurnzd_v28_special as v

SNAP='data/provider_snapshots/eurusd_h1_oct2024_final.json'
OUT='data/eurusd_v32_oct2024_final.json'
PARAM=('BREAKOUT',8,1.0,3.0,12,'HYBRID',0.7,3,3,-0.25,0.25)
A='2024-10-01';B='2024-10-31'

def weekdays(a,b):
 x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(b).date();z=[]
 while x<=y:
  if x.weekday()<5:z.append(x.isoformat())
  x+=timedelta(days=1)
 return z

def main():
 doc=json.load(open(SNAP,encoding='utf-8'))
 rows=v.enrich(doc['data']['EURUSD']);idx={r['dt']:(i,r) for i,r in enumerate(rows)};trades=[];missing=[]
 for d in weekdays(A,B):
  t=datetime.fromisoformat(d).replace(tzinfo=timezone.utc)+timedelta(hours=8);q=idx.get(t)
  if not q:missing.append(d);continue
  i,r=q
  if r.get('ema50') is None or r.get('mom24') is None:missing.append(d);continue
  sd=v.side('BREAKOUT',r,rows,i);o=v.execute(rows,i,sd,PARAM)
  if o is None:missing.append(d);continue
  trades.append({'day':d,'side':'BUY' if sd==1 else 'SELL','result':o[0],'r':o[1]})
 tp=sum(x['result']=='TP' for x in trades);sl=sum(x['result']=='SL' for x in trades);cut=len(trades)-tp-sl;resolved=tp+sl;wr=100*tp/resolved if resolved else 0;mean=statistics.mean(x['r'] for x in trades) if trades else -9
 s={'expectedDays':len(weekdays(A,B)),'tradedDays':len(trades),'missingDays':missing,'tp':tp,'sl':sl,'cut':cut,'resolved':resolved,'wr':round(wr,2),'cutRate':round(100*cut/len(trades),2) if trades else 100,'meanR':round(mean,3),'plannedRR':1.0}
 passed=(not missing and resolved>=5 and wr>=80 and mean>0)
 out={'version':'EURUSD_V32_OCT2024_FINAL','lockedCheckpoint':'docs/checkpoints/FOREX_EURUSD_V32_PRE_2024_LOCK.md','snapshot':SNAP,'parameters':PARAM,'summary':s,'trades':trades,'finalTargetMet':passed}
 Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print(json.dumps(out,indent=2))
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
