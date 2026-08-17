#!/usr/bin/env python3
"""Offline refinement for V64 failures only; no live execution."""
import json, datetime as dt
from collections import defaultdict
from pathlib import Path
import scripts.offline_forex_precision_evolver_v15 as b
from scripts.offline_nocut_geometry_core import simulate,stats

OUT='data/offline_forex_nocut_refine_v66.json';START='2026-05-01';END='2026-07-30';TARGET=80.0
FAILED=['USDJPY','AUDUSD','NZDUSD','EURAUD','EURCAD','GBPJPY','GBPAUD','GBPNZD','AUDCAD','NZDJPY','CADJPY']
SEED={
'USDJPY':(.50,2,.50),'AUDUSD':(.75,4,.50),'NZDUSD':(1.0,4,.75),'EURAUD':(.50,4,.50),'EURCAD':(1.0,4,1.0),
'GBPJPY':(.75,2,.75),'GBPAUD':(1.0,4,.75),'GBPNZD':(1.0,2,.75),'AUDCAD':(.50,2,.50),'NZDJPY':(.75,2,.75),'CADJPY':(1.0,4,1.0)}
FAMILIES=('FAST','MED','SLOW','H1','H4','MOM','REVERT','SESSION','HYBRID','CONTRA24')

def side_of(f,m):
 x={'FAST':m['g3']+.6*m['g6'],'MED':.6*m['g12']+m['g24'],'SLOW':m['g24']+.5*m['g72'],'H1':m['h1'],'H4':m['h4'],'MOM':m['mom'],'REVERT':-m['dev'],'SESSION':m['sess'],'HYBRID':.6*m['g6']+m['g24']+.45*m['h4']+.25*m['mom']+.15*m['sess'],'CONTRA24':-m['g24']}[f]
 return 1 if x>=0 else -1

def vals(center,steps,lo,hi):return sorted(set(round(max(lo,min(hi,center+x)),2) for x in steps))
def configs(sym):
 off,ex,rf=SEED[sym];offs=vals(off,(-.20,-.10,-.05,0,.05,.10,.20),.25,1.25);rfs=vals(rf,(-.20,-.10,-.05,0,.05,.10,.20),.25,1.25);exs=sorted(set(max(1,min(6,ex+x)) for x in (-2,-1,0,1,2)));holds=(8,10,12,14,16,18)
 return [('DUAL_FADE',o,e,1.0,r,h) for o in offs for e in exs for r in rfs for h in holds]
def weekdays():
 x=dt.date.fromisoformat(START);e=dt.date.fromisoformat(END);n=0
 while x<=e:
  if x.weekday()<5:n+=1
  x+=dt.timedelta(days=1)
 return n

def main():
 doc=json.load(open(b.SNAP,encoding='utf-8'));data={s:b.enrich(doc['data'][s]) for s in b.PAIRS};maps={s:{r['dt']:(i,r) for i,r in enumerate(data[s])} for s in b.PAIRS};common=sorted(set.intersection(*(set(m) for m in maps.values())));dm=defaultdict(lambda:defaultdict(dict))
 for t in common:
  d=t.date().isoformat()
  if d<START or d>END or t.weekday()>=5:continue
  fp=b.factor_pack(maps,t)
  if not fp:continue
  for sym in FAILED:
   i,row=maps[sym][t]
   if row.get('atr') is None or row.get('ema50') is None:continue
   _,m=b.candidate_features(sym,row,fp,1);dm[sym][d][t.hour]=(i,m)
 exp=weekdays();res={}
 for sym in FAILED:
  cs=configs(sym);print('SEARCH',sym,len(cs),flush=True);best=None;bp=None;cache={}
  for fam in FAMILIES:
   for hr in range(24):
    sig=[]
    for d in sorted(dm[sym]):
     if hr not in dm[sym][d]:sig=[];break
     i,m=dm[sym][d][hr];sig.append((i,side_of(fam,m)))
    if len(sig)!=exp:continue
    for cfg in cs:
     z=[]
     for i,sd in sig:
      k=(i,sd,cfg)
      if k not in cache:cache[k]=simulate(data[sym],i,sd,cfg)
      z.append(cache[k])
     s=stats(z,exp);hit=s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0 and s['trades']==exp;r=(int(hit),s['wrAllTrades'],s['meanRAllTrades'],-s['timeout'])
     if best is None or r>best:best=r;bp=(fam,hr,cfg,s)
  if bp is None:res[sym]={'status':'FAIL','reason':'no path'};continue
  fam,hr,cfg,s=bp;ok=s['wrAllTrades']>=TARGET;res[sym]={'status':'PASS' if ok else 'FAIL','style':{'family':fam,'signalHourUTC':hr,'entryMode':'DUAL_FADE','offsetATR':cfg[1],'expiryH':cfg[2],'rr':1.0,'riskATR':cfg[4],'maxHoldH':cfg[5]},'development':s};print('PASS' if ok else 'FAIL',sym,res[sym]['style'],s,flush=True)
 passed=[s for s in FAILED if res[s]['status']=='PASS'];failed=[s for s in FAILED if res[s]['status']!='PASS'];out={'version':'FOREX_NOCUT_REFINE_V66','parent':'V64','scope':'targeted exposed development refinement of 11 V64 failures using all H1 signal hours','passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'all11Passed':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','failed','all11Passed')},indent=2),flush=True)
if __name__=='__main__':main()
