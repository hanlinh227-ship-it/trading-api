#!/usr/bin/env python3
import json, os, statistics, itertools
from scripts.offline_crypto_v34_flow_mode import extract, sm, wilson

def candidates():
    return itertools.product(
      (0,.03,.08,.15,.25),       # aligned OFI
      (0,1.5,3,4.5),             # aligned score
      (-99,0,3,6),               # HTF
      (-99,0,.5,1.0),            # relative strength
      (-99,0,.25),               # micro
      ('ANY','BREADTH','FLOW','BOTH'),
      (False,True))               # BTC aligned

def passed(r,p):
    ofi,score,htf,rs,micro,align,btc=p
    if not r['flowAvailable']:return False
    if r['ofiAlign']<ofi or r['scoreAlign']<score or r['htfAlign']<htf or r['rsAlign']<rs or r['microAlign']<micro:return False
    if align in ('BREADTH','BOTH') and r['breadthAlign']<=0:return False
    if align in ('FLOW','BOTH') and r['flowBreadthAlign']<=0:return False
    if btc and r['btcAlign']<=0:return False
    return True

def choose(dev):
    best=None
    for p in candidates():
        z=[r for r in dev if passed(r,p)];s=sm(z)
        if s.get('n',0)<10:continue
        lb=100*wilson(s['wins'],s['n'])
        score=(1 if s['wr']>=80 else 0,lb,s['wr'],s['meanR'],min(s['n'],30))
        if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=extract();dates=sorted(set(r['date'] for r in rows));dev=[r for r in rows if r['date']==dates[0]];val=[r for r in rows if r['date']==dates[-1]]
    best=choose(dev);sel=[r for r in val if best and passed(r,best[1])];v=sm(sel)
    out={'version':'CRYPTO V34C FLOW FOCUSED','providerCreditsUsed':0,'developmentDate':dates[0],'validationDate':dates[-1],
      'rule':best[1] if best else None,'development':best[2] if best else None,'validation':v,
      'oneHoldoutTargetHit':bool(v.get('n',0)>=20 and v.get('wr',0)>=80 and 1<=v.get('avgRR',0)<=1.5 and v.get('meanR',-9)>0),
      'globalTargetMet':False,'method':'Focused FLOW_AVAILABLE branch selected only on Jul02; frozen on Jul04. Pre-entry OFI/score/HTF/relative-strength/micro/breadth/BTC only.'}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v34c_flow_fast.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
