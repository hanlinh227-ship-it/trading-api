#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import scripts.offline_crypto_precision_evolver_v36b as vb

v=vb.v
BASE='data/provider_snapshots/crypto_4h_feb_jul_2026.json'
FINAL='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json'
OUT='data/crypto_v36b_aug1_7_final1.json'
CFG=('LIMIT',1.0,.65,5,4,.7,1,0,0)
HP=('HGB',3,8,.66,.16,1)


def combine(a,b):
    z={}
    for x in a+b:z[x[0]]=x
    return [z[k] for k in sorted(z)]


def final_times(mp):
    alltimes=sorted(set().union(*(set(x) for x in mp.values())))
    return [t for t in alltimes if '2026-08-01'<=v.day(t)<='2026-08-07']


def build_final_events(data,mp,times):
    out=[];requested_slots=0;eligible_slots=0
    for t in times:
        regpack=vb.fixed_regime_at(mp,t)
        if not regpack:continue
        eligible,reg=regpack;requested_slots+=61
        for sym in v.SYMBOLS:
            q=eligible.get(sym)
            if not q:continue
            i,row=q;eligible_slots+=1
            for side in (1,-1):
                feat,meta=v.features(sym,row,reg,side)
                o=v.execute(data[sym],i,side,CFG)
                if o:out.append({'symbol':sym,'time':t,'day':v.day(t),'side':side,'x':feat,'meta':meta,**o})
    return out,requested_slots,eligible_slots


def select(mdl,events):
    if not events:return []
    pr=mdl.predict_proba(np.asarray([x['x'] for x in events],float))[:,1]
    grouped=defaultdict(list)
    for e,p in zip(events,pr):grouped[(e['time'],e['symbol'])].append((float(p),e))
    cand=[]
    for _,z in grouped.items():
        z=sorted(z,key=lambda x:x[0],reverse=True);best=z[0];other=z[1][0] if len(z)>1 else 0
        if best[0]>=HP[3] and best[0]-other>=HP[4]:
            q=dict(best[1]);q['prob']=best[0];q['edge']=best[0]-other;cand.append(q)
    by=defaultdict(list)
    for x in cand:by[x['day']].append(x)
    out=[]
    for d,z in by.items():out.extend(sorted(z,key=lambda x:(x['prob'],x['edge']),reverse=True)[:HP[5]])
    return out


def sm(z):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cuts=[x for x in z if x['result']=='CUT'];den=tp+sl
    return {'n':len(z),'tp':tp,'sl':sl,'cut':len(cuts),'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'avgCutR':round(statistics.mean(x['r'] for x in cuts),3) if cuts else None,'cutRate':round(100*len(cuts)/len(z),2) if z else 0,'symbolsTraded':sorted(set(x['symbol'] for x in z))}


def main():
    base=json.load(open(BASE,encoding='utf-8'));final=json.load(open(FINAL,encoding='utf-8'))
    if base.get('coverageCount')!=61 or final.get('coverageCount')!=61:raise RuntimeError('coverage not 61/61')
    raw={s:combine(base['data'][s],final['data'][s]) for s in v.SYMBOLS}
    data={s:v.enrich(raw[s]) for s in v.SYMBOLS};mp=v.maps(data)
    # build_events itself only uses dates <= 2026-07-31, preserving the locked training boundary.
    train_events,_,_=v.build_events(data,mp,CFG)
    mdl=v.model(train_events,HP[0],HP[1],HP[2])
    if mdl is None:raise RuntimeError('model train failed')
    events,requested_slots,eligible_slots=build_final_events(data,mp,final_times(mp))
    selected=select(mdl,events);s=sm(selected)
    passed=bool(s['n']>=5 and s['wr']>=80 and s['meanR']>0 and s['cutRate']<=50)
    result={'version':'CRYPTO_V36B_AUG1_7_FINAL1','lockedCheckpoint':'docs/checkpoints/CRYPTO_V36B_PRE_AUG_LOCK.md','scanUniverseCount':61,'all61Loaded':True,'signalDates':'2026-08-01..2026-08-07','execution':{'mode':'LIMIT','plannedRR':1.0,'riskFloorATR':.65,'swingBars4H':5,'maxHoldBars4H':4,'limitOffsetATR':.7,'limitExpiryBars4H':1,'cutAfterBars4H':0},'model':{'kind':'HistGradientBoosting','depth':3,'leaf':8,'threshold':.66,'sideMargin':.16,'topKPerDay':1},'trainingEndsBeforeAugust':True,'requestedScanSlots':requested_slots,'eligibleScanSlots':eligible_slots,'finalCandidateEvents':len(events),'selected':s,'selectedTrades':[{'day':x['day'],'symbol':x['symbol'],'side':'BUY' if x['side']==1 else 'SELL','result':x['result'],'r':round(x['r'],3),'prob':round(x['prob'],4)} for x in selected],'finalTargetMet':passed}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(result,open(OUT,'w'),indent=2);print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
