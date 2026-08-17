#!/usr/bin/env python3
import json, os, statistics, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22
import blind_backtest_crypto_v24 as v24

# V26 TRUE-BLIND candidate, frozen before May outcomes are inspected.
# Single conceptual change from V24: direction hierarchy.
# Macro momentum/structure owns BUY/SELL direction. Microflow and market-regime context
# may change confidence/RR, but may not independently flip the macro side.
# No climax reversal rule from rejected V25 is retained.
CUTOFFS=[
    ('BLIND_MAY30','2026-05-30T12:00:00Z'),
    ('BLIND_MAY27','2026-05-27T12:00:00Z'),
    ('BLIND_MAY24','2026-05-24T12:00:00Z'),
    ('BLIND_MAY21','2026-05-21T12:00:00Z'),
    ('BLIND_MAY18','2026-05-18T12:00:00Z'),
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


def context_score(macro,micro,flow,market_regime):
    # Preserve V24's regime-confidence transformation, but it no longer owns direction.
    score=macro+micro
    if market_regime=='capitulation_rebound':
        if flow.get('available') and micro>0:
            score=.45*macro+1.65*micro+.55
        elif macro<0:
            score=.85*macro
    elif market_regime=='distribution_reversal':
        if flow.get('available') and micro<0:
            score=.45*macro+1.65*micro-.55
        elif macro>0:
            score=.85*macro
    return score


def decide(macro,micro,flow,model,market_regime):
    score=context_score(macro,micro,flow,market_regime)
    side='BUY' if macro>=0 else 'SELL'
    sgn=1 if side=='BUY' else -1
    macro_aligned=macro*sgn>0
    flow_aligned=micro*sgn>0
    ofi=abs(flow.get('ofi') or 0.0)
    # Keep V24 RR ladder; only direction ownership changes.
    if macro_aligned and flow_aligned and abs(score)>=2.6 and ofi>=.25 and model.get('regime')=='trend':
        rr=1.95
    elif flow_aligned and abs(score)>=1.35 and ofi>=.10:
        rr=1.80
    else:
        rr=1.60
    return side,score,rr,flow_aligned


def run(label,cutoff):
    cut=v6.iso_ms(cutoff); entry_t=cut+OBSERVE_MS
    bs,bf,bm=v6.load_frames('BTC',cut); tmp=[]; errors=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            f=core.features(sym,fr,su,bf)
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
    market_regime=v24.classify_market(pb,fb,fm)

    rows=[]
    for r in tmp:
        sym=r['sym']; flow=r['flow']; macro=v22.macro_score(sym,r['f'],r['model'],pb)
        all_future=v22.future(r['source'],sym,cut)
        obs=[x for x in all_future if x['ts']<entry_t]; post=[x for x in all_future if x['ts']>=entry_t]
        fallback=obs[-1]['close'] if obs else r['pre']
        en=flow.get('lastPx') if flow.get('lastPx') is not None else fallback
        micro,move=v22.micro_score(flow,r['pre'],r['su']['M15'].get('atr14'))
        side,score,rr,flow_aligned=decide(macro,micro,flow,r['model'],market_regime)
        sl,tp,risk=v22.levels(sym,side,en,r['su'],r['fr'],rr)
        out=v22.evaluate(side,en,sl,tp,post)
        rows.append({
            'symbol':sym+'USDT','cutoff':cutoff,'entryTimeMs':entry_t,'blind':True,
            'decision':side,'marketRegime':market_regime,'priceBreadth':round(pb,3),
            'flowBreadth':round(fb,3),'flowMedian':round(fm,3),'macroScore':round(macro,3),
            'microScore':round(micro,3),'contextScore':round(score,3),'flowAligned':bool(flow_aligned),
            'entry':en,'sl':sl,'tp':tp,'risk':risk,'plannedRR':rr,'flow':flow,
            'microMoveATR':round(move,3),'model':r['model'],'outcome':out,
        })
    return {
        'label':label,'cutoff':cutoff,'isTrueBlind':True,'priceBreadth':round(pb,3),
        'flowBreadth':round(fb,3),'flowMedian':round(fm,3),'marketRegime':market_regime,
        'flowCoverage':round(len(available)/len(tmp),3) if tmp else 0,'dataErrors':errors,
        'summary':summarize(rows),'tests':rows,
    }


def main():
    samples={n:run(n,c) for n,c in CUTOFFS}
    all_rows=[r for s in samples.values() for r in s['tests']]
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'method':'V26 locked true blind. Same V24 short-horizon macro core, +5m OKX taker flow, V24 market-regime context, V22 structural 48xM15 SL with profile ATR floor, and V24 RR ladder. Single change: BUY/SELL direction is anchored to macro momentum/structure; microflow and market-regime transformations are confirmation/confidence only and cannot independently flip macro. Rejected V25 synchronized-climax reversal is not retained. Five May 2026 cutoffs were locked before outcomes were read.',
        'samples':samples,'aggregate':summarize(all_rows),
    }
    with open('data/blind_backtest_v26.json','w') as f: json.dump(payload,f,indent=2)
    print(json.dumps({'aggregate':payload['aggregate'],'samples':{k:v['summary']|{'marketRegime':v['marketRegime'],'priceBreadth':v['priceBreadth'],'flowBreadth':v['flowBreadth'],'flowMedian':v['flowMedian'],'flowCoverage':v['flowCoverage']} for k,v in samples.items()}},indent=2))


if __name__=='__main__': main()
