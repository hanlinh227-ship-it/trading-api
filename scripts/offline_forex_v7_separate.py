#!/usr/bin/env python3
import json, os, math, statistics, itertools
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx


def prep(rows):
    out=[]
    for r in rows:
        if r['rr'] < 1.0: continue
        z=dict(r)
        z['targetRR']=min(r['rr'],1.5)
        z['targetR']=z['targetRR'] if r['r']>0 else -1.0
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['targetR']>0 for r in rows); l=sum(r['targetR']<0 for r in rows); n=w+l
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),
            'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if n<=0:return 0.0
    p=w/n; den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def day_state(rows):
    by=defaultdict(list)
    for r in rows:by[r['date']].append(r)
    states={}
    for d,x in by.items():
        buy=[r for r in x if r['side']=='BUY']; sell=[r for r in x if r['side']=='SELL']
        aligned=sum((r['side']=='BUY' and r['h1']>0) or (r['side']=='SELL' and r['h1']<0) for r in x)/max(1,len(x))
        h4aligned=sum((r['side']=='BUY' and r['h4']>0) or (r['side']=='SELL' and r['h4']<0) for r in x)/max(1,len(x))
        states[d]={
          'buyShare':len(buy)/max(1,len(x)),
          'h1AlignShare':aligned,'h4AlignShare':h4aligned,
          'medianScore':statistics.median(r['score'] for r in x),
          'medianAdx':statistics.median(r['adx'] for r in x),
          'medianCoh3':statistics.median(r['coh3'] for r in x),
          'medianImpulse':statistics.median(r['impulse'] for r in x),
          'regimeShare':sum(r['mode']=='REGIME_24H' for r in x)/max(1,len(x))
        }
    return states

def candidates():
    # Forex-specific: day common-factor gate + V5/F8 trade state.
    for p in itertools.product(
      ('ANY','BUY','SELL'),(0,.5,1,1.5,2),(0,15,20,25),(0,.35,.55,.7),(0,2,3,4),('ANY','H1','H1H4'),
      (0,.55,.65,.75),(0,.55,.65,.75),(0,15,20,25),(0,.35,.5,.6),('ANY','LOW_REGIME','HIGH_REGIME')):
        yield p

def passed(r,p,states):
    side,score,adx,coh,imp,align,dha,dh4,dadx,dcoh,dreg=p
    if side!='ANY' and r['side']!=side:return False
    if r['score']<score or r['adx']<adx or r['coh3']<coh or r['impulse']<imp:return False
    sg=1 if r['side']=='BUY' else -1
    if align=='H1' and r['h1']!=sg:return False
    if align=='H1H4' and not (r['h1']==sg and r['h4']==sg):return False
    s=states[r['date']]
    if dha and s['h1AlignShare']<dha:return False
    if dh4 and s['h4AlignShare']<dh4:return False
    if dadx and s['medianAdx']<dadx:return False
    if dcoh and s['medianCoh3']<dcoh:return False
    if dreg=='LOW_REGIME' and s['regimeShare']>.35:return False
    if dreg=='HIGH_REGIME' and s['regimeShare']<.35:return False
    return True

def choose(dev,states):
    best=None
    for p in candidates():
        z=[r for r in dev if passed(r,p,states)]
        s=sm(z)
        if s['n']<24 or s['dates']<4:continue
        by=[]
        for d in sorted(set(r['date'] for r in z)):
            q=sm([r for r in z if r['date']==d])
            if q['n']>=3:by.append(q['wr'])
        med=statistics.median(by) if by else s['wr']; pos=sum(v>=50 for v in by)/max(1,len(by))
        lower=100*wilson(s['wins'],s['n'])
        # Prefer lower-bound + day robustness before raw WR.
        score=(lower,pos,med,s['meanR'],s['wr'],min(s['n'],100))
        if best is None or score>best[0]:best=(score,p,s,{'medianDayWR':round(med,2),'positiveDayRate':round(pos,3),'wilsonLB':round(lower,2)})
    return best

def main():
    rows=prep(extract_fx()); dates=sorted(set(r['date'] for r in rows)); cut=len(dates)//2
    devdates=dates[:cut]; valdates=dates[cut:]
    dev=[r for r in rows if r['date'] in devdates]; val=[r for r in rows if r['date'] in valdates]
    states=day_state(rows); best=choose(dev,states)
    ds=[r for r in dev if best and passed(r,best[1],states)]
    vs=[r for r in val if best and passed(r,best[1],states)]
    out={'version':'FOREX V7 SEPARATE FACTOR-DAY-RISK','providerCreditsUsed':0,
         'method':'Forex-only continuation of F8/V5. Uses trade-time F8 features plus cross-pair day common-factor state; one rule frozen on first chronological half and applied unchanged to later half.',
         'devDates':devdates,'validationDates':valdates,'baselineValidation':sm(val),
         'rule':best[1] if best else None,'development':sm(ds),'developmentRobustness':best[3] if best else None,
         'validation':sm(vs),'targetMet':False}
    v=out['validation'];out['targetMet']=bool(v.get('n',0)>=20 and (v.get('wr') or 0)>=80 and 1.0<=(v.get('avgRR') or 0)<=1.5 and v.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v7_separate.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
