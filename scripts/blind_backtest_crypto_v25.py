#!/usr/bin/env python3
import json, os, statistics, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22

# V25 DEVELOPMENT ONLY on June dates already revealed by V24 validation.
# Theory locked before this run:
# 1) macro momentum/structure owns direction;
# 2) first-5m taker flow is confirmation and may change RR, but may not independently flip macro;
# 3) only synchronized cross-market climax (extreme price breadth + extreme same-direction OFI)
#    may override macro direction, because one-sided aggressor flow after a broad move can mark exhaustion.
CUTOFFS=[
    ('DEV_JUN30','2026-06-30T12:00:00Z'),
    ('DEV_JUN27','2026-06-27T12:00:00Z'),
    ('DEV_JUN24','2026-06-24T12:00:00Z'),
    ('DEV_JUN21','2026-06-21T12:00:00Z'),
    ('DEV_JUN18','2026-06-18T12:00:00Z'),
]
OBSERVE_MS=5*60_000


def summarize(rows):
    resolved=[x for x in rows if x.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[x for x in resolved if x['outcome']['result']=='TP']; losses=[x for x in resolved if x['outcome']['result']=='SL']
    total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    return {
        'marketTrades':len(rows),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),
        'unresolved':len(rows)-len(resolved),
        'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,
        'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,
        'expectancyR':round(total/len(resolved),3) if resolved else None,
    }


def classify_market(pb,fb,fm):
    # Same-direction extreme = possible terminal crowding/climax, not clean continuation.
    if pb<=.25 and fb<=.35 and fm<=-.25: return 'sell_climax'
    if pb>=.75 and fb>=.65 and fm>=.25: return 'buy_climax'
    # Divergence states are context only in V25; they do not directly own direction.
    if pb<=.15 and fb>=.60 and fm>=.08: return 'bearish_breadth_positive_flow_divergence'
    if pb>=.85 and fb<=.40 and fm<=-.08: return 'bullish_breadth_negative_flow_divergence'
    return 'normal'


def decide(macro,micro,flow,model,market_regime):
    macro_side='BUY' if macro>=0 else 'SELL'
    if market_regime=='sell_climax':
        side='BUY'
    elif market_regime=='buy_climax':
        side='SELL'
    else:
        side=macro_side

    sgn=1 if side=='BUY' else -1
    flow_aligned=flow.get('available') and micro*sgn>0
    ofi=abs(flow.get('ofi') or 0.0)
    # Confidence score is diagnostic only; it cannot flip the side outside a climax state.
    score=macro + (0.35*micro if flow.get('available') else 0.0)
    if market_regime in ('sell_climax','buy_climax'):
        rr=1.60
    elif flow_aligned and abs(macro)>=3.0 and ofi>=.25 and model.get('regime')=='trend':
        rr=1.95
    elif flow_aligned and abs(macro)>=1.35 and ofi>=.10:
        rr=1.80
    else:
        rr=1.60
    return side,score,rr,macro_side,flow_aligned


def run(label,cutoff):
    cut=v6.iso_ms(cutoff); entry_t=cut+OBSERVE_MS
    bs,bf,bm=v6.load_frames('BTC',cut); tmp=[]; errors=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm); f=core.features(sym,fr,su,bf)
            tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'model':model,'f':f,'pre':fr['M5'][-1]['close']})
        except Exception as e:
            errors.append({'symbol':sym+'USDT','error':str(e)})

    pb=sum(x['f']['r24']>0 for x in tmp)/len(tmp) if tmp else .5
    available=[]
    for r in tmp:
        try: fl=v22.tradeflow(r['sym'],cut,entry_t)
        except Exception as e: fl={'available':False,'n':0,'ofi':0.0,'lastPx':None,'error':str(e)}
        r['flow']=fl
        if fl.get('available'): available.append(fl)
    fb=sum(x['ofi']>0 for x in available)/len(available) if available else .5
    fm=statistics.median([x['ofi'] for x in available]) if available else 0.0
    market_regime=classify_market(pb,fb,fm)

    rows=[]
    for r in tmp:
        sym=r['sym']; flow=r['flow']; macro=v22.macro_score(sym,r['f'],r['model'],pb)
        all_future=v22.future(r['source'],sym,cut); obs=[x for x in all_future if x['ts']<entry_t]; post=[x for x in all_future if x['ts']>=entry_t]
        fallback=obs[-1]['close'] if obs else r['pre']; en=flow.get('lastPx') if flow.get('lastPx') is not None else fallback
        micro,move=v22.micro_score(flow,r['pre'],r['su']['M15'].get('atr14'))
        side,score,rr,macro_side,flow_aligned=decide(macro,micro,flow,r['model'],market_regime)
        sl,tp,risk=v22.levels(sym,side,en,r['su'],r['fr'],rr); out=v22.evaluate(side,en,sl,tp,post)
        rows.append({
            'symbol':sym+'USDT','cutoff':cutoff,'entryTimeMs':entry_t,'blind':False,'development':True,
            'decision':side,'macroSide':macro_side,'directionOverriddenByClimax':side!=macro_side,
            'marketRegime':market_regime,'priceBreadth':round(pb,3),'flowBreadth':round(fb,3),'flowMedian':round(fm,3),
            'macroScore':round(macro,3),'microScore':round(micro,3),'confidenceScore':round(score,3),
            'flowAligned':bool(flow_aligned),'entry':en,'sl':sl,'tp':tp,'risk':risk,'plannedRR':rr,
            'flow':flow,'microMoveATR':round(move,3),'model':r['model'],'outcome':out,
        })
    return {
        'label':label,'cutoff':cutoff,'isTrueBlind':False,'development':True,
        'priceBreadth':round(pb,3),'flowBreadth':round(fb,3),'flowMedian':round(fm,3),
        'marketRegime':market_regime,'flowCoverage':round(len(available)/len(tmp),3) if tmp else 0,
        'dataErrors':errors,'summary':summarize(rows),'tests':rows,
    }


def main():
    samples={n:run(n,c) for n,c in CUTOFFS}
    all_rows=[r for s in samples.values() for r in s['tests']]
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'method':'V25 DEVELOPMENT candidate: macro/structure anchors direction; first-5m OKX taker flow confirms confidence/RR but cannot independently reverse macro; synchronized extreme price breadth plus same-direction extreme market OFI is treated as terminal crowding/climax and may override macro. Same +5m MARKET entry and V22 structural SL. June dates are already revealed development data and are NOT true blind.',
        'samples':samples,'aggregate':summarize(all_rows),
    }
    with open('data/v25_development.json','w') as f: json.dump(payload,f,indent=2)
    print(json.dumps({'aggregate':payload['aggregate'],'samples':{k:v['summary']|{'marketRegime':v['marketRegime'],'priceBreadth':v['priceBreadth'],'flowBreadth':v['flowBreadth'],'flowMedian':v['flowMedian']} for k,v in samples.items()}},indent=2))


if __name__=='__main__': main()
