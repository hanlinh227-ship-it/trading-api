#!/usr/bin/env python3
import json, os, math, statistics, itertools
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx

def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1:continue
        z=dict(r);z['targetRR']=min(r['rr'],1.5);z['y']=1 if r['r']>0 else 0;z['targetR']=z['targetRR'] if z['y'] else -1
        sg=1 if r['side']=='BUY' else -1;z['h1Align']=r['h1']==sg;z['h4Align']=r['h4']==sg
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    n=len(rows);w=sum(r['y'] for r in rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if not n:return 0
    p=w/n;den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def candidates():
    return itertools.product((0,.5,1,1.5,2.5),(0,15,20,25,30),(0,.35,.55,.7),(0,2,3,4),('H1','H1H4'),(0,.6,1.0,1.4),('ANY','IMPULSE_3H','REGIME_24H'),(0,.2,.35,.5))

def passed(r,p,side):
    sc,adx,coh,imp,align,maxdev,mode,minfq=p
    if r['side']!=side:return False
    if r['score']<sc or r['adx']<adx or r['coh3']<coh or r['impulse']<imp or r['fq3']<minfq:return False
    if align=='H1' and not r['h1Align']:return False
    if align=='H1H4' and not (r['h1Align'] and r['h4Align']):return False
    if maxdev and r['dev']>maxdev:return False
    if mode!='ANY' and r['mode']!=mode:return False
    return True

def choose(dev,side):
    best=None
    for p in candidates():
        z=[r for r in dev if passed(r,p,side)];s=sm(z)
        if s['n']<10 or s['dates']<3:continue
        lb=100*wilson(s['wins'],s['n']);score=(1 if s['wr']>=80 else 0,lb,s['wr'],s['meanR'],min(s['n'],30))
        if best is None or score>best[0]:best=(score,p,s)
    # Disable branch unless it is actually promising in development.
    if not best or best[2]['wr']<65 or best[2]['meanR']<=.25:return None
    return best

def main():
    rows=prep(extract_fx());dates=sorted(set(r['date'] for r in rows));cut=len(dates)//2;devdates=dates[:cut];valdates=dates[cut:]
    dev=[r for r in rows if r['date'] in devdates];val=[r for r in rows if r['date'] in valdates]
    branches={};selected=[]
    for side in ('BUY','SELL'):
        b=choose(dev,side);v=[r for r in val if b and passed(r,b[1],side)];selected+=v
        branches[side]={'rule':b[1] if b else None,'development':b[2] if b else None,'validation':sm(v),'enabled':bool(b)}
    res=sm(selected)
    out={'version':'FOREX V14 INDEPENDENT BUY SELL','providerCreditsUsed':0,'method':'Forex-only. BUY and SELL entry branches are optimized independently on the first chronological half; a weak side is disabled. No symmetric inversion assumption and no crypto features.',
      'devDates':devdates,'validationDates':valdates,'branches':branches,'validationCombined':res,
      'targetMet':bool(res.get('n',0)>=20 and res.get('wr',0)>=80 and 1<=res.get('avgRR',0)<=1.5 and res.get('meanR',-9)>0)}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v14_dual_side.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
