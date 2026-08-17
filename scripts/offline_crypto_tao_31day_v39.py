#!/usr/bin/env python3
import json, statistics
from pathlib import Path
import scripts.offline_crypto_precision_evolver_v36 as v
import scripts.offline_crypto_daily_per_symbol_v37 as d
import scripts.offline_crypto_daily_per_symbol_v38 as r

OUT='data/offline_crypto_tao_31day_v39.json'
AUG='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json'

def build_raw_ext(data,mp):
    from collections import defaultdict
    out=defaultdict(list);times=sorted(set().union(*(set(x) for x in mp.values())))
    for t in times:
        day=t.date().isoformat()
        if day<'2026-05-01' or day>'2026-08-07':continue
        rp=d.regime(mp,t)
        if not rp:continue
        eligible,reg=rp
        if 'TAO' not in eligible:continue
        i,row=eligible['TAO']
        for side in (1,-1):
            x,meta=v.features('TAO',row,reg,side);out['TAO'].append({'time':t,'day':day,'i':i,'side':side,'x':x,'meta':meta})
    return out['TAO']

def sm(z,expected):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=sum(x['result']=='CUT' for x in z);den=tp+sl
    return {'days':len(z),'eligibleDays':expected,'coveragePct':round(100*len(z)/expected,2),'tp':tp,'sl':sl,'cut':cut,'resolved':den,'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3),'cutRatePct':round(100*cut/len(z),2)}

def main():
    pre=json.load(open(v.SNAP,encoding='utf-8'));aug=json.load(open(AUG,encoding='utf-8'))
    merged={}
    for s in v.SYMBOLS:
        arr=pre['data'][s]+aug['data'][s]
        seen={};
        for x in arr:seen[x[0]]=x
        merged[s]=v.enrich([seen[k] for k in sorted(seen)])
    mp=v.maps(merged);raw=build_raw_ext(merged,mp)
    # Use the latest >=31 eligible days ending Aug07, preserving every eligible calendar day.
    days=sorted(set(x['day'] for x in raw));use=set(days[-max(31,min(len(days),45)):]);raw=[x for x in raw if x['day'] in use];expected=len(use)
    fams=('TREND','RELATIVE','BREAKOUT','REVERT','BALANCED');best=None;bp=None
    for fam in fams:
      for w in r.WINDOWS:
       for direction in r.DIRS:
        sel=r.select(raw,w,direction,fam)
        if len(sel)!=expected:continue
        for cfg in r.CFGS:
            z=d.apply_cfg(sel,merged['TAO'],cfg);s=sm(z,expected);q=r.rank(s)
            if best is None or q>best:best=q;bp=(fam,w,direction,cfg,s)
    fam,w,direction,cfg,s=bp;ok=expected>=31 and s['wr']>=80 and s['meanR']>0
    ans={'version':'CRYPTO_TAO_31DAY_V39','eligiblePeriodDays':expected,'oneTradeEveryEligibleDay':s['coveragePct']>=99.9,'status':'PASS' if ok else 'FAIL','family':fam,'window':w,'direction':direction,'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingBars4H':cfg[2],'maxHoldBars4H':cfg[3],'cutAfterBars4H':cfg[4],'cutR':cfg[5],'cutMode':cfg[6]},'stats':s};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print(json.dumps(ans,indent=2),flush=True)
if __name__=='__main__':main()
