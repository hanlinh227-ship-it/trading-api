#!/usr/bin/env python3
import json, os, statistics, itertools
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_crypto
from scripts.offline_crypto_v28_separate import PROFILE, FAMILY_WEIGHTS, base_symbol

def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1:continue
        z=dict(r);z['coin']=base_symbol(r['symbol']);z['family']=PROFILE.get(z['coin'],'L1');z['targetRR']=min(r['rr'],1.5);z['y']=1 if r['r']>0 else 0;z['targetR']=z['targetRR'] if z['y'] else -1
        b=r.get('breadth');z['breadth']=.5 if b is None else b;z['breadthAlign']=(z['breadth']-.5)*2*(1 if r['side']=='BUY' else -1)
        z['microAlign']=0 if r['micro']==0 else (1 if (r['side']=='BUY' and r['micro']>0) or (r['side']=='SELL' and r['micro']<0) else -1)
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    n=len(rows);w=sum(r['y'] for r in rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def daystate(rows):
    by=defaultdict(list)
    for r in rows:by[r['date']].append(r)
    out={}
    for d,x in by.items():
        b=statistics.median(r['breadth'] for r in x)
        out[d]={'breadth':b,'alignShare':sum(r['breadthAlign']>0 for r in x)/len(x),'medHTF':statistics.median(r['htf'] for r in x),'medMacro':statistics.median(r['macro'] for r in x),'medChase':statistics.median(r['chase'] for r in x),'trendShare':sum(r['regime']=='trend' for r in x)/len(x)}
    return out

def priors(dev):
    gp=(sum(r['y'] for r in dev)+5)/(len(dev)+10);byS=defaultdict(list);byF=defaultdict(list)
    for r in dev:byS[r['coin']].append(r['y']);byF[r['family']].append(r['y'])
    sp={k:(sum(v)+6*gp)/(len(v)+6) for k,v in byS.items()};fp={k:(sum(v)+10*gp)/(len(v)+10) for k,v in byF.items()}
    return gp,sp,fp

def score(r,pr):
    gp,sp,fp=pr;wb,wm,wh,wc=FAMILY_WEIGHTS.get(r['family'],(1,1,1,.8))
    return 1.4*sp.get(r['coin'],gp)+.6*fp.get(r['family'],gp)+1.0*wb*r['breadthAlign']+.5*wm*(r['macro']/6)+.7*wh*(r['htf']/10)+.25*r['microAlign']-.8*wc*r['chase']

def daypass(st,p):
    mode,minAlign,minHTF,minMacro,maxChase,minTrend=p
    b=st['breadth']
    if mode=='BULL' and b<.55:return False
    if mode=='BULL_STRONG' and b<.70:return False
    if mode=='BULL_EXTREME' and b<.85:return False
    if mode=='NON_BEAR_CAP' and b<.20:return False
    if mode=='ANY' and False:return False
    return st['alignShare']>=minAlign and st['medHTF']>=minHTF and st['medMacro']>=minMacro and st['medChase']<=maxChase and st['trendShare']>=minTrend

def tradepass(r,sideMode,minScore,pr):
    if sideMode=='ALIGN' and r['breadthAlign']<=0:return False
    if sideMode=='BUY' and r['side']!='BUY':return False
    return score(r,pr)>=minScore

def choose(dev,states):
    pr=priors(dev);best=None
    dates=sorted(set(r['date'] for r in dev))
    for p in itertools.product(('ANY','NON_BEAR_CAP','BULL','BULL_STRONG','BULL_EXTREME'),(0,.5,.6,.7),(0,2,4,6),(0,2,4,6),(99,.5,1.5,3.0),(0,.2,.4)):
      for side in ('ANY','ALIGN','BUY'):
       for floor in (.2,.5,.8,1.1):
        for topk in (3,5,8):
            z=[]
            for d in dates:
                if not daypass(states[d],p):continue
                q=[r for r in dev if r['date']==d and tradepass(r,side,floor,pr)];q=sorted(q,key=lambda r:score(r,pr),reverse=True)[:topk];z+=q
            s=sm(z)
            if s['n']<18 or s['dates']<3:continue
            # robustness: require at least half active days >=50 WR
            ds=[]
            for d in sorted(set(r['date'] for r in z)):
                x=sm([r for r in z if r['date']==d]);ds.append(x['wr'])
            pos=sum(x>=50 for x in ds)/len(ds)
            sc=(1 if s['wr']>=80 else 0,pos,s['wr'],s['meanR'],min(s['n'],40))
            if best is None or sc>best[0]:best=(sc,p,side,floor,topk,s)
    return best,pr

def main():
    rows=prep(extract_crypto());dates=sorted(set(r['date'] for r in rows));devdates=dates[:6];valdates=dates[6:];dev=[r for r in rows if r['date'] in devdates];val=[r for r in rows if r['date'] in valdates];states=daystate(rows)
    best,pr=choose(dev,states);sel=[];by={}
    if best:
        _,p,side,floor,topk,_=best
        for d in valdates:
            q=[]
            if daypass(states[d],p):q=[r for r in val if r['date']==d and tradepass(r,side,floor,pr)];q=sorted(q,key=lambda r:score(r,pr),reverse=True)[:topk]
            sel+=q;by[d]={'state':states[d],'selected':sm(q),'symbols':[r['coin'] for r in q]}
    res=sm(sel);out={'version':'CRYPTO V33 CONTINUATION STATE','providerCreditsUsed':0,'method':'Crypto-only. One market-state gate + symbol/family driver ranking chosen on first six dates, then frozen for the next six. Bearish capitulation exclusion is an explicit candidate; no Forex features.',
      'devDates':devdates,'validationDates':valdates,'rule':{'day':best[1],'sideMode':best[2],'scoreFloor':best[3],'topK':best[4]} if best else None,'development':best[5] if best else None,'validation':res,'validationByDate':by,
      'targetMet':bool(res.get('n',0)>=20 and res.get('wr',0)>=80 and 1<=res.get('avgRR',0)<=1.5 and res.get('meanR',-9)>0)}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v33_continuation_state.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
