#!/usr/bin/env python3
import json, os, math, statistics
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx


def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0: continue
        z=dict(r); z['targetRR']=min(r['rr'],1.5); z['y']=1 if r['r']>0 else 0; z['targetR']=z['targetRR'] if z['y'] else -1.0
        sg=1 if r['side']=='BUY' else -1
        z['h1Align']=1 if r['h1']==sg else 0; z['h4Align']=1 if r['h4']==sg else 0
        z['techConf']=r['score'] + r['adx']/25.0 + .7*r['impulse'] + .4*r['coh3'] + .3*r['coh24'] + .4*z['h4Align'] - .25*r['dev']
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['y'] for r in rows); n=len(rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def v7(r):
    return r['side']=='BUY' and r['score']>=.5 and r['adx']>=20 and r['impulse']>=3 and r['h1Align']==1

def day_state(rows):
    by=defaultdict(list)
    for r in rows:by[r['date']].append(r)
    out={}
    for d,x in by.items():
        out[d]={
          'h1Align':sum(r['h1Align'] for r in x)/len(x),
          'h4Align':sum(r['h4Align'] for r in x)/len(x),
          'buyShare':sum(r['side']=='BUY' for r in x)/len(x),
          'medAdx':statistics.median(r['adx'] for r in x),
          'medCoh3':statistics.median(r['coh3'] for r in x),
          'medCoh24':statistics.median(r['coh24'] for r in x),
          'medImpulse':statistics.median(r['impulse'] for r in x),
          'medRegimeEv':statistics.median(r['regimeEv'] for r in x),
          'regimeShare':sum(r['mode']=='REGIME_24H' for r in x)/len(x),
          'medFq3':statistics.median(r['fq3'] for r in x),
          'medFq24':statistics.median(r['fq24'] for r in x),
        }
    return out

KEYS=('h1Align','h4Align','buyShare','medAdx','medCoh3','medCoh24','medImpulse','medRegimeEv','regimeShare','medFq3','medFq24')

def pred_day_quality(d,past,states,dayperf,k,recency):
    avail=[x for x in past if dayperf.get(x,{}).get('n',0)>=3]
    if len(avail)<2:return None
    means={q:statistics.mean(states[x][q] for x in avail) for q in KEYS}
    sds={q:(statistics.pstdev(states[x][q] for x in avail) or 1.0) for q in KEYS}
    scored=[]
    for j,x in enumerate(avail):
        dist=math.sqrt(sum(((states[d][q]-states[x][q])/sds[q])**2 for q in KEYS)/len(KEYS))
        age=len(avail)-1-j
        w=1.0/(.25+dist)
        if recency:w*=1/(1+.15*age)
        scored.append((dist,w,x))
    scored=sorted(scored)[:k]
    den=sum(w for _,w,_ in scored)
    wr=sum(w*dayperf[x]['wr'] for _,w,x in scored)/den
    er=sum(w*dayperf[x]['meanR'] for _,w,x in scored)/den
    return {'predWR':wr,'predR':er,'neighbors':[x for _,_,x in scored]}

def select_day(rows,topk):
    z=[r for r in rows if v7(r)]
    if topk>0:z=sorted(z,key=lambda r:r['techConf'],reverse=True)[:topk]
    return z

def evaluate_param(train_dates,rows,states,dayperf,param):
    k,thr,recency,topk=param;sel=[]
    for i,d in enumerate(train_dates):
        if i<3:continue
        past=train_dates[:i];p=pred_day_quality(d,past,states,dayperf,k,recency)
        if p and p['predWR']>=thr and p['predR']>=0:
            sel+=select_day([r for r in rows if r['date']==d],topk)
    return sm(sel)

def choose(train_dates,rows,states,dayperf):
    best=None
    for k in (2,3,4):
      for thr in (50,55,60,65,70):
       for recency in (False,True):
        for topk in (0,4,6,8):
            p=(k,thr,recency,topk);s=evaluate_param(train_dates,rows,states,dayperf,p)
            if s['n']<12 or s['dates']<2:continue
            score=(1 if s['wr']>=80 else 0,s['wr'],s['meanR'],min(s['n'],30))
            if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=prep(extract_fx());dates=sorted(set(r['date'] for r in rows));states=day_state(rows)
    dayperf={d:sm(select_day([r for r in rows if r['date']==d],0)) for d in dates}
    outsel=[];detail={}
    for i,d in enumerate(dates):
        if i<5:detail[d]={'warmup':True,'v7Day':dayperf[d],'state':states[d]};continue
        train_dates=dates[:i];best=choose(train_dates,rows,states,dayperf)
        p=pred_day_quality(d,train_dates,states,dayperf,best[1][0],best[1][2]) if best else None
        gate=bool(best and p and p['predWR']>=best[1][1] and p['predR']>=0)
        sel=select_day([r for r in rows if r['date']==d],best[1][3]) if gate else []
        outsel+=sel;detail[d]={'warmup':False,'param':best[1] if best else None,'inner':best[2] if best else None,'prediction':p,'gate':gate,'v7Day':dayperf[d],'selected':sm(sel),'state':states[d]}
    res=sm(outsel)
    out={'version':'FOREX V11 DAY-REGIME GATE','providerCreditsUsed':0,'method':'Forex-only V7 continuation. Current-day common-factor state is compared only with earlier Forex days; gate parameters are chosen by inner chronological tests. No crypto features.',
         'walkForward':res,'byDate':detail,'targetMet':bool(res.get('n',0)>=20 and res.get('wr',0)>=80 and 1<=res.get('avgRR',0)<=1.5 and res.get('meanR',-9)>0)}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v11_day_gate.json','w'),indent=2)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
