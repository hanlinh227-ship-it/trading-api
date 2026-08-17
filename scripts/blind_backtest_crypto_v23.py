#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22

# V23 changes ONLY RR gating. Direction engine is frozen from V22.
# Both cutoffs were untouched before this file was locked.
CUTOFFS=[('BLIND_JUL08','2026-07-08T12:00:00Z'),('BLIND_JUL06','2026-07-06T12:00:00Z')]
OBSERVE_MS=5*60_000
HOURS=96
LOOKBACK=48
STOP_FACTOR=.75

def v23_rr(side,macro,micro,score,flow,move,model):
    sgn=1 if side=='BUY' else -1
    ma=macro*sgn>0; fa=micro*sgn>0
    ofi=abs(flow.get('ofi') or 0)
    if ma and fa and abs(score)>=2.4 and ofi>=.28 and abs(move)>=.12 and model.get('regime')=='trend': return 2.05
    if ma and fa and abs(score)>=1.5 and ofi>=.10: return 1.85
    if flow.get('available'):
        # Conflicting microflow: protect hit rate instead of forcing a distant target.
        return 1.55
    # No public flow coverage: only extend RR when the frozen price core is strong.
    return 1.65 if abs(macro)>=2.5 else 1.55

def future_once(source,sym,start):
    return v22.future(source,sym,start)

def summarize(rows):
    usable=[x for x in rows if x.get('decision')]
    resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[x for x in resolved if x['outcome']['result']=='TP']; losses=[x for x in resolved if x['outcome']['result']=='SL']
    total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    return {'marketTrades':len(usable),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None}

def run(label,cutoff):
    cut=v6.iso_ms(cutoff); entry_t=cut+OBSERVE_MS
    bs,bf,bm=v6.load_frames('BTC',cut); tmp=[]; errors=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            f=core.features(sym,fr,su,bf)
            tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'model':model,'f':f,'pre':fr['M5'][-1]['close']})
        except Exception as e: errors.append({'symbol':sym+'USDT','error':str(e)})
    breadth=sum(x['f']['r24']>0 for x in tmp)/len(tmp) if tmp else .5
    rows22=[]; rows23=[]; coverage=0
    for r in tmp:
        sym=r['sym']; macro=v22.macro_score(sym,r['f'],r['model'],breadth)
        try: flow=v22.tradeflow(sym,cut,entry_t)
        except Exception as e: flow={'available':False,'n':0,'ofi':0.0,'lastPx':None,'error':str(e)}
        if flow.get('available'): coverage+=1
        all_future=future_once(r['source'],sym,cut)
        obs=[x for x in all_future if x['ts']<entry_t]; post=[x for x in all_future if x['ts']>=entry_t]
        fallback=obs[-1]['close'] if obs else r['pre']; en=flow.get('lastPx') if flow.get('lastPx') is not None else fallback
        micro,move=v22.micro_score(flow,r['pre'],r['su']['M15'].get('atr14'))
        side,score,rr22=v22.side_rr(macro,micro,flow,move,r['model'])
        rr23=v23_rr(side,macro,micro,score,flow,move,r['model'])
        for rr,target in ((rr22,rows22),(rr23,rows23)):
            sl,tp,risk=v22.levels(sym,side,en,r['su'],r['fr'],rr)
            out=v22.evaluate(side,en,sl,tp,post)
            target.append({'symbol':sym+'USDT','cutoff':cutoff,'entryTimeMs':entry_t,'blind':True,'decision':side,'macroScore':round(macro,3),'microScore':round(micro,3),'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'risk':risk,'plannedRR':rr,'flow':flow,'microMoveATR':round(move,3),'model':r['model'],'outcome':out})
    return {'label':label,'cutoff':cutoff,'isTrueBlind':True,'breadth':round(breadth,3),'flowCoverage':round(coverage/len(tmp),3) if tmp else 0,'dataErrors':errors,'v22Frozen':{'summary':summarize(rows22),'tests':rows22},'v23RR':{'summary':summarize(rows23),'tests':rows23}}

def main():
    samples={n:run(n,c) for n,c in CUTOFFS}
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V23 true blind RR development. V22 direction is frozen exactly: 6h/24h/72h momentum + H4/H1 structure + H4 EMA + BTC-relative strength + first-5m OKX taker trade imbalance confirmation. Only RR changes: 1.55 conflict/weak, 1.65 strong core without flow, 1.85 macro+flow agreement, 2.05 strong aligned trend. Same +5m MARKET entry and same 48xM15 structural SL with .75 profile ATR floor. V22 frozen RR is evaluated side-by-side on the same unseen Jul08/Jul06 samples.','samples':samples}
    with open('data/blind_backtest_v23.json','w') as f: json.dump(payload,f,indent=2)
    print(json.dumps({k:{'v22':v['v22Frozen']['summary'],'v23':v['v23RR']['summary'],'flowCoverage':v['flowCoverage']} for k,v in samples.items()},indent=2))

if __name__=='__main__': main()
