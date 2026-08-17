#!/usr/bin/env python3
"""Offline H1 development search. One trade/day, no CUT, RR1. Coordinate refinement per coin."""
import json
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h
from scripts.offline_crypto_v28_separate import PROFILE
from scripts.offline_nocut_geometry_core import simulate,stats

OUT='data/offline_crypto_h1_coordinate_v69.json';START='2026-05-01';END='2026-07-30';TARGET=80.0
FAMS=h.FAMILIES;HOURS=range(24);EXPECTED=91
OFFS=(.30,.40,.50,.60,.70,.80,.90,1.00,1.10,1.20,1.35,1.50)
RFS=(.30,.40,.50,.60,.70,.80,.90,1.00,1.10,1.20,1.35,1.50)
EXPS=(1,2,3,4,5,6,8);HOLDS=(6,8,10,12,14,16,18,20,24)

def run_style(sym,data,dm,fam,hr,cfg,cache):
 z=[]
 for d in sorted(dm[sym]):
  q=dm[sym][d].get(hr)
  if q is None:return None
  i,m=q;sd=h.side(fam,m);k=(i,sd,cfg)
  if k not in cache:cache[k]=simulate(data[sym],i,sd,cfg)
  z.append(cache[k])
 if len(z)!=EXPECTED:return None
 return stats(z,EXPECTED)

def better(a,b):
 if b is None:return True
 return (a['wrAllTrades'],a['meanRAllTrades'],-a['timeout'])>(b['wrAllTrades'],b['meanRAllTrades'],-b['timeout'])

def main():
 doc=json.load(open(h.SNAP,encoding='utf-8'));data={s:h.enrich(doc['data'][s]) for s in h.ALL};mp=h.maps(data);dm=defaultdict(lambda:defaultdict(dict));times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<START or d>END:continue
  p=h.context(mp,t)
  if not p:continue
  elig,reg=p
  for sym,q in elig.items():dm[sym][d][t.hour]=(q[0],h.meta(q[1],reg))
 results={}
 for sym in h.ALL:
  if len(dm[sym])!=EXPECTED:results[sym]={'status':'FAIL','reason':'incomplete H1 days','availableDays':len(dm[sym])};print('NO_FULL',sym,len(dm[sym]),flush=True);continue
  cache={};cfg=('DUAL_FADE',.75,4,1.0,.75,12);bestS=None;fam0=None;hr0=None
  # pass 1: family/hour
  for fam in FAMS:
   for hr in HOURS:
    s=run_style(sym,data,dm,fam,hr,cfg,cache)
    if s and better(s,bestS):bestS=s;fam0=fam;hr0=hr
  # pass 2: offset/risk
  bestCfg=cfg
  for off in OFFS:
   for rf in RFS:
    c=('DUAL_FADE',off,4,1.0,rf,12);s=run_style(sym,data,dm,fam0,hr0,c,cache)
    if s and better(s,bestS):bestS=s;bestCfg=c
  # pass 3: expiry/hold using best offset/risk
  off=bestCfg[1];rf=bestCfg[4]
  for ex in EXPS:
   for hold in HOLDS:
    c=('DUAL_FADE',off,ex,1.0,rf,hold);s=run_style(sym,data,dm,fam0,hr0,c,cache)
    if s and better(s,bestS):bestS=s;bestCfg=c
  # pass 4: family/hour again
  for fam in FAMS:
   for hr in HOURS:
    s=run_style(sym,data,dm,fam,hr,bestCfg,cache)
    if s and better(s,bestS):bestS=s;fam0=fam;hr0=hr
  # pass 5: local fine offset/risk
  bo,br=bestCfg[1],bestCfg[4]
  offs=sorted(set(round(max(.20,min(1.70,bo+x)),2) for x in (-.15,-.10,-.05,0,.05,.10,.15)))
  rfs=sorted(set(round(max(.20,min(1.70,br+x)),2) for x in (-.15,-.10,-.05,0,.05,.10,.15)))
  for off in offs:
   for rf in rfs:
    c=('DUAL_FADE',off,bestCfg[2],1.0,rf,bestCfg[5]);s=run_style(sym,data,dm,fam0,hr0,c,cache)
    if s and better(s,bestS):bestS=s;bestCfg=c
  ok=bestS['wrAllTrades']>=TARGET and bestS['trades']==EXPECTED and bestS['meanRAllTrades']>0
  style={'profile':PROFILE.get(sym,'OTHER'),'family':fam0,'signalHourUTC':hr0,'entryMode':'DUAL_FADE','offsetATR':bestCfg[1],'expiryH':bestCfg[2],'rr':1.0,'riskATR':bestCfg[4],'maxHoldH':bestCfg[5]}
  results[sym]={'status':'PASS' if ok else 'FAIL','style':style,'development':bestS};print('PASS' if ok else 'FAIL',sym,style,bestS,flush=True)
 passed=[s for s in h.ALL if results[s]['status']=='PASS'];failed=[s for s in h.ALL if results[s]['status']!='PASS'];out={'version':'CRYPTO_H1_COORDINATE_V69','scope':'59 H1 coins May1-Jul30 exposed development; coordinate-refined unique dual-fade style','definition':{'cutUsed':False,'noTradeAllowed':False,'tradesPerDay':1,'rr':1.0,'timeout':'non-win','sameBar':'SL'},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'all59Passed':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','failed','all59Passed')},indent=2),flush=True)
if __name__=='__main__':main()
