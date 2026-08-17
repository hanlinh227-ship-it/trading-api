#!/usr/bin/env python3
import json, os, math, statistics, itertools
from scripts.offline_crypto_v34_flow_mode import extract, sm, wilson

def candidates():
    # All fields are observable pre-entry and selected on Jul02 only.
    return itertools.product(
      (0,.02,.05,.10,.20,.35),          # min aligned OFI
      (0,1.5,2.5,3.5,5),                # min aligned score
      (-99,0,2,4,6),                     # min aligned HTF
      (-99,-1,0,1,2),                    # min aligned LTF
      (-99,-.5,0,.5,1.0),                # min aligned relative strength
      (-99,-.25,0,.25,.5),               # min aligned micro score
      (99,3,2,1,.5),                     # max chase adjustment
      ('ANY','trend','transition','range'),
      ('ANY','BREADTH','FLOW_BREADTH','BOTH'),
      ('ANY','BTC')
    )

def passed(r,p):
    ofi,score,htf,ltf,rs,micro,maxchase,reg,align,btc=p
    if not r['flowAvailable']:return False
    if r['ofiAlign']<ofi or r['scoreAlign']<score or r['htfAlign']<htf or r['ltfAlign']<ltf or r['rsAlign']<rs or r['microAlign']<micro:return False
    if r['chase']>maxchase:return False
    if reg!='ANY' and r['regime']!=reg:return False
    if align in ('BREADTH','BOTH') and r['breadthAlign']<=0:return False
    if align in ('FLOW_BREADTH','BOTH') and r['flowBreadthAlign']<=0:return False
    if btc=='BTC' and r['btcAlign']<=0:return False
    return True

def choose(dev):
    best=None
    for p in candidates():
        z=[r for r in dev if passed(r,p)];s=sm(z)
        if s.get('n',0)<10:continue
        lb=100*wilson(s['wins'],s['n'])
        # Prefer robust probability, then WR, expectancy, and sample. No validation feedback.
        score=(1 if s['wr']>=80 else 0,lb,s['wr'],s['meanR'],min(s['n'],30),-sum(1 for x in p if x not in (0,-99,99,'ANY')))
        if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=extract();dates=sorted(set(r['date'] for r in rows));dev=[r for r in rows if r['date']==dates[0]];val=[r for r in rows if r['date']==dates[-1]]
    best=choose(dev);sel=[r for r in val if best and passed(r,best[1])];v=sm(sel)
    out={'version':'CRYPTO V34B FLOW REFINE','providerCreditsUsed':0,
      'method':'Crypto FLOW_AVAILABLE only. Refinement selected solely on Jul02 using pre-entry OFI/HTF/LTF/relative-strength/micro/chase/breadth/BTC alignment; frozen unchanged on Jul04.',
      'developmentDate':dates[0],'validationDate':dates[-1],'rule':best[1] if best else None,'development':best[2] if best else None,'validation':v,
      'oneHoldoutTargetHit':bool(v.get('n',0)>=20 and v.get('wr',0)>=80 and 1<=v.get('avgRR',0)<=1.5 and v.get('meanR',-9)>0),
      'globalTargetMet':False,'note':'One validation date cannot establish global robustness even if the numeric threshold is hit.'}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v34b_flow_refine.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
