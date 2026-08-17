#!/usr/bin/env python3
import json, os, statistics, itertools
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx


def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0:continue
        z=dict(r);z['targetRR']=min(r['rr'],1.5);z['targetR']=z['targetRR'] if r['r']>0 else -1.0
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['targetR']>0 for r in rows);l=sum(r['targetR']<0 for r in rows);n=w+l
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def post(xs,parent,alpha):
    w=sum(r['targetR']>0 for r in xs);n=len(xs)
    return (w+alpha*parent)/(n+alpha)

def priors(train):
    gs=sm(train);gp=(gs.get('wins',0)+4)/(max(1,gs.get('n',0))+8)
    groups=defaultdict(list);pairs=defaultdict(list);ps=defaultdict(list)
    for r in train:
        groups[r['group']].append(r);pairs[r['symbol']].append(r);ps[(r['symbol'],r['side'])].append(r)
    g={k:post(v,gp,8) for k,v in groups.items()}
    p={k:post(v,g.get(v[0]['group'],gp),6) for k,v in pairs.items()}
    s={k:post(v,p.get(k[0],gp),4) for k,v in ps.items()}
    return gp,g,p,s

def conf(r,pr):
    gp,g,p,s=pr;sg=1 if r['side']=='BUY' else -1
    prior=.50*s.get((r['symbol'],r['side']),p.get(r['symbol'],gp))+.30*p.get(r['symbol'],gp)+.20*g.get(r['group'],gp)
    q=0.0
    q += .035*min(30,r['adx'])
    q += .065*min(4,r['impulse'])
    q += .10*min(1,r['coh3'])
    q += .06*min(1,r['coh24'])
    q += .09 if r['h1']==sg else -.12
    q += .05 if r['h4']==sg else -.04
    q += .025*min(2,r['score'])
    if r['dev']>1.2:q-=.06
    return prior+q

PARAMS=[(th,k,buyonly) for th,k,buyonly in itertools.product((.86,.92,.98,1.04,1.10,1.16),(3,5,8,12),(False,True))]

def apply_day(day,pr,p):
    th,k,buy=p
    z=[(conf(r,pr),r) for r in day if r['adx']>=18 and r['impulse']>=2 and (not buy or r['side']=='BUY')]
    z=[x for x in z if x[0]>=th];z.sort(key=lambda x:x[0],reverse=True)
    return [r for _,r in z[:k]]

def inner(train,p):
    dates=sorted(set(r['date'] for r in train));out=[]
    for i,d in enumerate(dates):
        if i<3:continue
        tr=[r for r in train if r['date']<d];day=[r for r in train if r['date']==d]
        out+=apply_day(day,priors(tr),p)
    s=sm(out)
    if s.get('n',0)<12 or s.get('dates',0)<2:return None
    return s

def choose(train):
    best=None
    for p in PARAMS:
        s=inner(train,p)
        if not s:continue
        score=(1 if s['wr']>=70 else 0,s['meanR'],s['wr'],min(s['n'],80))
        if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=prep(extract_fx());dates=sorted(set(r['date'] for r in rows));out=[];detail={}
    for i,d in enumerate(dates):
        if i<5:
            detail[d]={'warmup':True,'selected':{'n':0}};continue
        train=[r for r in rows if r['date']<d];day=[r for r in rows if r['date']==d];best=choose(train)
        sel=apply_day(day,priors(train),best[1]) if best else [];out+=sel
        detail[d]={'warmup':False,'rule':best[1] if best else None,'innerPerformance':best[2] if best else None,'selected':sm(sel)}
    result={'version':'FOREX V9 NESTED PAIR WALKFORWARD','providerCreditsUsed':0,
            'method':'Forex-only chronological nested walk-forward. Pair+side prior is shrunk to pair and F8 archetype group using only earlier dates, then combined with F8 technical quality. Threshold/topK selected only by expanding inner held-date tests.',
            'dates':dates,'walkForward':sm(out),'byDate':detail,'targetMet':False}
    s=result['walkForward'];result['targetMet']=bool(s.get('n',0)>=20 and (s.get('wr') or 0)>=80 and 1.0<=(s.get('avgRR') or 0)<=1.5 and s.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(result,open('data/offline_forex_v9_nested_pair.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
