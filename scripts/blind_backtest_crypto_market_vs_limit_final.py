#!/usr/bin/env python3
import json, os, statistics, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22
import blind_backtest_crypto_v24 as v24

LABEL='BLIND_MARKET_VS_LIMIT_APR16'
CUTOFF='2026-04-16T12:00:00Z'
OBSERVE_MS=5*60_000
LIMIT_VALID_MS=6*60*60_000
HOURS=96


def vwap(c, n=96):
    x=c[-n:]; num=den=0.0
    for z in x:
        vol=z.get('volume') or 0.0
        typ=(z['high']+z['low']+z['close'])/3.0
        num += typ*vol; den += vol
    return num/den if den else None


def ema(vals,p):
    if len(vals)<p:return None
    x=sum(vals[:p])/p; k=2/(p+1)
    for z in vals[p:]:x=z*k+x*(1-k)
    return x


def limit_price(side, market_entry, su, fr):
    m15=fr['M15']; vals=[x['close'] for x in m15]
    e20=ema(vals,20); vw=vwap(m15,96); atr=su['M15'].get('atr14') or market_entry*0.01
    candidates=[]
    if e20 is not None:candidates.append(('EMA20_M15',e20))
    if vw is not None:candidates.append(('VWAP_M15',vw))
    # Only use a favorable retracement relative to current MARKET entry.
    if side=='BUY':
        fav=[(n,p) for n,p in candidates if p<market_entry]
        if fav:
            n,p=max(fav,key=lambda t:t[1])
        else:
            n,p='ATR_PULLBACK',market_entry-0.5*atr
        # avoid placing an absurdly deep stale limit
        floor=market_entry-1.25*atr
        p=max(p,floor)
    else:
        fav=[(n,p) for n,p in candidates if p>market_entry]
        if fav:
            n,p=min(fav,key=lambda t:t[1])
        else:
            n,p='ATR_PULLBACK',market_entry+0.5*atr
        ceil=market_entry+1.25*atr
        p=min(p,ceil)
    return n,p


def fill_limit(side, px, post, valid_until):
    for i,c in enumerate(post):
        if c['ts']>valid_until:break
        if side=='BUY' and c['low']<=px:return i,c
        if side=='SELL' and c['high']>=px:return i,c
    return None,None


def summarize(rows,key):
    xs=[r[key] for r in rows if r.get(key)]
    if key=='limit':
        fills=[x for x in xs if x.get('filled')]
        resolved=[x for x in fills if x.get('outcome',{}).get('result') in ('TP','SL')]
        wins=[x for x in resolved if x['outcome']['result']=='TP']
        losses=[x for x in resolved if x['outcome']['result']=='SL']
        total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
        return {'signals':len(xs),'fills':len(fills),'fillRate':round(100*len(fills)/len(xs),2) if xs else None,'noFill':len(xs)-len(fills),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),'unresolvedAfterFill':len(fills)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None}
    resolved=[x for x in xs if x.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[x for x in resolved if x['outcome']['result']=='TP']; losses=[x for x in resolved if x['outcome']['result']=='SL']
    total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    return {'signals':len(xs),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),'unresolved':len(xs)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None}


def main():
    cut=v6.iso_ms(CUTOFF); entry_t=cut+OBSERVE_MS
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
        try:fl=v22.tradeflow(r['sym'],cut,entry_t)
        except Exception as e:fl={'available':False,'n':0,'ofi':0.0,'lastPx':None,'error':str(e)}
        r['flow']=fl
        if fl.get('available'):available.append(fl)
    fb=sum(x['ofi']>0 for x in available)/len(available) if available else .5
    fm=statistics.median([x['ofi'] for x in available]) if available else 0.0
    market_regime=v24.classify_market(pb,fb,fm)

    rows=[]
    for r in tmp:
        sym=r['sym']; flow=r['flow']
        macro=v22.macro_score(sym,r['f'],r['model'],pb)
        all_future=v22.future(r['source'],sym,cut)
        obs=[x for x in all_future if x['ts']<entry_t]
        post=[x for x in all_future if x['ts']>=entry_t]
        fallback=obs[-1]['close'] if obs else r['pre']
        market_entry=flow.get('lastPx') if flow.get('lastPx') is not None else fallback
        micro,move=v22.micro_score(flow,r['pre'],r['su']['M15'].get('atr14'))
        side,score,rr=v24.decide(macro,micro,flow,move,r['model'],market_regime)

        msl,mtp,mrisk=v22.levels(sym,side,market_entry,r['su'],r['fr'],rr)
        mout=v22.evaluate(side,market_entry,msl,mtp,post)
        market={'entry':market_entry,'sl':msl,'tp':mtp,'risk':mrisk,'plannedRR':rr,'outcome':mout}

        anchor,lpx=limit_price(side,market_entry,r['su'],r['fr'])
        li,fillbar=fill_limit(side,lpx,post,entry_t+LIMIT_VALID_MS)
        if fillbar is None:
            limit={'anchor':anchor,'entry':lpx,'filled':False,'validHours':6,'plannedRR':rr,'outcome':{'result':'NO_FILL'}}
        else:
            lsl,ltp,lrisk=v22.levels(sym,side,lpx,r['su'],r['fr'],rr)
            lpost=post[li:]
            lout=v22.evaluate(side,lpx,lsl,ltp,lpost)
            limit={'anchor':anchor,'entry':lpx,'filled':True,'fillTimeMs':fillbar['ts'],'sl':lsl,'tp':ltp,'risk':lrisk,'plannedRR':rr,'outcome':lout}

        rows.append({'symbol':sym+'USDT','decision':side,'score':round(score,3),'macroScore':round(macro,3),'microScore':round(micro,3),'marketRegime':market_regime,'priceBreadth':round(pb,3),'flowAvailable':bool(flow.get('available')),'market':market,'limit':limit})

    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'Final blind MARKET-vs-LIMIT execution comparison using the surviving V24 directional core after V25/V26/V27 rejections. Same frozen BUY/SELL signal for both executions. MARKET enters after +5m observation. LIMIT uses nearest favorable pre-known M15 EMA20 or M15 VWAP; if neither is favorable, 0.5 M15 ATR pullback; depth capped at 1.25 ATR. LIMIT expires after 6h. If filled, structural SL and same RR are recalculated from the better entry using V22 levels, then TP/SL is evaluated. No future data is used to choose direction or limit price. Cutoff fixed before outcomes inspection.','label':LABEL,'cutoff':CUTOFF,'entryTimeMs':entry_t,'marketRegime':market_regime,'priceBreadth':round(pb,3),'flowBreadth':round(fb,3),'flowMedian':round(fm,3),'flowCoverage':round(len(available)/len(tmp),3) if tmp else 0,'universe':len(v6.COINS),'tested':len(rows),'dataErrors':errors,'marketSummary':summarize(rows,'market'),'limitSummary':summarize(rows,'limit'),'tests':rows}
    with open('data/blind_backtest_market_vs_limit_final.json','w') as f:json.dump(payload,f,indent=2)
    print(json.dumps({'cutoff':CUTOFF,'regime':market_regime,'priceBreadth':round(pb,3),'flowCoverage':payload['flowCoverage'],'tested':len(rows),'errors':len(errors),'market':payload['marketSummary'],'limit':payload['limitSummary']},indent=2))

if __name__=='__main__':main()
