#!/usr/bin/env python3
import json, os, math, statistics
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_crypto
from scripts.offline_crypto_v28_separate import PROFILE, FAMILY_WEIGHTS, base_symbol


def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0: continue
        z=dict(r);z['coin']=base_symbol(r['symbol']);z['family']=PROFILE.get(z['coin'],'L1')
        z['targetRR']=min(r['rr'],1.5);z['y']=1 if r['r']>0 else 0;z['targetR']=z['targetRR'] if z['y'] else -1.0
        b=r.get('breadth');z['breadthAlign']=0.0 if b is None else (b-.5)*2*(1 if r['side']=='BUY' else -1)
        z['microAlign']=0 if r['micro']==0 else (1 if (r['side']=='BUY' and r['micro']>0) or (r['side']=='SELL' and r['micro']<0) else -1)
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    n=len(rows);w=sum(r['y'] for r in rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def day_state(rows):
    by=defaultdict(list)
    for r in rows:by[r['date']].append(r)
    st={}
    for d,x in by.items():
        bs=[r['breadth'] for r in x if r.get('breadth') is not None];b=statistics.median(bs) if bs else .5
        st[d]={
          'breadth':b,'extreme':abs(b-.5)*2,
          'medMacro':statistics.median(r['macro'] for r in x),'medHTF':statistics.median(r['htf'] for r in x),
          'medChase':statistics.median(r['chase'] for r in x),'buyShare':sum(r['side']=='BUY' for r in x)/len(x),
          'alignShare':sum(r['breadthAlign']>0 for r in x)/len(x),
          'microAgreeShare':sum(r['microAlign']>0 for r in x)/len(x),
          'trendShare':sum(r['regime']=='trend' for r in x)/len(x),
          'transitionShare':sum(r['regime']=='transition' for r in x)/len(x),
          'rangeShare':sum(r['regime']=='range' for r in x)/len(x),
        }
    return st

KEYS=('breadth','extreme','medMacro','medHTF','medChase','buyShare','alignShare','microAgreeShare','trendShare','transitionShare','rangeShare')

def priors(train):
    gp=(sum(r['y'] for r in train)+5)/(len(train)+10)
    def mk(key,a):
        by=defaultdict(list)
        for r in train:by[key(r)].append(r['y'])
        return {k:(sum(v)+a*gp)/(len(v)+a) for k,v in by.items()}
    return gp,mk(lambda r:r['coin'],5),mk(lambda r:r['family'],10),mk(lambda r:(r['coin'],r['side']),7)

def symbol_score(r,pr,w):
    gp,sp,fp,ssp=pr;wb,wm,wh,wc=FAMILY_WEIGHTS.get(r['family'],(1,1,1,.8))
    a,b,c,d,e,f=w
    return (a*ssp.get((r['coin'],r['side']),sp.get(r['coin'],gp)) + b*fp.get(r['family'],gp) +
            c*wb*r['breadthAlign'] + d*wm*(r['macro']/6.0) + e*wh*(r['htf']/10.0) + .25*r['microAlign'] - f*wc*r['chase'])

def side_perf(rows,side=None):
    z=[r for r in rows if side is None or r['side']==side];return sm(z)

def neighbor_prediction(d,past,states,perf,k,recency):
    avail=[x for x in past if perf[x]['all'].get('n',0)>=20]
    if len(avail)<2:return None
    means={q:statistics.mean(states[x][q] for x in avail) for q in KEYS};sds={q:(statistics.pstdev(states[x][q] for x in avail) or 1) for q in KEYS}
    arr=[]
    for j,x in enumerate(avail):
        dist=math.sqrt(sum(((states[d][q]-states[x][q])/sds[q])**2 for q in KEYS)/len(KEYS));age=len(avail)-1-j
        wt=1/(.2+dist)*(1/(1+.18*age) if recency else 1);arr.append((dist,wt,x))
    arr=sorted(arr)[:k];den=sum(w for _,w,_ in arr)
    def pred(side):
        vals=[]
        for _,wt,x in arr:
            s=perf[x][side]
            if s.get('n',0):vals.append((wt,s['wr'],s['meanR']))
        dd=sum(v[0] for v in vals)
        return {'wr':sum(w*wr for w,wr,_ in vals)/dd,'r':sum(w*rr for w,_,rr in vals)/dd} if dd else {'wr':0,'r':-9}
    return {'ALL':pred('all'),'BUY':pred('BUY'),'SELL':pred('SELL'),'neighbors':[x for _,_,x in arr]}

def rank_day(dayrows,train,w,topk,score_floor,side_mode,pred):
    pr=priors(train);z=[]
    side=None
    if side_mode=='PREDICT_BEST':side='BUY' if pred['BUY']['r']>=pred['SELL']['r'] else 'SELL'
    for r in dayrows:
        if side and r['side']!=side:continue
        if side_mode=='BREADTH_ALIGN' and r['breadthAlign']<=0:continue
        sc=symbol_score(r,pr,w)
        if sc>=score_floor:z.append((sc,r))
    return [r for _,r in sorted(z,key=lambda x:x[0],reverse=True)[:topk]]

WEIGHTS=((1.2,.5,.8,.5,.6,.6),(1.5,.3,1.0,.4,.7,.8),(1.0,.7,1.2,.3,.8,1.0))

def inner_eval(train_dates,rows,states,perf,param):
    k,recency,daywr,dayr,topk,floor,side_mode,widx=param;out=[]
    for i,d in enumerate(train_dates):
        if i<4:continue
        past=train_dates[:i];pred=neighbor_prediction(d,past,states,perf,k,recency)
        if not pred:continue
        bestside=max(pred['BUY']['r'],pred['SELL']['r'])
        gate=(pred['ALL']['wr']>=daywr and pred['ALL']['r']>=dayr) or (side_mode=='PREDICT_BEST' and bestside>=dayr and max(pred['BUY']['wr'],pred['SELL']['wr'])>=daywr)
        if not gate:continue
        tr=[r for r in rows if r['date']<d];day=[r for r in rows if r['date']==d]
        out+=rank_day(day,tr,WEIGHTS[widx],topk,floor,side_mode,pred)
    return sm(out)

def choose(train_dates,rows,states,perf):
    best=None
    for k in (2,3,4):
     for rec in (False,True):
      for dwr in (40,45,50,55,60):
       for dr in (-.1,0,.1,.2,.3):
        for topk in (3,4,5,6):
         for floor in (.35,.5,.65,.8,1.0):
          for side in ('ANY','BREADTH_ALIGN','PREDICT_BEST'):
           for wi in range(len(WEIGHTS)):
            p=(k,rec,dwr,dr,topk,floor,side,wi);s=inner_eval(train_dates,rows,states,perf,p)
            if s['n']<15 or s['dates']<3:continue
            score=(1 if s['wr']>=80 else 0,s['wr'],s['meanR'],min(s['n'],35))
            if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=prep(extract_crypto());dates=sorted(set(r['date'] for r in rows));states=day_state(rows)
    perf={d:{'all':side_perf([r for r in rows if r['date']==d]),'BUY':side_perf([r for r in rows if r['date']==d],'BUY'),'SELL':side_perf([r for r in rows if r['date']==d],'SELL')} for d in dates}
    outsel=[];detail={}
    for i,d in enumerate(dates):
        if i<6:detail[d]={'warmup':True,'state':states[d],'perf':perf[d]};continue
        train_dates=dates[:i];best=choose(train_dates,rows,states,perf)
        if not best:detail[d]={'warmup':False,'selected':{'n':0}};continue
        k,rec,dwr,dr,topk,floor,side,wi=best[1];pred=neighbor_prediction(d,train_dates,states,perf,k,rec)
        bestside=max(pred['BUY']['r'],pred['SELL']['r'])
        gate=(pred['ALL']['wr']>=dwr and pred['ALL']['r']>=dr) or (side=='PREDICT_BEST' and bestside>=dr and max(pred['BUY']['wr'],pred['SELL']['wr'])>=dwr)
        day=[r for r in rows if r['date']==d];tr=[r for r in rows if r['date']<d]
        sel=rank_day(day,tr,WEIGHTS[wi],topk,floor,side,pred) if gate else []
        outsel+=sel;detail[d]={'warmup':False,'param':best[1],'inner':best[2],'prediction':pred,'gate':gate,'selected':sm(sel),'symbols':[r['coin'] for r in sel],'state':states[d],'actualAll':perf[d]['all']}
    res=sm(outsel);out={'version':'CRYPTO V32 MARKET-DAY SYMBOL GATE','providerCreditsUsed':0,
      'method':'Crypto-only: market-day regime first using only prior crypto days, then symbol/family priors + linked-driver weights + breadth/HTF/macro/micro/chase. No Forex features.',
      'walkForward':res,'byDate':detail,'targetMet':bool(res.get('n',0)>=20 and res.get('wr',0)>=80 and 1<=res.get('avgRR',0)<=1.5 and res.get('meanR',-9)>0),
      'hourlyManagement':'NOT_REPLAYABLE_FROM_COMMITTED_OLD_CRYPTO_DATA'}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v32_market_symbol_gate.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
