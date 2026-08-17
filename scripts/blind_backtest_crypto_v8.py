#!/usr/bin/env python3
import importlib.util, json
from datetime import datetime, timezone

spec=importlib.util.spec_from_file_location('v7','scripts/blind_backtest_crypto.py')
v7=importlib.util.module_from_spec(spec); spec.loader.exec_module(v7)

# Fresh validation cutoff not used in prior V3-V7 reports.
CUTOFFS=[
 ('OLD_REGRESSION_2026-08-13_12UTC','2026-08-13T12:00:00Z',False),
 ('NEW_BLIND_2026-08-13_20UTC','2026-08-13T20:00:00Z',True),
]

def calibrate_balanced(m15,side):
    stops=[0.8,1.0,1.2,1.4,1.6,1.9,2.2]
    tps=[0.8,1.0,1.2,1.4,1.6,1.9,2.2,2.6]
    candidates=[]
    for sm in stops:
        for tm in tps:
            rr=tm/sm
            if rr<0.95 or rr>2.25: continue
            w=l=0
            for i in range(65,len(m15)-10,3):
                hist=m15[:i+1]; vals=[x['close'] for x in hist]
                e20=v7.ema(vals,20); e50=v7.ema(vals,50); rrsi=v7.rsi(vals); a=v7.local_atr(m15,i)
                if not a or not e20 or not e50: continue
                cl=m15[i]['close']
                aligned=(cl>=e20 and (rrsi or 50)>=48) if side=='BUY' else (cl<=e20 and (rrsi or 50)<=52)
                if not aligned: continue
                sl=cl-sm*a if side=='BUY' else cl+sm*a
                tp=cl+tm*a if side=='BUY' else cl-tm*a
                result=None
                for z in m15[i+1:i+9]:
                    hs=z['low']<=sl if side=='BUY' else z['high']>=sl
                    ht=z['high']>=tp if side=='BUY' else z['low']<=tp
                    if hs and ht: result='SL'; break
                    if hs: result='SL'; break
                    if ht: result='TP'; break
                if result=='TP': w+=1
                elif result=='SL': l+=1
            n=w+l
            if n>=18:
                wr=w/n; exp=(w*rr-l)/n
                if exp>=0.05: candidates.append((wr,exp,n,sm,tm,rr))
    if candidates:
        candidates.sort(key=lambda x:(x[0],x[1],x[2]),reverse=True); x=candidates[0]
        return {'stopATR':x[3],'tpATR':x[4],'rr':x[5],'histWinRate':x[0],'histExpectancyR':x[1],'samples':x[2],'mode':'balanced_positive_expectancy'}
    return {'stopATR':1.25,'tpATR':1.25,'rr':1.0,'histWinRate':None,'histExpectancyR':None,'samples':0,'mode':'balanced_fallback'}

v7.calibrate_barriers=calibrate_balanced

def choose_balanced(sym,sums,frames,btc_frames,btc_sums):
    sc,model=v7.directional_score(sym,sums,frames,btc_frames,btc_sums)
    side='BUY' if sc>=0 else 'SELL'; entry=frames['M5'][-1]['close']; p=v7.profile(sym)
    a=sums['M15']['atr14'] or entry*0.01; cal=calibrate_balanced(frames['M15'],side)
    highs,lows=v7.pivot_levels(frames['M15'],2,2,64); buf=p['stopBuf']*a
    if side=='BUY':
        piv=sorted([x for x in lows if x<entry],reverse=True); structural=(entry-(piv[0]-buf)) if piv else 1.15*a
    else:
        piv=sorted([x for x in highs if x>entry]); structural=((piv[0]+buf)-entry) if piv else 1.15*a
    # Keep invalidation structure, but avoid turning a local stop into a huge low-R stop.
    empirical=cal['stopATR']*a
    risk=max(empirical,min(structural,1.75*a))
    cap=2.05*a if p['type'] in ('meme','new_high_beta','ai_high_beta') else 1.85*a
    risk=min(risk,cap)
    sl=entry-risk if side=='BUY' else entry+risk
    desired=max(cal['tpATR']*a,0.98*risk)
    if model['regime']=='trend' and abs(sc)>=4.5 and abs(model['chaseAdjustment'])<1.0: desired*=1.12
    if abs(model['chaseAdjustment'])>=1.5: desired*=0.95
    tp=v7.choose_target_level(side,entry,desired,frames['M15'],frames['H1'])
    reward=abs(tp-entry); rr=reward/risk if risk else 0
    min_rr=0.95 if p['type'] in ('meme','new_high_beta','ai_high_beta') else 1.00
    max_rr=2.10 if model['regime']=='trend' else 1.70
    if rr<min_rr:
        reward=min_rr*risk; tp=entry+reward if side=='BUY' else entry-reward; rr=min_rr
    elif rr>max_rr:
        reward=max_rr*risk; tp=entry+reward if side=='BUY' else entry-reward; rr=max_rr
    return side,sc,entry,sl,tp,rr,cal,model

v7.choose=choose_balanced

def main():
    samples={}
    for label,cutoff,is_blind in CUTOFFS:
        samples[label]=v7.run_cutoff(label,cutoff,is_blind)
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V8 balanced free TP/SL: V7 directional model; per-coin pre-cutoff barrier calibration constrained to RR>=0.95 and historical expectancy>=+0.05R; nearest structure stop with capped width; liquidity target with minimum ~1R; OLD regression, NEW true blind.','samples':samples}
    with open('data/blind_backtest_v8.json','w',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v['summary'] for k,v in samples.items()},indent=2))

if __name__=='__main__': main()
