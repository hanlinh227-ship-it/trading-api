#!/usr/bin/env python3
import json, os, statistics, itertools
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx, extract_crypto
from scripts.offline_crossmarket_fixed_rule_v5 import prep, sm, robust, managed, msm

def fx_score(r,mode):
    sg=1 if r['side']=='BUY' else -1
    align=(1 if r['h1']==sg else -1)+(1 if r['h4']==sg else -1)
    if mode=='BAL':return r['score']+.035*r['adx']+.8*r['coh3']+.22*r['impulse']+.18*align-.28*r['dev']
    if mode=='FAST':return 1.25*r['score']+.9*r['coh3']+.32*r['impulse']+.12*align-.38*r['dev']
    if mode=='STRUCT':return .75*r['score']+.025*r['adx']+.35*r['coh3']+.45*align-.12*r['dev']
    return r['score']

def cr_score(r,mode):
    b=r.get('breadth');align=0
    if b is not None:align=1 if ((b>=.5 and r['side']=='BUY') or (b<.5 and r['side']=='SELL')) else -1
    micro=0
    if r['micro']!=0:micro=1 if ((r['side']=='BUY' and r['micro']>0) or (r['side']=='SELL' and r['micro']<0)) else -1
    if mode=='BAL':return r['score']+.35*r['macro']+.16*r['htf']+1.4*align+.35*micro-.3*r['chase']
    if mode=='HTF':return .6*r['score']+.2*r['macro']+.28*r['htf']+1.0*align+.25*micro
    if mode=='BREADTH':return .7*r['score']+.25*r['macro']+.12*r['htf']+2.2*align+.25*micro
    return r['score']

def topk(rows,scorefn,mode,k,minscore=0):
    out=[]
    for d in sorted(set(r['date'] for r in rows)):
        day=[r for r in rows if scorefn(r,mode)>=minscore]
        day.sort(key=lambda r:scorefn(r,mode),reverse=True);out+=day[:k]
    return out

def choose(dev,scorefn,modes,ks,mins):
    best=None
    for mode,k,mn in itertools.product(modes,ks,mins):
        x=topk(dev,scorefn,mode,k,mn)
        if len(x)<20 or len(set(r['date'] for r in x))<4:continue
        rb=robust(x);s=rb['summary']
        score=(1 if s['wr']>=80 else 0,rb['wilson80LB'],rb['positiveDayRate'],rb['medianDayWR'],s['meanR'],s['wr'])
        if best is None or score>best[0]:best=(score,(mode,k,mn),rb)
    return best

def split(rows,scorefn,modes,ks,mins):
    dates=sorted(set(r['date'] for r in rows));cut=len(dates)//2;devd=dates[:cut];vald=dates[cut:]
    dev=[r for r in rows if r['date'] in devd];val=[r for r in rows if r['date'] in vald]
    b=choose(dev,scorefn,modes,ks,mins)
    dv=topk(dev,scorefn,b[1][0],b[1][1],b[1][2]) if b else []
    vv=topk(val,scorefn,b[1][0],b[1][1],b[1][2]) if b else []
    return {'devDates':devd,'validationDates':vald,'rule':b[1] if b else None,'development':robust(dv) if dv else None,'validation':robust(vv) if vv else None},dv,vv

def choose_cut(dev):
    best=None
    for th in (-.1,-.2,-.3,-.4,-.5,-.6,-.75):
        z=managed(dev,th);s=msm(z)
        if s['TP']+s['SL']<15 or s['cutRate']>45:continue
        score=(1 if (s['wrExcludingCut'] or 0)>=80 else 0,s['wrExcludingCut'] or 0,s['meanManagedRIncludingCut'],-s['cutRate'])
        if best is None or score>best[0]:best=(score,th,s)
    return best

def main():
    fx=prep(extract_fx());cr=prep(extract_crypto())
    ft,fd,fv=split(fx,fx_score,('BAL','FAST','STRUCT','RAW'),(4,5,6,8),(0,.5,1,1.5,2))
    ct,cd,cv=split(cr,cr_score,('BAL','HTF','BREADTH','RAW'),(4,5,6,8,10),(0,1,2,3,4))
    hc=choose_cut(fd);hm=msm(managed(fv,hc[1])) if hc and fv else {'n':0}
    out={'version':'CROSSMARKET TOPK V6','providerCreditsUsed':0,
      'method':'Confidence formula + daily Top-K frozen on chronological first half, then applied unchanged to second half. RR conservatively capped to 1.5 without converting old losses.',
      'FOREX':{'topK':ft,'H3Cut':{'rule':hc[1] if hc else None,'development':hc[2] if hc else None,'validation':hm}},
      'CRYPTO':{'topK':ct,'hourlyManagement':'NOT_REPLAYABLE_FROM_OLD_DATA'}}
    out['FOREX']['targetMet']=bool(hm.get('n',0)>=20 and (hm.get('wrExcludingCut') or 0)>=80 and 1<=hm.get('avgRR',0)<=1.5 and hm.get('meanManagedRIncludingCut',-9)>0)
    cvs=(ct.get('validation') or {}).get('summary') if ct.get('validation') else None
    out['CRYPTO']['targetMet']=bool(cvs and cvs['n']>=20 and cvs['wr']>=80 and 1<=cvs['avgRR']<=1.5 and cvs['meanR']>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crossmarket_topk_v6.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
