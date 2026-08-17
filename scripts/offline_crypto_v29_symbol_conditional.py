#!/usr/bin/env python3
import json, os, math, statistics, itertools
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_crypto
from scripts.offline_crypto_v28_separate import PROFILE, base_symbol


def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0:continue
        z=dict(r);z['coin']=base_symbol(r['symbol']);z['family']=PROFILE.get(z['coin'],'L1')
        z['targetRR']=min(r['rr'],1.5);z['targetR']=z['targetRR'] if r['r']>0 else -1.0
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['targetR']>0 for r in rows);l=sum(r['targetR']<0 for r in rows);n=w+l
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def regime(r):
    b=r.get('breadth')
    if b is None:return 'UNKNOWN'
    if b>=.70:return 'BULL'
    if b<=.30:return 'BEAR'
    return 'MID'

def aligned(r):
    b=r.get('breadth')
    if b is None:return False
    return (b>=.5 and r['side']=='BUY') or (b<.5 and r['side']=='SELL')

def stats_map(dev):
    global_s=sm(dev); gp=(global_s.get('wins',0)+3)/(max(1,global_s.get('n',0))+6)
    fam=defaultdict(list); coin=defaultdict(list); cr=defaultdict(list); fr=defaultdict(list)
    for r in dev:
        fam[r['family']].append(r);coin[r['coin']].append(r);cr[(r['coin'],regime(r))].append(r);fr[(r['family'],regime(r))].append(r)
    def post(xs,parent,alpha=6):
        w=sum(x['targetR']>0 for x in xs);n=len(xs)
        return (w+alpha*parent)/(n+alpha),n
    fam_p={}
    for k,x in fam.items():fam_p[k]=post(x,gp,8)
    fr_p={}
    for k,x in fr.items():fr_p[k]=post(x,fam_p.get(k[0],(gp,0))[0],6)
    coin_p={}
    for k,x in coin.items():coin_p[k]=post(x,fam_p.get(PROFILE.get(k,'L1'),(gp,0))[0],5)
    cr_p={}
    for k,x in cr.items():cr_p[k]=post(x,fr_p.get((PROFILE.get(k[0],'L1'),k[1]),(gp,0))[0],4)
    return gp,fam_p,fr_p,coin_p,cr_p

def score_row(r,maps):
    gp,fam,fr,coin,cr=maps; rg=regime(r);f=r['family'];c=r['coin']
    pf=fam.get(f,(gp,0))[0];pfr=fr.get((f,rg),(pf,0))[0];pc=coin.get(c,(pf,0))[0];pcr=cr.get((c,rg),(pfr,0))[0]
    # Symbol-specific prior is strongest, then family/regime; current observable state adjusts it.
    prior=.40*pcr+.25*pc+.20*pfr+.15*pf
    cur=0.0
    cur += .08 if aligned(r) else -.08
    cur += .025*min(4.0,abs(r['macro']))
    cur += .018*min(8.0,abs(r['htf']))
    if r['micro']!=0:cur += .05 if ((r['side']=='BUY' and r['micro']>0) or (r['side']=='SELL' and r['micro']<0)) else -.05
    cur -= .04*min(2.0,r['chase'])
    return prior+cur

def choose(dev,maps):
    best=None
    for th,k,align_only in itertools.product((.50,.54,.58,.62,.66,.70,.74), (2,3,5,8,12), (False,True)):
        chosen=[]
        for d in sorted(set(r['date'] for r in dev)):
            day=[r for r in dev if r['date']==d]
            z=[(score_row(r,maps),r) for r in day if (not align_only or aligned(r))]
            z=[x for x in z if x[0]>=th];z.sort(key=lambda x:x[0],reverse=True)
            chosen += [r for _,r in z[:k]]
        s=sm(chosen)
        if s['n']<24 or s['dates']<4:continue
        by=[]
        for d in sorted(set(r['date'] for r in chosen)):
            q=sm([r for r in chosen if r['date']==d])
            if q['n']>=2:by.append(q['wr'])
        med=statistics.median(by) if by else s['wr'];pos=sum(v>=50 for v in by)/max(1,len(by))
        score=(pos,med,s['meanR'],s['wr'],min(s['n'],100))
        if best is None or score>best[0]:best=(score,(th,k,align_only),s)
    return best

def apply(rows,maps,rule):
    th,k,align_only=rule;out=[]
    for d in sorted(set(r['date'] for r in rows)):
        day=[r for r in rows if r['date']==d]
        z=[(score_row(r,maps),r) for r in day if (not align_only or aligned(r))]
        z=[x for x in z if x[0]>=th];z.sort(key=lambda x:x[0],reverse=True)
        out += [r for _,r in z[:k]]
    return out

def by_coin(rows):
    o={}
    for c in sorted(set(r['coin'] for r in rows)):
        z=[r for r in rows if r['coin']==c]
        if z:o[c]=sm(z)
    return o

def main():
    rows=prep(extract_crypto());dates=sorted(set(r['date'] for r in rows));cut=len(dates)//2
    devdates=dates[:cut];valdates=dates[cut:];dev=[r for r in rows if r['date'] in devdates];val=[r for r in rows if r['date'] in valdates]
    maps=stats_map(dev);best=choose(dev,maps);ds=apply(dev,maps,best[1]) if best else [];vs=apply(val,maps,best[1]) if best else []
    out={'version':'CRYPTO V29 SYMBOL-CONDITIONAL','providerCreditsUsed':0,
         'method':'Per-symbol Bayesian shrinkage learned only on development: coin+regime -> coin -> family+regime -> family, then adjusted by current breadth alignment, macro, HTF, micro and chase. One threshold/TopK frozen before validation.',
         'devDates':devdates,'validationDates':valdates,'rule':best[1] if best else None,'development':sm(ds),'validation':sm(vs),
         'validationByCoin':by_coin(vs),'targetMet':False,'hourlyManagement':'NOT_REPLAYABLE_FROM_COMMITTED_OLD_CRYPTO_DATA'}
    v=out['validation'];out['targetMet']=bool(v.get('n',0)>=20 and (v.get('wr') or 0)>=80 and 1.0<=(v.get('avgRR') or 0)<=1.5 and v.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v29_symbol_conditional.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({k:out[k] for k in ('version','providerCreditsUsed','devDates','validationDates','rule','development','validation','targetMet','hourlyManagement')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
