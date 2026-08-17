#!/usr/bin/env python3
"""Offline refinement: keep V65 style, search only signal hour 0..23."""
import json
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h
from scripts.offline_nocut_geometry_core import simulate,stats

BASE='data/offline_crypto_h1_nocut_geometry_v65.json';OUT='data/offline_crypto_h1_hour_refine_v68.json';START='2026-05-01';END='2026-07-30';TARGET=80.0

def main():
 base=json.load(open(BASE));doc=json.load(open(h.SNAP,encoding='utf-8'));data={s:h.enrich(doc['data'][s]) for s in h.ALL};mp=h.maps(data);dm=defaultdict(lambda:defaultdict(dict));times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<START or d>END:continue
  p=h.context(mp,t)
  if not p:continue
  elig,reg=p
  for sym,q in elig.items():dm[sym][d][t.hour]=(q[0],h.meta(q[1],reg))
 res={}
 for sym in h.ALL:
  old=base['results'][sym]
  if old.get('status')=='PASS':res[sym]={'status':'PASS','source':'V65','style':old['style'],'development':old['development']};print('KEEP_PASS',sym,old['development'],flush=True);continue
  if 'style' not in old:res[sym]=old;print('NO_STYLE',sym,old,flush=True);continue
  st=old['style'];cfg=(st['entryMode'],st['entryParam'],st['expiryH'],st['rr'],st['riskATR'],st['maxHoldH']);fam=st['family'];best=None;bp=None
  for hr in range(24):
   z=[];ok=True
   for d in sorted(dm[sym]):
    if hr not in dm[sym][d]:ok=False;break
    i,m=dm[sym][d][hr];z.append(simulate(data[sym],i,h.side(fam,m),cfg))
   if not ok or len(z)!=91:continue
   s=stats(z,91);r=(s['wrAllTrades'],s['meanRAllTrades'],-s['timeout'])
   if best is None or r>best:best=r;bp=(hr,s)
  if bp is None:res[sym]={'status':'FAIL','reason':'no full hour path'};print('FAIL',sym,'NO_HOUR',flush=True);continue
  hr,s=bp;sty=dict(st);sty['signalHourUTC']=hr;ok=s['wrAllTrades']>=TARGET;res[sym]={'status':'PASS' if ok else 'FAIL','source':'V68','style':sty,'development':s};print('PASS' if ok else 'FAIL',sym,sty,s,flush=True)
 passed=[s for s in h.ALL if res[s]['status']=='PASS'];failed=[s for s in h.ALL if res[s]['status']!='PASS'];out={'version':'CRYPTO_H1_HOUR_REFINE_V68','parent':'V65','scope':'same V65 per-coin style, only signal hour refined across all 24 H1 hours','passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'all59Passed':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','failed','all59Passed')},indent=2),flush=True)
if __name__=='__main__':main()
