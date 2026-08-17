#!/usr/bin/env python3
"""Offline H1 crypto backtest only. Exactly one simulated trade per calendar day."""
import json
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h
from scripts.offline_nocut_geometry_core import simulate,cfgs,stats

OUT='data/offline_crypto_h1_nocut_geometry_v65.json'; START='2026-05-01'; END='2026-07-30'; TARGET=80.0
HOURS=(0,4,8,12,16,20); FAMILIES=h.FAMILIES

def main():
    doc=json.load(open(h.SNAP,encoding='utf-8')); data={s:h.enrich(doc['data'][s]) for s in h.ALL}; mp=h.maps(data); daymap=defaultdict(lambda:defaultdict(dict))
    times=sorted(set().union(*(set(m) for m in mp.values())))
    for t in times:
        d=t.date().isoformat()
        if d<START or d>END or t.hour not in HOURS:continue
        pack=h.context(mp,t)
        if not pack:continue
        elig,reg=pack
        for sym,q in elig.items():
            i,row=q; daymap[sym][d][t.hour]=(i,h.meta(row,reg))
    expected=91; cs=cfgs(); print('V65_CONFIGS',len(cs),'EXPECTED',expected,flush=True); results={}
    for sym in h.ALL:
        best=None;bp=None;cache={}
        for fam in FAMILIES:
            for hr in HOURS:
                sig=[]
                for d in sorted(daymap[sym]):
                    if hr not in daymap[sym][d]:sig=[];break
                    i,m=daymap[sym][d][hr];sig.append((i,h.side(fam,m)))
                if len(sig)!=expected:continue
                for cfg in cs:
                    z=[]
                    for i,sd in sig:
                        key=(i,sd,cfg)
                        if key not in cache:cache[key]=simulate(data[sym],i,sd,cfg)
                        z.append(cache[key])
                    s=stats(z,expected); hit=s['trades']==expected and s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0
                    r=(int(hit),s['wrAllTrades'],s['meanRAllTrades'],-s['timeout'])
                    if best is None or r>best:best=r;bp=(fam,hr,cfg,s)
        if bp is None:
            have=len(daymap[sym]);results[sym]={'status':'FAIL','reason':'no full 91-day H1 path','availableDays':have};print('FAIL',sym,'NO_FULL',have,flush=True);continue
        fam,hr,cfg,s=bp;ok=s['wrAllTrades']>=TARGET and s['trades']==expected and s['meanRAllTrades']>0
        results[sym]={'status':'PASS' if ok else 'FAIL','style':{'profile':h.PROFILE.get(sym,'OTHER'),'family':fam,'signalHourUTC':hr,'entryMode':cfg[0],'entryParam':cfg[1],'expiryH':cfg[2],'rr':cfg[3],'riskATR':cfg[4],'maxHoldH':cfg[5]},'development':s};print('PASS' if ok else 'FAIL',sym,results[sym]['style'],s,flush=True)
    passed=[s for s in h.ALL if results[s]['status']=='PASS'];failed=[s for s in h.ALL if results[s]['status']!='PASS'];out={'version':'CRYPTO_H1_NOCUT_GEOMETRY_V65','scope':'59 H1-covered coins, May1-Jul30 exposed development ceiling; fixed unique style per coin','definition':{'cutUsed':False,'noTradeAllowed':False,'tradesPerDay':1,'rrAllowed':[1,2],'timeout':'non-win','sameBarAmbiguity':'SL','remainingSeparate':['TON','IP']},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'all59Passed':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','failed','all59Passed')},indent=2),flush=True)
if __name__=='__main__':main()
