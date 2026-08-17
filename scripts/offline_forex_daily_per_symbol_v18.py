#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from pathlib import Path
import scripts.offline_forex_precision_evolver_v15 as b
import scripts.offline_forex_daily_per_symbol_v17 as m

OUT='data/offline_forex_daily_per_symbol_v18.json';TARGET=80.0
WINDOWS=m.WINDOWS;DIRS=m.DIRS
CFGS=[]
for rr in (1.0,2.0):
  rfs=(.55,.75,1.0,1.25,1.5,2.0) if rr==1.0 else (.75,1.0,1.5,2.0)
  for rf in rfs:
    for sw in (4,6,12):
      hold=18 if rr==1 else 36
      for ca,cr,cm in ((0,0,'NONE'),(1,.50,'R'),(1,.25,'R'),(1,0,'R'),(1,-.20,'EMA'),(2,.25,'R'),(2,0,'R'),(2,-.30,'EMA'),(3,-.40,'EMA')):
        CFGS.append((rr,rf,sw,hold,ca,cr,cm))

def hscore(x,f):
    a=x['meta'];side=x['side'];g3=a['g3']*side;g6=a['g6']*side;g12=a['g12']*side;g24=a['g24']*side;g72=a['g72']*side
    h1=a['h1']*side;h4=a['h4']*side;mom=a['mom']*side;dev=a['dev']*side;sess=a['sess']*side;coh=(a['coh3']+a['coh24'])/2
    if f=='FAST':return 1.8*g3+1.2*g6+.5*g12+.8*coh+.5*h1+.25*mom
    if f=='BALANCED':return 1.2*g3+g6+.8*g12+.8*g24+.3*g72+.8*coh+.45*h1+.35*h4
    if f=='TREND':return .8*g24+.5*g72+1.2*h1+1.0*h4+.7*mom+.4*sess-.2*max(dev-1.5,0)
    if f=='SESSION':return 1.0*g3+.6*g6+1.0*mom+1.1*sess+.6*h1+.3*coh
    if f=='REVERT':return .7*g24+.4*g72-1.25*dev+.6*h4+.4*coh-.2*mom
    return g3+g6+g12+g24+.5*h1+.5*h4

def select(raw,window,direction,fam):
    g=defaultdict(list)
    for x in raw:
        if x['time'].weekday()>=5 or x['time'].hour not in WINDOWS[window]:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        q=dict(x);q['score']=hscore(q,fam);g[q['day']].append(q)
    return [max(z,key=lambda q:q['score']) for _,z in sorted(g.items())]

def sm(z,exp):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=sum(x['result']=='CUT' for x in z);den=tp+sl
    return {'days':len(z),'expectedDays':exp,'coveragePct':round(100*len(z)/exp,2) if exp else 0,'tp':tp,'sl':sl,'cut':cut,'resolved':den,'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'cutRatePct':round(100*cut/len(z),2) if z else 0}

def rank(s):
    minres=max(12,math.ceil(s['expectedDays']*.20));hit=s['coveragePct']>=99.9 and s['resolved']>=minres and s['wr']>=TARGET and s['meanR']>0
    return (int(hit),s['wr']-max(0,minres-s['resolved'])*5,s['meanR'],-s['cutRatePct'],s['resolved'])

def main():
    doc=json.load(open(b.SNAP,encoding='utf-8'));data={s:b.enrich(doc['data'][s]) for s in b.PAIRS};maps,times=b.make_maps(data);raw=m.raw_candidates(data,maps,times);results={};fams=('FAST','BALANCED','TREND','SESSION','REVERT')
    for sym in b.PAIRS:
        r=[x for x in raw[sym] if '2026-05-01'<=x['day']<='2026-07-31'];exp=len(set(x['day'] for x in r));best=None;bp=None
        sels={(f,w,d):select(r,w,d,f) for f in fams for w in WINDOWS for d in DIRS}
        for key,sel in sels.items():
            if len(sel)!=exp:continue
            for cfg in CFGS:
                z=[]
                for e in sel:
                    o=m.exec_mkt(data[sym],e['i'],e['side'],cfg)
                    if o:q=dict(e);q['result'],q['r'],q['bars']=o;z.append(q)
                s=sm(z,exp);q=rank(s)
                if best is None or q>best:best=q;bp=(key,cfg,s)
                if q[0] and s['wr']>=90 and s['meanR']>.15:break
        fam,w,d=bp[0];cfg=bp[1];s=bp[2];ok=rank(s)[0]==1
        results[sym]={'status':'PASS' if ok else 'FAIL','family':fam,'window':w,'direction':d,'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingHours':cfg[2],'maxHoldH':cfg[3],'cutAfterH':cfg[4],'cutR':cfg[5],'cutMode':cfg[6]},'mayJulyDevelopment':s};print('PASS' if ok else 'FAIL',sym,fam,s,flush=True)
    passed=[x for x in b.PAIRS if results[x]['status']=='PASS'];failed=[x for x in b.PAIRS if results[x]['status']!='PASS'];ans={'version':'FOREX_DAILY_PER_SYMBOL_V18','scope':'May-Jul three-month per-pair development ceiling; one market trade each weekday','passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','passed','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
