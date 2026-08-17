#!/usr/bin/env python3
import json, math, os, statistics, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22

# V24 addresses a structural failure mode found after V23: extreme cross-market price breadth can be
# capitulation/distribution rather than clean continuation. The new rule is locked before these dates.
CUTOFFS=[('BLIND_JUL04','2026-07-04T12:00:00Z'),('BLIND_JUL02','2026-07-02T12:00:00Z')]
OBSERVE_MS=5*60_000
HOURS=96

def clip(x,a,b): return max(a,min(b,x))

def summarize(rows):
    usable=[x for x in rows if x.get('decision')]
    resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[x for x in resolved if x['outcome']['result']=='TP']; losses=[x for x in resolved if x['outcome']['result']=='SL']
    total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    return {'marketTrades':len(usable),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None}

def classify_market(price_breadth, flow_breadth, flow_median):
    if price_breadth<=.15 and flow_breadth>=.60 and flow_median>=.08: return 'capitulation_rebound'
    if price_breadth>=.85 and flow_breadth<=.40 and flow_median<=-.08: return 'distribution_reversal'
    return 'normal'

def decide(macro,micro,flow,move,model,market_regime):
    score=macro+micro
    if market_regime=='capitulation_rebound':
        # Only actual positive aggressor flow may counter a bearish macro; no blind global flip.
        if flow.get('available') and micro>0:
            score=.45*macro+1.65*micro+.55
        elif macro<0:
            score=.85*macro
    elif market_regime=='distribution_reversal':
        if flow.get('available') and micro<0:
            score=.45*macro+1.65*micro-.55
        elif macro>0:
            score=.85*macro
    side='BUY' if score>=0 else 'SELL'; sgn=1 if side=='BUY' else -1
    ma=macro*sgn>0; fa=micro*sgn>0; ofi=abs(flow.get('ofi') or 0)
    # RR remains conservative until regime+flow prove the direction.
    if ma and fa and abs(score)>=2.6 and ofi>=.25 and model.get('regime')=='trend': rr=1.95
    elif fa and abs(score)>=1.35 and ofi>=.10: rr=1.80
    else: rr=1.60
    return side,score,rr

def run(label,cutoff):
    cut=v6.iso_ms(cutoff);entry_t=cut+OBSERVE_MS
    bs,bf,bm=v6.load_frames('BTC',cut);tmp=[];errors=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm);f=core.features(sym,fr,su,bf)
            tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'model':model,'f':f,'pre':fr['M5'][-1]['close']})
        except Exception as e: errors.append({'symbol':sym+'USDT','error':str(e)})
    pb=sum(x['f']['r24']>0 for x in tmp)/len(tmp) if tmp else .5
    # Collect all opening flow first so market-level order-flow breadth is observable before any decision.
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
        sym=r['sym'];macro=v22.macro_score(sym,r['f'],r['model'],pb);flow=r['flow']
        all_future=v22.future(r['source'],sym,cut);obs=[x for x in all_future if x['ts']<entry_t];post=[x for x in all_future if x['ts']>=entry_t]
        fallback=obs[-1]['close'] if obs else r['pre'];en=flow.get('lastPx') if flow.get('lastPx') is not None else fallback
        micro,move=v22.micro_score(flow,r['pre'],r['su']['M15'].get('atr14'))
        side,score,rr=decide(macro,micro,flow,move,r['model'],market_regime)
        sl,tp,risk=v22.levels(sym,side,en,r['su'],r['fr'],rr);out=v22.evaluate(side,en,sl,tp,post)
        rows.append({'symbol':sym+'USDT','cutoff':cutoff,'entryTimeMs':entry_t,'blind':True,'decision':side,'marketRegime':market_regime,'priceBreadth':round(pb,3),'flowBreadth':round(fb,3),'flowMedian':round(fm,3),'macroScore':round(macro,3),'microScore':round(micro,3),'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'risk':risk,'plannedRR':rr,'flow':flow,'microMoveATR':round(move,3),'model':r['model'],'outcome':out})
    return {'label':label,'cutoff':cutoff,'isTrueBlind':True,'priceBreadth':round(pb,3),'flowBreadth':round(fb,3),'flowMedian':round(fm,3),'marketRegime':market_regime,'flowCoverage':round(len(available)/len(tmp),3) if tmp else 0,'dataErrors':errors,'summary':summarize(rows),'tests':rows}

def main():
    samples={n:run(n,c) for n,c in CUTOFFS}
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V24 true blind regime guard. V22 short-horizon momentum/structure remains primary and first-5m OKX taker imbalance remains micro confirmation. New market-level guard compares pre-entry 24h price breadth with observable first-5m flow breadth/median: extreme bearish breadth plus broad positive flow is capitulation-rebound; extreme bullish breadth plus broad negative flow is distribution-reversal. Only coins with confirming actual flow are allowed to counter macro. Same +5m MARKET entry, same 48xM15 structural SL/.75 ATR floor, RR1.6/1.8/1.95. Rules locked before Jul04/Jul02 outcomes.','samples':samples}
    with open('data/blind_backtest_v24.json','w') as f: json.dump(payload,f,indent=2)
    print(json.dumps({k:v['summary']|{'marketRegime':v['marketRegime'],'priceBreadth':v['priceBreadth'],'flowBreadth':v['flowBreadth'],'flowCoverage':v['flowCoverage']} for k,v in samples.items()},indent=2))

if __name__=='__main__': main()
