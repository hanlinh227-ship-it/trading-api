#!/usr/bin/env python3
import importlib.util, json, math
from datetime import datetime, timezone

spec=importlib.util.spec_from_file_location('v7','scripts/blind_backtest_crypto.py')
v7=importlib.util.module_from_spec(spec); spec.loader.exec_module(v7)

CUTOFFS=[
 ('OLD_REGRESSION_2026-08-13_12UTC','2026-08-13T12:00:00Z',False),
 ('NEW_BLIND_2026-08-13_16UTC','2026-08-13T16:00:00Z',True),
]

def percentile_rank(vals,x):
    a=sorted(vals)
    if len(a)<2:return .5
    return sum(v<x for v in a)/(len(a)-1)

def structural_plan(sym,side,score,model,sums,frames):
    p=v7.profile(sym); entry=frames['M5'][-1]['close']; a=sums['M15']['atr14'] or entry*.01
    highs,lows=v7.pivot_levels(frames['M15'],2,2,72); h1h,h1l=v7.pivot_levels(frames['H1'],2,2,60)
    # Stop: nearest meaningful invalidation beyond a profile-specific ATR floor.
    floor={'major':1.05,'defi':1.15,'l1_l2':1.18,'alt':1.20,'ai_high_beta':1.28,'new_high_beta':1.32,'meme':1.35}.get(p['type'],1.2)*a
    buf=p['stopBuf']*a
    if side=='BUY':
        candidates=sorted([x for x in lows if x<entry-.25*a],reverse=True)
        structural=entry-(candidates[0]-buf) if candidates else floor
    else:
        candidates=sorted([x for x in highs if x>entry+.25*a])
        structural=(candidates[0]+buf)-entry if candidates else floor
    risk=max(floor,structural)
    risk=min(risk,(2.0 if p['type'] in ('meme','new_high_beta','ai_high_beta') else 1.75)*a)
    sl=entry-risk if side=='BUY' else entry+risk

    # TP is a real liquidity/structure objective, not a fixed RR. Minimum RR depends on regime and confidence.
    rg=model['regime']
    if rg=='trend': minrr=1.15
    elif rg=='transition': minrr=1.05
    else: minrr=.95
    if abs(score)>=5:minrr+=.10
    elif abs(score)<1.2:minrr-=.05
    if p['type'] in ('meme','new_high_beta'):minrr-=.05
    minrr=max(.90,minrr)
    levels=(highs+h1h) if side=='BUY' else (lows+h1l)
    if side=='BUY':
        good=sorted(x for x in levels if x>=entry+minrr*risk)
        tp=good[0] if good else entry+minrr*risk
    else:
        good=sorted((x for x in levels if x<=entry-minrr*risk),reverse=True)
        tp=good[0] if good else entry-minrr*risk
    rr=abs(tp-entry)/risk
    cap=2.1 if rg=='trend' else 1.65
    if rr>cap:
        rr=cap; tp=entry+rr*risk if side=='BUY' else entry-rr*risk
    return entry,sl,tp,rr

def run_cutoff(label,cutoff,is_blind):
    cut=v7.iso_ms(cutoff)
    loaded={}; errors={}
    for sym in v7.COINS:
        try: loaded[sym]=v7.load_frames(sym,cut)
        except Exception as e: errors[sym]=str(e)
    if 'BTC' not in loaded: raise RuntimeError('BTC missing')
    btc_source,btc_inst,btc_frames,btc_sums=loaded['BTC']
    # Cross-sectional relative strength and breadth are known at cutoff and contain no future data.
    r1={}; r4={}; above=[]
    for sym,(source,inst,frames,sums) in loaded.items():
        r1[sym]=v7.ret(frames['H1'],12); r4[sym]=v7.ret(frames['H4'],6)
        above.append(1 if sums['H1']['close']>=sums['H1']['ema20'] else 0)
    vals1=list(r1.values()); vals4=list(r4.values()); breadth=sum(above)/len(above)
    results=[]
    for sym in v7.COINS:
        if sym not in loaded:
            results.append({'symbol':sym+'USDT','cutoff':cutoff,'error':errors.get(sym,'missing')}); continue
        source,inst,frames,sums=loaded[sym]
        base,model=v7.directional_score(sym,sums,frames,btc_frames,btc_sums)
        if sym=='BTC': cross=0.0
        else:
            p1=percentile_rank(vals1,r1[sym]); p4=percentile_rank(vals4,r4[sym])
            cross=1.05*((p1-.5)*2)+.75*((p4-.5)*2)+.45*((breadth-.5)*2)
            # Cross score is a tiebreaker; cannot overpower a high-confidence HTF setup.
            if abs(base)>=4.5:cross*=.55
        score=base+cross
        side='BUY' if score>=0 else 'SELL'
        entry,sl,tp,rr=structural_plan(sym,side,score,model,sums,frames)
        out=v7.evaluate(source,inst,sym,side,entry,sl,tp,cut)
        results.append({'symbol':sym+'USDT','cutoff':cutoff,'source':source,'blind':is_blind,'decision':side,'baseScore':round(base,3),'crossSectionScore':round(cross,3),'score':round(score,3),'marketBreadth':round(breadth,3),'entry':entry,'sl':sl,'tp':tp,'plannedRR':round(rr,3),'model':model,'outcome':out})
    usable=[r for r in results if r.get('decision') in ('BUY','SELL')]
    resolved=[r for r in usable if r.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[r for r in resolved if r['outcome']['result']=='TP']; losses=[r for r in resolved if r['outcome']['result']=='SL']
    total=sum(r['plannedRR'] if r['outcome']['result']=='TP' else -1 for r in resolved)
    s={'label':label,'cutoff':cutoff,'isTrueBlind':is_blind,'requested':len(v7.COINS),'marketTrades':len(usable),'dataErrors':len(results)-len(usable),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(r['plannedRR'] for r in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(breadth,3)}
    return {'summary':s,'tests':results}

def main():
    samples={}
    for label,cutoff,is_blind in CUTOFFS:samples[label]=run_cutoff(label,cutoff,is_blind)
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V9 forced-market: V7 regime/structure engine + cross-sectional relative strength and market breadth; free structure-based SL and nearest liquidity TP; no universal TP/SL; target floor varies by regime/profile/confidence; OLD regression and fresh NEW blind.','samples':samples}
    with open('data/blind_backtest_v9.json','w',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v['summary'] for k,v in samples.items()},indent=2))

if __name__=='__main__':main()
