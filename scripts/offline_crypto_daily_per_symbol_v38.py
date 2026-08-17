#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_daily_per_symbol_v37 as b
import scripts.offline_crypto_precision_evolver_v36 as v
from scripts.offline_crypto_v28_separate import PROFILE

OUT='data/offline_crypto_daily_per_symbol_v38.json';TARGET=80.0
FAILED='ETH SOL HYPE TRX XRP AAVE ADA ALGO ATOM AVAX CRV DOT ETC FLOKI HBAR JTO LDO LINK LTC MOODENG NEAR ONDO ORDI PNUT POPCAT STX SUI TAO TIA TRUMP UNI AIXBT ASTER IP PUMP VIRTUAL XPL'.split()
WINDOWS=b.WINDOWS;DIRS=b.DIRS
CFGS=[]
for rr in (1.0,2.0):
  for rf in (.55,.75,1.0,1.25,1.5,2.0):
    for sw in (3,5,8):
      hold=6 if rr==1.0 else 10
      CFGS.append((rr,rf,sw,hold,0,0,'NONE'))
      for ca in (1,2):
        for cr in (-.25,0,.25,.50,.75):CFGS.append((rr,rf,sw,hold,ca,cr,'R'))
        for cr in (-.25,0,.25):CFGS.append((rr,rf,sw,hold,ca,cr,'EMA'))

def heuristic(x,fam):
    m=x['meta'];side=x['side']
    h4=m['h4']*side;d1=m['d1']*side;mom=m['mom']*side;dev=m['dev']*side;rel24=m['rel24']*side;rel72=m['rel72']*side
    breadth=m['breadth'] if side==1 else 1-m['breadth'];btc=(m['btc24']*side)*20
    if fam=='TREND':return 1.4*h4+1.0*d1+.6*mom+.5*breadth+.15*m['adx']-.3*max(dev-1.5,0)
    if fam=='RELATIVE':return 1.4*rel24*20+.8*rel72*10+.7*h4+.5*d1+.35*breadth
    if fam=='BREAKOUT':return 1.2*mom+.8*h4+.5*d1+.4*btc+.25*m['adx']-.15*abs(dev)
    if fam=='REVERT':return -1.25*dev+.55*d1+.35*h4+.25*breadth-.15*mom
    return h4+d1+mom+.4*breadth+.4*rel24*20

def select(raw,window,direction,fam):
    g=defaultdict(list)
    for x in raw:
        if x['time'].hour not in WINDOWS[window]:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        q=dict(x);q['score']=heuristic(q,fam);g[q['day']].append(q)
    return [max(z,key=lambda q:q['score']) for _,z in sorted(g.items())]

def sm(z,expected):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=sum(x['result']=='CUT' for x in z);den=tp+sl
    return {'days':len(z),'eligibleDays':expected,'coveragePct':round(100*len(z)/expected,2) if expected else 0,'tp':tp,'sl':sl,'cut':cut,'resolved':den,'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'cutRatePct':round(100*cut/len(z),2) if z else 0}

def rank(s):
    minres=max(12,math.ceil(s['eligibleDays']*.20));hit=s['coveragePct']>=99.9 and s['resolved']>=minres and s['wr']>=TARGET and s['meanR']>0
    return (int(hit),s['wr']-max(0,minres-s['resolved'])*5,s['meanR'],-s['cutRatePct'],s['resolved'])

def main():
    doc=json.load(open(v.SNAP,encoding='utf-8'));data={s:v.enrich(doc['data'][s]) for s in v.SYMBOLS};mp=v.maps(data);raw=b.build_raw(data,mp);results={}
    fams=('TREND','RELATIVE','BREAKOUT','REVERT','BALANCED')
    for sym in FAILED:
        r=[x for x in raw.get(sym,[]) if '2026-05-01'<=x['day']<='2026-07-31'];expected=len(set(x['day'] for x in r));best=None;bp=None
        if expected<20:
            results[sym]={'status':'NO_HISTORY','eligibleDays':expected};print('NO_HISTORY',sym,expected,flush=True);continue
        selections={}
        for fam in fams:
          for w in WINDOWS:
           for d in DIRS:selections[(fam,w,d)]=select(r,w,d,fam)
        for key,sel in selections.items():
          if len(sel)!=expected:continue
          for cfg in CFGS:
            z=b.apply_cfg(sel,data[sym],cfg);s=sm(z,expected);q=rank(s)
            if best is None or q>best:best=q;bp=(key,cfg,s)
            if q[0] and s['wr']>=90 and s['meanR']>.15:break
        fam,w,d=bp[0];cfg=bp[1];s=bp[2];ok=rank(s)[0]==1
        results[sym]={'status':'PASS' if ok else 'FAIL','profile':PROFILE.get(sym,'OTHER'),'family':fam,'window':w,'direction':d,'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingBars4H':cfg[2],'maxHoldBars4H':cfg[3],'cutAfterBars4H':cfg[4],'cutR':cfg[5],'cutMode':cfg[6]},'mayJulyDevelopment':s};print('PASS' if ok else 'FAIL',sym,fam,s,flush=True)
    passed=[s for s in FAILED if results[s]['status']=='PASS'];failed=[s for s in FAILED if results[s]['status']!='PASS'];ans={'version':'CRYPTO_DAILY_PER_SYMBOL_V38','scope':'development optimizer for V37 failures; May-Jul exposed, not fresh holdout','passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allFailedResolved':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','passed','failed','allFailedResolved')},indent=2),flush=True)
if __name__=='__main__':main()
