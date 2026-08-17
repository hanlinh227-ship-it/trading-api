#!/usr/bin/env python3
"""Offline historical backtest only. Exactly one simulated trade per weekday."""
import json, datetime as dt
from collections import defaultdict
from pathlib import Path
import scripts.offline_forex_precision_evolver_v15 as b
from scripts.offline_nocut_geometry_core import simulate,cfgs,stats

OUT='data/offline_forex_nocut_geometry_v64.json'; START='2026-05-01'; END='2026-07-30'; TARGET=80.0
HOURS=(0,4,8,12,16,20)
FAMILIES=('FAST','MED','SLOW','H1','H4','MOM','REVERT','SESSION','HYBRID','CONTRA24')

def side_of(f,m):
    x={'FAST':m['g3']+.6*m['g6'],'MED':.6*m['g12']+m['g24'],'SLOW':m['g24']+.5*m['g72'],
       'H1':m['h1'],'H4':m['h4'],'MOM':m['mom'],'REVERT':-m['dev'],'SESSION':m['sess'],
       'HYBRID':.6*m['g6']+m['g24']+.45*m['h4']+.25*m['mom']+.15*m['sess'],'CONTRA24':-m['g24']}[f]
    return 1 if x>=0 else -1

def weekdays(a,z):
    x=dt.date.fromisoformat(a); e=dt.date.fromisoformat(z); n=0
    while x<=e:
        if x.weekday()<5:n+=1
        x+=dt.timedelta(days=1)
    return n

def main():
    doc=json.load(open(b.SNAP,encoding='utf-8')); data={s:b.enrich(doc['data'][s]) for s in b.PAIRS}; maps,times=b.make_maps(data)
    daymap=defaultdict(lambda:defaultdict(dict))
    for t in times:
        d=t.date().isoformat()
        if d<START or d>END or t.weekday()>=5:continue
        fp=b.factor_pack(maps,t)
        if not fp:continue
        for sym in b.PAIRS:
            i,row=maps[sym][t]
            if row.get('atr') is None or row.get('ema50') is None:continue
            _,m=b.candidate_features(sym,row,fp,1); daymap[sym][d][t.hour]=(i,m)
    expected=weekdays(START,END); cs=cfgs(); print('V64_CONFIGS',len(cs),'EXPECTED',expected,flush=True); results={}
    for sym in b.PAIRS:
        best=None; bp=None; cache={}
        for fam in FAMILIES:
            for h in HOURS:
                sig=[]
                for d in sorted(daymap[sym]):
                    if h not in daymap[sym][d]:sig=[];break
                    i,m=daymap[sym][d][h];sig.append((i,side_of(fam,m)))
                if len(sig)!=expected:continue
                for cfg in cs:
                    z=[]
                    for i,side in sig:
                        key=(i,side,cfg)
                        if key not in cache:cache[key]=simulate(data[sym],i,side,cfg)
                        z.append(cache[key])
                    s=stats(z,expected); hit=s['trades']==expected and s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0
                    r=(int(hit),s['wrAllTrades'],s['meanRAllTrades'],-s['timeout'])
                    if best is None or r>best:best=r;bp=(fam,h,cfg,s)
        if bp is None:results[sym]={'status':'FAIL','reason':'no full daily path'};print('FAIL',sym,'NO_PATH',flush=True);continue
        fam,h,cfg,s=bp;ok=s['wrAllTrades']>=TARGET and s['trades']==expected and s['meanRAllTrades']>0
        results[sym]={'status':'PASS' if ok else 'FAIL','style':{'family':fam,'signalHourUTC':h,'entryMode':cfg[0],'entryParam':cfg[1],'expiryBars':cfg[2],'rr':cfg[3],'riskATR':cfg[4],'maxHoldH':cfg[5]},'development':s}
        print('PASS' if ok else 'FAIL',sym,results[sym]['style'],s,flush=True)
    passed=[s for s in b.PAIRS if results[s]['status']=='PASS']; failed=[s for s in b.PAIRS if results[s]['status']!='PASS']
    out={'version':'FOREX_NOCUT_GEOMETRY_V64','scope':'May1-Jul30 exposed development ceiling; fixed unique style per pair','definition':{'cutUsed':False,'noTradeAllowed':False,'tradesPerDay':1,'rrAllowed':[1,2],'timeout':'non-win','sameBarAmbiguity':'SL'},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
