#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
import scripts.offline_forex_precision_evolver_v15 as v

BASE='data/provider_snapshots/forex_h1_feb_jul_2026.json'
FINAL='data/provider_snapshots/forex_h1_aug1_8_2026_final1.json'
OUT='data/forex_v15_aug1_7_final1.json'
CFG=('LIMIT',1.0,.65,6,12,.35,4,2,-.45)
HP=('ET',7,25,.70,.08,1)


def combine(a,b):
    z={}
    for x in a+b:z[x[0]]=x
    return [z[k] for k in sorted(z)]


def final_times(maps):
    common=set.intersection(*(set(x) for x in maps.values()))
    return sorted(t for t in common if '2026-08-03'<=v.day(t)<='2026-08-07' and t.hour in (0,4,8,12,16,20))


def build_final_events(data,maps,times):
    out=[];scans=0
    for t in times:
        fp=v.factor_pack(maps,t)
        if not fp:continue
        for p in v.PAIRS:
            i,row=maps[p][t]
            if row.get('adx') is None or row.get('rsi') is None or row.get('ema50') is None:continue
            scans+=1
            for side in (1,-1):
                feat,meta=v.candidate_features(p,row,fp,side)
                o=v.execute(data[p],i,side,CFG)
                if o:out.append({'symbol':p,'time':t,'day':v.day(t),'x':feat,'side':side,'meta':meta,**o})
    return out,scans


def select(model,events):
    if not events:return []
    pr=model.predict_proba(np.asarray([x['x'] for x in events],float))[:,1]
    g=defaultdict(list)
    for e,p in zip(events,pr):g[(e['time'],e['symbol'])].append((float(p),e))
    cand=[]
    for k,z in g.items():
        z=sorted(z,key=lambda x:x[0],reverse=True);best=z[0];other=z[1][0] if len(z)>1 else 0
        if best[0]>=HP[3] and best[0]-other>=HP[4]:
            q=dict(best[1]);q['prob']=best[0];q['edge']=best[0]-other;cand.append(q)
    by=defaultdict(list)
    for e in cand:by[e['day']].append(e)
    out=[]
    for d,z in by.items():out.extend(sorted(z,key=lambda x:(x['prob'],x['edge']),reverse=True)[:HP[5]])
    return out


def sm(z):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cuts=[x for x in z if x['result']=='CUT'];den=tp+sl
    return {'n':len(z),'tp':tp,'sl':sl,'cut':len(cuts),'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'avgCutR':round(statistics.mean(x['r'] for x in cuts),3) if cuts else None,'cutRate':round(100*len(cuts)/len(z),2) if z else 0,'symbolsTraded':sorted(set(x['symbol'] for x in z))}


def main():
    base=json.load(open(BASE,encoding='utf-8'));final=json.load(open(FINAL,encoding='utf-8'))
    if base.get('coverageCount')!=28 or final.get('coverageCount')!=28:raise RuntimeError('coverage not 28/28')
    raw={p:combine(base['data'][p],final['data'][p]) for p in v.PAIRS}
    data={p:v.enrich(raw[p]) for p in v.PAIRS}
    maps={p:{r['dt']:(i,r) for i,r in enumerate(data[p])} for p in v.PAIRS}
    # Training events are strictly pre-August and use the already-frozen execution.
    train_maps,train_times=v.make_maps(data)
    train_events,train_scans=v.build_events(data,train_maps,train_times,CFG)
    mdl=v.train_model(train_events,HP[0],HP[1],HP[2])
    if mdl is None:raise RuntimeError('model train failed')
    ft=final_times(maps);events,scans=build_final_events(data,maps,ft);sel=select(mdl,events);s=sm(sel)
    passed=bool(s['n']>=4 and s['wr']>=80 and s['meanR']>0 and s['cutRate']<=50)
    result={'version':'FOREX_V15_AUG1_7_FINAL1','lockedCheckpoint':'docs/checkpoints/FOREX_V15_PRE_AUG_LOCK.md','scanUniverseCount':28,'all28Scanned':True,'signalDates':'2026-08-03..2026-08-07','execution':{'mode':'LIMIT','plannedRR':1.0,'riskFloorATR':.65,'swingHours':6,'maxHoldH':12,'limitOffsetATR':.35,'limitExpiryH':4,'cutAfterH':2,'cutRThreshold':-.45},'model':{'kind':'ExtraTrees','depth':7,'leaf':25,'threshold':.70,'sideMargin':.08,'topKPerDay':1},'trainingEndsBeforeAugust':True,'finalScanCount':scans,'finalCandidateEvents':len(events),'selected':s,'selectedTrades':[{'day':x['day'],'symbol':x['symbol'],'side':'BUY' if x['side']==1 else 'SELL','result':x['result'],'r':round(x['r'],3),'prob':round(x['prob'],4)} for x in sel],'finalTargetMet':passed}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(result,open(OUT,'w'),indent=2);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
